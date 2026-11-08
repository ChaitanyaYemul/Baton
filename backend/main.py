import base64
import copy
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Literal
import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from backend.engine import DEMO, KINDS, now, parse_source, reconstruct, redact
from backend.llm import cache_identity

app = FastAPI(title='Baton API', version='0.1.0')
DB = Path(os.getenv('BATON_DB', 'data/baton.sqlite3'))
LOCK = threading.RLock()
ROLES = {'reviewer': ('Kabir', ['core','technical','leads']), 'successor': ('Meera', ['core','technical']),
         'coordinator': ('Riya', ['core']), 'leaver': ('Aarav', ['core','technical'])}

def initial():
    return {'project': 'Fest registration portal', 'sources': [], 'claims': [], 'versions': [], 'audit': [],
            'acks': [], 'mode': 'Not reconstructed', 'sudden_exit': False, 'cache': {}}

def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute('CREATE TABLE IF NOT EXISTS workspace (id INTEGER PRIMARY KEY, body TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS users (role TEXT PRIMARY KEY, salt TEXT, password TEXT)')
    con.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, role TEXT, expires REAL)')
    con.execute('INSERT OR IGNORE INTO workspace VALUES (1, ?)', (json.dumps(initial()),))
    for role in ROLES:
        # Demo accounts are explicitly opt-in on hosted installations.
        password = os.getenv(f'BATON_{role.upper()}_PASSWORD')
        if not password and os.getenv('BATON_DEMO', '0') == '1':
            password = 'baton-demo-2026'
        if password:
            salt = hashlib.sha256(f'baton-{role}'.encode()).hexdigest()
            digest = password_digest(role, password, salt)
            existing = con.execute('SELECT password FROM users WHERE role=?', (role,)).fetchone()
            if not existing or existing[0] != digest:
                con.execute('INSERT OR REPLACE INTO users VALUES (?,?,?)', (role,salt,digest))
                con.execute('DELETE FROM sessions WHERE role=?', (role,))
    con.commit()
    return con

from functools import lru_cache

@lru_cache(maxsize=16)
def password_digest(role, password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 200000).hex()

@contextmanager
def state():
    with LOCK:
        con = connect()
        try:
            data = json.loads(con.execute('SELECT body FROM workspace WHERE id=1').fetchone()[0])
            yield data
            con.execute('UPDATE workspace SET body=? WHERE id=1', (json.dumps(data),))
            con.commit()
        finally:
            con.close()

def audit(s, role, action, detail=''):
    s['audit'].append({'at': now(), 'actor': ROLES[role][0], 'action': action, 'detail': detail})

def auth(request, reviewer=False):
    token = request.cookies.get('baton_session', '')
    with LOCK:
        con = connect()
        row = con.execute('SELECT role FROM sessions WHERE token=? AND expires>?', (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
        con.close()
    if not row:
        raise HTTPException(401, 'Sign in to continue')
    if reviewer and row[0] != 'reviewer':
        raise HTTPException(403, 'Reviewer access required')
    if request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('x-baton-request') != '1':
        raise HTTPException(403, 'Missing request protection header')
    return row[0]

@app.middleware('http')
async def guard(request, call_next):
    if int(request.headers.get('content-length', '0') or 0) > 1200000:
        return Response('Request too large', status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api') else 'no-cache'
    return response

class Login(BaseModel):
    role: Literal['reviewer','successor','coordinator','leaver']
    password: str = Field(max_length=200)

FAILURES = {}

@app.post('/api/login')
def login(body: Login, request: Request, response: Response):
    address = request.client.host if request.client else 'unknown'
    with LOCK:
        failures = [t for t in FAILURES.get(address, []) if t > time.time()-60]
        if len(failures) >= 10:
            raise HTTPException(429, 'Too many attempts; try again in a minute')
        con = connect()
        row = con.execute('SELECT salt,password FROM users WHERE role=?', (body.role,)).fetchone()
        digest = hashlib.pbkdf2_hmac('sha256', body.password.encode(), (row[0] if row else 'dummy').encode(), 200000).hex()
        if not row or not hmac.compare_digest(digest, row[1]):
            con.close()
            FAILURES[address] = failures + [time.time()]
            raise HTTPException(401, 'Incorrect password or account is not configured')
        token = secrets.token_urlsafe(32)
        con.execute('INSERT INTO sessions VALUES (?,?,?)', (hashlib.sha256(token.encode()).hexdigest(),body.role,time.time()+28800))
        con.commit()
        con.close()
    response.set_cookie('baton_session',token,httponly=True,samesite='strict',secure=os.getenv('BATON_SECURE_COOKIE')=='1',max_age=28800)
    return {'role': body.role, 'name': ROLES[body.role][0]}

@app.post('/api/logout')
def logout(request: Request, response: Response):
    auth(request)
    with LOCK:
        con=connect()
        con.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(request.cookies.get('baton_session','').encode()).hexdigest(),))
        con.commit(); con.close()
    response.delete_cookie('baton_session')
    return {'ok': True}

def visible(c, s, role):
    sources = {x['id']:x for x in s['sources']}
    return bool(c['evidence']) and all(e['source_id'] in sources and sources[e['source_id']]['access'] in ROLES[role][1] for e in c['evidence'])

def filtered(claims, s, role):
    result = []
    for claim in claims:
        if not visible(claim,s,role):
            result.append({'id':claim['id'],'restricted':True,'text':'Restricted knowledge','owner':'Kabir','reason':'Ask the reviewer for access.'})
        else:
            c=copy.deepcopy(claim)
            # Never reveal identifiers of conflicting restricted records.
            c['conflicts']=[x for x in c['conflicts'] if any(p['id']==x and visible(p,s,role) for p in claims)]
            result.append(c)
    return result

@app.get('/api/workspace')
def workspace(request: Request):
    role=auth(request)
    with state() as s:
        claims = s['claims'] if role in ('reviewer','leaver') else s['versions'][-1]['claims'] if s['versions'] else []
        digest=hashlib.sha256(json.dumps([(x['id'],x['access']) for x in s['sources']]).encode()).hexdigest()
        result={'project':s['project'],'user':{'role':role,'name':ROLES[role][0]},'claims':filtered(claims,s,role),
                'sources':[{k:v for k,v in x.items() if k!='text'} for x in s['sources'] if x['access'] in ROLES[role][1] and (role in ('reviewer','leaver') or s['versions'])],
                'versions':[{'number':v['number'],'at':v['at'],'by':v['by'],'count':len(v['claims'])} for v in s['versions']],
                'audit':s['audit'][-100:][::-1] if role=='reviewer' else [],
                'acks':[a for a in s['acks'] if (a['role']==role or role=='reviewer') and a.get('access_hash')==digest], 'mode':s['mode'] if role=='reviewer' else 'Approved handover',
                'sudden_exit':s['sudden_exit'],'demo':os.getenv('BATON_DEMO','0')=='1'}
        return result

class SourceIn(BaseModel):
    name: str = Field(min_length=1,max_length=160)
    kind: Literal['notes','tasks','chat','git'] = 'notes'
    access: Literal['core','technical','leads'] = 'core'
    text: str = Field(min_length=1,max_length=250000)
    authorised: bool

def add_source(s, body):
    if not body.authorised:
        raise HTTPException(400,'Confirm that you are authorised to import this source')
    try:
        text = parse_source(body.name,body.text)
    except ValueError as exc:
        raise HTTPException(400,str(exc))
    text,n=redact(text)
    digest=hashlib.sha256(text.encode()).hexdigest()
    if any(x['hash']==digest and x['access']==body.access for x in s['sources']):
        raise HTTPException(409,'This source is already imported')
    if len(s['sources'])>=40:
        raise HTTPException(400,'This prototype supports up to 40 sources per workspace')
    source={'id':secrets.token_hex(8),'name':redact(body.name)[0],'kind':body.kind,'access':body.access,'text':text,
            'hash':digest,'redactions':n,'created_at':now(),'lines':len(text.splitlines())}
    s['sources'].append(source)
    return source

@app.post('/api/sources')
def import_source(body: SourceIn, request: Request):
    role=auth(request,True)
    with state() as s:
        source=add_source(s,body)
        audit(s,role,'Imported source',source['name'])
        return {'id':source['id'],'redactions':source['redactions']}

@app.post('/api/demo')
def demo(request: Request):
    role=auth(request,True)
    with state() as s:
        if s['sources']:
            raise HTTPException(409,'Demo can only be loaded into an empty workspace')
        for name,kind,access,text in DEMO:
            add_source(s,SourceIn(name=name,kind=kind,access=access,text=text,authorised=True))
        audit(s,role,'Loaded synthetic demo','5 sources; 2 planted conflicts')
    return {'ok':True}

class RepoIn(BaseModel):
    url: str = Field(max_length=300)
    access: Literal['core','technical','leads']='technical'
    authorised: bool

@app.post('/api/github')
def github(body: RepoIn, request: Request):
    role=auth(request,True)
    if not body.authorised:
        raise HTTPException(400,'Authorisation is required')
    match=re.fullmatch(r'https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?',body.url)
    if not match:
        raise HTTPException(400,'Use a public https://github.com/owner/repo URL')
    owner,repo=match.groups()
    try:
        with httpx.Client(timeout=20,follow_redirects=False,headers={'Accept':'application/vnd.github+json'}) as client:
            base=f'https://api.github.com/repos/{owner}/{repo}'
            info=client.get(base); info.raise_for_status()
            commits=client.get(base+'/commits',params={'per_page':30}); commits.raise_for_status()
            lines=[f"{c['commit']['author']['date']} commit {c['sha']} author: {c['commit']['author']['name']} | {c['commit']['message'].replace(chr(10),' ')}. Owner: {c['commit']['author']['name']}." for c in commits.json()]
            readme=client.get(base+'/readme')
            docs=[]
            if readme.status_code==200:
                docs.append((readme.json()['name'],base64.b64decode(readme.json()['content']).decode('utf-8')))
    except (httpx.HTTPError,ValueError,KeyError,UnicodeError):
        raise HTTPException(502,'GitHub import failed. Check repository visibility, connection and rate limits; use an export if needed.')
    with state() as s:
        for name,text in [('git-history.txt','\n'.join(lines)),*docs]:
            add_source(s,SourceIn(name=f'{repo}/{name}',text=text[:250000],kind='git',access=body.access,authorised=True))
        audit(s,role,'Imported public GitHub repository',f'{owner}/{repo}; latest 30 commits and README')
    return {'ok':True}

class AccessIn(BaseModel):
    access: Literal['core','technical','leads']

@app.patch('/api/sources/{source_id}')
def access(source_id: str, body: AccessIn, request: Request):
    role=auth(request,True)
    with state() as s:
        source=next((x for x in s['sources'] if x['id']==source_id),None)
        if not source: raise HTTPException(404,'Source missing')
        source['access']=body.access
        audit(s,role,'Changed source access',source_id+' → '+body.access)
    return {'ok':True}

@app.delete('/api/sources/{source_id}')
def remove_source(source_id: str, request: Request):
    role=auth(request,True)
    with state() as s:
        s['sources']=[x for x in s['sources'] if x['id']!=source_id]
        for c in s['claims']:
            if any(e['source_id']==source_id for e in c['evidence']):
                c.update(status='gap',review='pending',reason='Evidence removed. Reconstruct and review again.')
        audit(s,role,'Removed source',source_id)
    return {'ok':True}

@app.get('/api/evidence/{claim_id}')
def evidence(claim_id: str,request: Request):
    role=auth(request)
    with state() as s:
        claims=s['claims'] if role in ('reviewer','leaver') else s['versions'][-1]['claims'] if s['versions'] else []
        c=next((c for c in claims if c['id']==claim_id),None)
        if not c or not visible(c,s,role): raise HTTPException(404,'Evidence unavailable')
        audit(s,role,'Viewed evidence',claim_id)
        return [{'source':next(x['name'] for x in s['sources'] if x['id']==e['source_id']),**e} for e in c['evidence']]

@app.post('/api/reconstruct')
def run(request: Request):
    role=auth(request,True)
    with state() as s:
        if not s['sources']: raise HTTPException(400,'Import at least one source first')
        key=hashlib.sha256(json.dumps([(x['id'],x['hash']) for x in s['sources']]).encode()+cache_identity().encode()).hexdigest()
        if key in s['cache']:
            claims,mode=copy.deepcopy(s['cache'][key])
        else:
            claims,mode=reconstruct(s['sources'])
            # Retry the configured provider next time after a transient outage or missing key.
            if 'fallback' not in mode:
                s['cache'][key]=[copy.deepcopy(claims),mode]
        old={c['id']:c for c in s['claims']}
        s['claims']=[old.get(c['id'],c) for c in claims]
        s['mode']=mode
        audit(s,role,'Reconstructed project',f'{len(claims)} claims · {mode}')
        return {'count':len(claims),'mode':mode}

class ReviewIn(BaseModel):
    action: Literal['approve','reject','attest']
    text: str = Field(default='',max_length=2000)
    owner: str = Field(default='',max_length=100)

@app.patch('/api/claims/{claim_id}')
def review(claim_id: str,body: ReviewIn,request: Request):
    role=auth(request)
    if role not in ('reviewer','leaver'): raise HTTPException(403,'Reviewer or leaver required')
    with state() as s:
        c=next((x for x in s['claims'] if x['id']==claim_id),None)
        if not c or not visible(c,s,role): raise HTTPException(404,'Claim missing')
        if role=='leaver' and (body.action!='attest' or c['status']!='gap' or s['sudden_exit']):
            raise HTTPException(403,'Leaver may answer open gap questions only')
        if body.action=='approve':
            if c['status'] not in ('verified','attested'): raise HTTPException(400,'Resolve uncertainty or reject this claim before approval')
            c['review']='approved'
        elif body.action=='reject': c['review']='rejected'
        else:
            if not body.text.strip(): raise HTTPException(400,'An attestation needs an answer or correction')
            c['text']=redact(body.text.strip())[0]
            c['owner']=redact(body.owner.strip())[0] or c['owner']
            c['status']='attested'; c['review']='pending'
            c['attestation']={'by':ROLES[role][0],'at':now()}
            c['reason']='Confirmed by a named person; reviewer approval still required.'
        audit(s,role,body.action.title()+' claim',claim_id)
    return {'ok':True}

@app.post('/api/approve-verified')
def bulk(request: Request):
    role=auth(request,True)
    with state() as s:
        for c in s['claims']:
            if c['status'] in ('verified','attested') and c['review']=='pending': c['review']='approved'
        audit(s,role,'Approved supported claims')
    return {'ok':True}

@app.post('/api/publish')
def publish(request: Request):
    role=auth(request,True)
    with state() as s:
        if not s['claims']: raise HTTPException(400,'Reconstruct the project first')
        if any(c['review']=='pending' for c in s['claims']): raise HTTPException(400,'Review every claim: approve supported claims, resolve or reject uncertain ones')
        claims=[c for c in s['claims'] if c['review']=='approved']
        if not claims: raise HTTPException(400,'Approve at least one claim')
        if not all(visible(c,s,'reviewer') for c in claims): raise HTTPException(400,'Some evidence was removed; reconstruct and review again')
        version={'number':len(s['versions'])+1,'at':now(),'by':ROLES[role][0],'claims':copy.deepcopy(claims)}
        s['versions'].append(version)
        audit(s,role,'Published approved handover',f"Version {version['number']}")
        return {'number':version['number']}

class SettingsIn(BaseModel):
    sudden_exit: bool

@app.patch('/api/settings')
def settings(body: SettingsIn,request: Request):
    role=auth(request,True)
    with state() as s:
        s['sudden_exit']=body.sudden_exit
        audit(s,role,'Changed departure mode','Sudden exit' if body.sudden_exit else 'Planned exit')
    return {'ok':True}

@app.get('/api/versions/{number}')
def version(number: int,request: Request):
    role=auth(request)
    with state() as s:
        v=next((v for v in s['versions'] if v['number']==number),None)
        if not v: raise HTTPException(404,'Version missing')
        previous=s['versions'][number-2]['claims'] if number>1 else []
        before={c['id']:c for c in previous}
        view=filtered(v['claims'],s,role)
        for c in view:
            if not c.get('restricted'):
                c['change']='added' if c['id'] not in before else 'changed' if c['text']!=before[c['id']]['text'] else 'unchanged'
        return {'number':number,'claims':view,'removed_count':len([c for c in previous if c['id'] not in {x['id'] for x in v['claims']} and visible(c,s,role)])}

class AckIn(BaseModel):
    section: Literal['decisions','risks','next actions']

@app.post('/api/acknowledge')
def acknowledge(body: AckIn,request: Request):
    role=auth(request)
    with state() as s:
        if not s['versions']: raise HTTPException(400,'No published version')
        digest=hashlib.sha256(json.dumps([(x['id'],x['access']) for x in s['sources']]).encode()).hexdigest()
        a={'role':role,'by':ROLES[role][0],'section':body.section,'version':len(s['versions']),'access_hash':digest,'at':now()}
        s['acks'].append(a); audit(s,role,'Acknowledged '+body.section,f"Version {len(s['versions'])}")
    return {'ok':True}

def markdown(s,role):
    if not s['versions']: raise HTTPException(400,'Publish a handover first')
    v=s['versions'][-1]
    lines=[f"# {s['project']}", f"Approved version {v['number']} · {v['at']}", 'Access is checked at export time. Downloaded copies cannot be revoked.', '']
    for c in filtered(v['claims'],s,role):
        if c.get('restricted'): lines.append('- Restricted knowledge. Ask Kabir.'); continue
        lines.extend([f"## {c['type'].title()} · {c['status']}",c['text'],f"Owner: {c['owner']}"])
        for e in c['evidence']:
            source=next(x for x in s['sources'] if x['id']==e['source_id'])
            lines.extend([f"> {e['quote']}",f"Source: {source['name']} · {e['locator']}"])
        if c['attestation']: lines.append(f"Attested by {c['attestation']['by']} at {c['attestation']['at']}")
        lines.append('')
    return '\n'.join(lines)

@app.get('/api/export/{format}')
def export(format: str,request: Request):
    role=auth(request)
    with state() as s:
        text=markdown(s,role)
        audit(s,role,'Exported handover',format)
    if format=='md': return Response(text,media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="baton-handover.md"'})
    if format!='pdf': raise HTTPException(400,'Choose md or pdf')
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from xml.sax.saxutils import escape
    output=io.BytesIO(); styles=getSampleStyleSheet()
    story=[]
    for line in text.splitlines():
        style=styles['Heading1'] if line.startswith('# ') else styles['Heading2'] if line.startswith('## ') else styles['BodyText']
        story.extend([Paragraph(escape(line.lstrip('# ')),style),Spacer(1,7)])
    SimpleDocTemplate(output,title='Baton approved handover').build(story)
    return Response(output.getvalue(),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="baton-handover.pdf"'})

class QuestionIn(BaseModel):
    question: str = Field(min_length=3,max_length=400)

@app.post('/api/ask')
def ask(body: QuestionIn,request: Request):
    role=auth(request)
    with state() as s:
        claims=s['versions'][-1]['claims'] if s['versions'] else []
        words=set(re.findall(r'\w{4,}',body.question.lower()))
        matches=[c for c in claims if visible(c,s,role) and words.intersection(re.findall(r'\w{4,}',c['text'].lower()))]
        return {'answer':'Relevant approved claims are shown below.' if matches else 'No answer in your authorised approved handover. Ask the reviewer.', 'claims':filtered(matches[:5],s,role)}

@app.get('/api/health')
def health(): return {'status':'ok'}

if Path('dist').is_dir():
    app.mount('/assets',StaticFiles(directory='dist/assets'),name='assets')
    @app.get('/{path:path}')
    def frontend(path: str):
        if path.startswith('api/'): raise HTTPException(404,'Endpoint missing')
        return FileResponse('dist/index.html')
