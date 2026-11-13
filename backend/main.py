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
from datetime import date, datetime, timezone
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal
import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from backend.engine import DEMO, KINDS, now, parse_source, reconstruct, redact
from backend.llm import cache_identity
from backend import storage
from backend.questionnaire import prompt_for, follow_up

app = FastAPI(title='Baton API', version='0.1.0')
if os.getenv('VERCEL')=='1' and not storage.enabled():
    raise RuntimeError('Configure DATABASE_URL before deploying Baton; serverless local storage is not persistent.')
DB = Path(os.getenv('BATON_DB', 'data/baton.sqlite3'))
LOCK = threading.RLock()
ROLES = {'reviewer': ('Kabir', ['core','technical','leads']), 'successor': ('Meera', ['core','technical']),
         'coordinator': ('Riya', ['core']), 'leaver': ('Aarav', ['core','technical'])}
PRINCIPAL=ContextVar('baton_principal',default=None)

def actor_name(role):
    principal=PRINCIPAL.get()
    return principal['name'] if principal and principal['role']==role else ROLES[role][0]

def actor_id(role):
    principal=PRINCIPAL.get()
    return principal['id'] if principal and principal['role']==role else role

def initial():
    return {'project': 'Fest registration portal', 'sources': [], 'claims': [], 'versions': [], 'audit': [],
            'acks': [], 'actions': [], 'questions': [], 'mode': 'Not reconstructed', 'sudden_exit': False, 'cache': {}}

def connect():
    if storage.enabled():
        con=storage.AuthConnection()
        configure_credentials(con)
        con.commit()
        return con
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute('CREATE TABLE IF NOT EXISTS workspace (id INTEGER PRIMARY KEY, body TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS users (role TEXT PRIMARY KEY, salt TEXT, password TEXT)')
    con.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, role TEXT, expires REAL)')
    columns={r[1] for r in con.execute('PRAGMA table_info(sessions)').fetchall()}
    for name in ('account_id','name'):
        if name not in columns: con.execute('ALTER TABLE sessions ADD COLUMN '+name+' TEXT')
    con.execute('CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, username TEXT UNIQUE, role TEXT, name TEXT, salt TEXT, password TEXT, active INTEGER NOT NULL DEFAULT 1)')
    con.execute('CREATE TABLE IF NOT EXISTS invites (token TEXT PRIMARY KEY, username TEXT, role TEXT, name TEXT, expires REAL, used INTEGER NOT NULL DEFAULT 0)')
    if 'workspace_id' not in {r[1] for r in con.execute('PRAGMA table_info(invites)')}:
        con.execute('ALTER TABLE invites ADD COLUMN workspace_id INTEGER NOT NULL DEFAULT 1')
    con.execute('CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY, name TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS memberships (workspace_id INTEGER, account_id TEXT, role TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(workspace_id,account_id))')
    con.execute("INSERT OR IGNORE INTO projects VALUES (1, 'Fest registration portal')")
    # Backfill only on first upgrade. Later revocations must survive every connection.
    con.execute('CREATE TABLE IF NOT EXISTS schema_updates (name TEXT PRIMARY KEY)')
    if con.execute("INSERT OR IGNORE INTO schema_updates VALUES ('project-memberships')").rowcount:
        con.execute('INSERT OR IGNORE INTO memberships SELECT 1,id,role,active FROM accounts')
    con.execute('INSERT OR IGNORE INTO workspace VALUES (1, ?)', (json.dumps(initial()),))
    configure_credentials(con)
    con.commit()
    return con

def configure_credentials(con):
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
                con.execute('DELETE FROM sessions WHERE role=? AND account_id IS NULL', (role,))

from functools import lru_cache

@lru_cache(maxsize=16)
def password_digest(role, password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 200000).hex()

@contextmanager
def state(role=None):
    principal = PRINCIPAL.get() or {}
    workspace_id = principal.get('workspace_id', 1)
    if storage.enabled():
        try:
            with storage.remote_state(initial,role,actor_id(role),actor_name(role),workspace_id) as data:
                yield data
        except PermissionError as error:
            raise HTTPException(404,'Project unavailable') from error
        return
    with LOCK:
        con = connect()
        try:
            con.execute('BEGIN IMMEDIATE')
            if principal.get('account_id') and not con.execute(
                'SELECT 1 FROM memberships WHERE workspace_id=? AND account_id=? AND role=? AND active',
                (workspace_id,principal['account_id'],role)
            ).fetchone():
                raise HTTPException(404,'Project unavailable')
            row = con.execute('SELECT body FROM workspace WHERE id=?', (workspace_id,)).fetchone()
            if row is None:
                raise HTTPException(404, 'Project unavailable')
            data = json.loads(row[0])
            yield data
            con.execute('UPDATE workspace SET body=? WHERE id=?', (json.dumps(data), workspace_id))
            con.commit()
        finally:
            con.close()

def audit(s, role, action, detail=''):
    s['audit'].append({'at': now(), 'actor': actor_name(role), 'action': action, 'detail': detail})

def project_memberships(con, account_id):
    return con.execute(
        'SELECT p.id,p.name,m.role FROM memberships m JOIN projects p ON p.id=m.workspace_id '
        'WHERE m.account_id=? AND m.active ORDER BY p.id', (account_id,)
    ).fetchall()


def auth(request, reviewer=False, identity_only=False):
    token = request.cookies.get('baton_session', '')
    with LOCK:
        con = connect()
        row = con.execute('SELECT role,account_id,name FROM sessions WHERE token=? AND expires>?', (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
        try:
            if row and row[1]:
                account=con.execute('SELECT name FROM accounts WHERE id=?',(row[1],)).fetchone()
                projects=project_memberships(con,row[1]) if account else []
                row=(row[0],row[1],account[0]) if projects else None
            elif row:
                projects=[(1, 'Fest registration portal', row[0])]
        finally:
            con.close()
    if not row:
        raise HTTPException(401, 'Sign in to continue')
    requested = request.headers.get('x-baton-project')
    if requested is None and request.url.path.startswith('/api/export/'):
        requested = request.query_params.get('project')
    project = projects[0] if identity_only or requested is None else next(
        (item for item in projects if str(item[0]) == requested), None
    )
    if project is None:
        raise HTTPException(404, 'Project unavailable')
    role = project[2]
    PRINCIPAL.set({'role':role,'id':row[1] or row[0],'name':row[2] or ROLES[row[0]][0],
                   'account_id':row[1],'workspace_id':project[0],'projects':projects})
    if reviewer and role != 'reviewer':
        raise HTTPException(403, 'Reviewer access required')
    if request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('x-baton-request') != '1':
        raise HTTPException(403, 'Missing request protection header')
    return role


@app.get('/api/projects')
def list_projects(request: Request):
    auth(request, identity_only=True)
    principal = PRINCIPAL.get()
    return {'can_create': bool(principal['account_id']),
            'projects': [{'id':p[0],'name':p[1],'role':p[2]} for p in principal['projects']]}


class ProjectIn(BaseModel):
    name: str = Field(min_length=2,max_length=100)


@app.post('/api/projects', status_code=201)
def create_project(body: ProjectIn, request: Request):
    auth(request, identity_only=True)
    account_id = PRINCIPAL.get()['account_id']
    if not account_id:
        raise HTTPException(403, 'Use a named account to create a project')
    name = redact(body.name.strip())[0]
    if len(name) < 2:
        raise HTTPException(400, 'Enter a project name')
    data = {**initial(), 'project':name}
    with LOCK:
        con = connect()
        try:
            workspace_id = None
            for _ in range(3):
                candidate = secrets.randbelow(2147483645) + 2
                if con.execute('INSERT INTO projects VALUES (?,?) ON CONFLICT(id) DO NOTHING RETURNING id',
                               (candidate,name)).fetchone():
                    workspace_id = candidate
                    break
            if workspace_id is None:
                raise HTTPException(503, 'Could not allocate a project. Try again.')
            con.execute('INSERT INTO memberships VALUES (?,?,?,?)', (workspace_id,account_id,'reviewer',True))
            if storage.enabled():
                con.create_workspace(workspace_id, data)
            else:
                con.execute('INSERT INTO workspace VALUES (?,?)', (workspace_id,json.dumps(data)))
            con.commit()
        finally:
            con.close()
    return {'id':workspace_id,'name':name,'role':'reviewer'}

@app.middleware('http')
async def guard(request, call_next):
    try:size=int(request.headers.get('content-length','0') or 0)
    except ValueError:return Response('Invalid content length',status_code=400)
    if size > 1200000:
        return Response('Request too large', status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Cache-Control'] = 'no-store' if request.url.path.startswith('/api') else 'no-cache'
    return response

class Login(BaseModel):
    role: Literal['reviewer','successor','coordinator','leaver']='reviewer'
    username: str = Field(default='',max_length=120)
    password: str = Field(max_length=200)

FAILURES = {}

@app.get('/api/config')
def public_config():
    demo=os.getenv('BATON_DEMO','0')=='1'
    return {'demo':demo,'roles':[role for role in ROLES if demo or os.getenv('BATON_'+role.upper()+'_PASSWORD')]}

@app.post('/api/login')
def login(body: Login, request: Request, response: Response):
    address = request.client.host if request.client else 'unknown'
    with LOCK:
        failures = [t for t in FAILURES.get(address, []) if t > time.time()-60]
        if len(failures) >= 10:
            raise HTTPException(429, 'Too many attempts; try again in a minute')
        con = connect()
        account=con.execute('SELECT id,role,name,salt,password,active FROM accounts WHERE username=?',(body.username.casefold(),)).fetchone() if body.username else None
        projects = project_memberships(con,account[0]) if account else []
        role=projects[0][2] if projects else body.role
        name=account[2] if account else ROLES[role][0]
        row=(account[3],account[4]) if projects else None if body.username else con.execute('SELECT salt,password FROM users WHERE role=?', (body.role,)).fetchone()
        if not body.username and os.getenv('BATON_DEMO','0')!='1' and not os.getenv('BATON_'+body.role.upper()+'_PASSWORD'):
            row=None
        digest = hashlib.pbkdf2_hmac('sha256', body.password.encode(), (row[0] if row else 'dummy').encode(), 200000).hex()
        if not row or not hmac.compare_digest(digest, row[1]):
            con.close()
            FAILURES[address] = failures + [time.time()]
            raise HTTPException(401, 'Incorrect password or account is not configured')
        token = secrets.token_urlsafe(32)
        con.execute('INSERT INTO sessions(token,role,expires,account_id,name) VALUES (?,?,?,?,?)', (hashlib.sha256(token.encode()).hexdigest(),role,time.time()+28800,account[0] if account else None,name))
        con.commit()
        con.close()
    response.set_cookie('baton_session',token,httponly=True,samesite='strict',secure=os.getenv('BATON_SECURE_COOKIE')=='1',max_age=28800)
    return {'role':role,'name':name}

@app.post('/api/logout')
def logout(request: Request, response: Response):
    auth(request, identity_only=True)
    with LOCK:
        con=connect()
        con.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(request.cookies.get('baton_session','').encode()).hexdigest(),))
        con.commit(); con.close()
    response.delete_cookie('baton_session')
    return {'ok': True}

class InviteIn(BaseModel):
    username: str = Field(min_length=3,max_length=120,pattern=r'^[A-Za-z0-9_.@+\-]+$')
    name: str = Field(min_length=2,max_length=80)
    role: Literal['reviewer','successor','coordinator','leaver']

@app.post('/api/invites')
def invite(body: InviteIn,request: Request):
    role=auth(request,True)
    workspace_id = PRINCIPAL.get()['workspace_id']
    with LOCK:
        con=connect()
        try:
            if con.execute('SELECT 1 FROM accounts a JOIN memberships m ON a.id=m.account_id '
                           'WHERE a.username=? AND m.workspace_id=? AND m.active',
                           (body.username.casefold(),workspace_id)).fetchone():
                raise HTTPException(409,'That username already has access to this project')
            code=secrets.token_urlsafe(32)
            con.execute('INSERT INTO invites(token,username,role,name,expires,used,workspace_id) VALUES (?,?,?,?,?,0,?)',
                        (hashlib.sha256(code.encode()).hexdigest(),body.username.casefold(),body.role,redact(body.name)[0],time.time()+86400,workspace_id))
            con.commit()
        finally:con.close()
    with state(role) as s:audit(s,role,'Created one-time invitation',body.username.casefold()+' · '+body.role)
    return {'code':code,'username':body.username.casefold(),'expires_in_hours':24}

class RegisterIn(BaseModel):
    code: str = Field(min_length=20,max_length=100)
    password: str = Field(min_length=12,max_length=200)

@app.post('/api/register')
def register(body: RegisterIn,request: Request):
    if request.headers.get('x-baton-request')!='1':raise HTTPException(403,'Missing request protection header')
    with LOCK:
        con=connect()
        try:
            if not storage.enabled():con.execute('BEGIN IMMEDIATE')
            row=con.execute('SELECT username,role,name,expires,used,workspace_id FROM invites WHERE token=?'+(' FOR UPDATE' if storage.enabled() else ''),
                            (hashlib.sha256(body.code.encode()).hexdigest(),)).fetchone()
            if not row or row[4] or row[3]<time.time():raise HTTPException(400,'Invitation is invalid, expired or already used')
            account=con.execute('SELECT id,name,salt,password FROM accounts WHERE username=?'+(' FOR UPDATE' if storage.enabled() else ''),(row[0],)).fetchone()
            if account:
                account_id,name,salt,password=account
                if not hmac.compare_digest(password_digest('account',body.password,salt),password):
                    raise HTTPException(401,'Use the existing password for this username')
                if con.execute('SELECT 1 FROM memberships WHERE workspace_id=? AND account_id=? AND active',
                               (row[5],account_id)).fetchone():
                    raise HTTPException(409,'This account already has access to the project')
            else:
                account_id,name,salt=secrets.token_hex(16),row[2],secrets.token_hex(24)
                digest=password_digest('account',body.password,salt)
                inserted=con.execute('INSERT INTO accounts(id,username,role,name,salt,password) VALUES (?,?,?,?,?,?) '
                                     'ON CONFLICT(username) DO NOTHING RETURNING id',
                                     (account_id,row[0],row[1],name,salt,digest)).fetchone()
                if not inserted:
                    raise HTTPException(409,'The username was registered concurrently. Retry with its existing password.')
            con.execute('INSERT INTO memberships VALUES (?,?,?,?) ON CONFLICT(workspace_id,account_id) '
                        'DO UPDATE SET role=excluded.role,active=excluded.active',(row[5],account_id,row[1],True))
            con.execute('UPDATE invites SET used=1 WHERE token=?',(hashlib.sha256(body.code.encode()).hexdigest(),))
            con.commit()
        finally:con.close()
    return {'username':row[0],'name':name,'role':row[1],'project_id':row[5]}

@app.get('/api/members')
def members(request: Request):
    auth(request,True)
    with LOCK:
        con=connect()
        rows=con.execute('SELECT a.id,a.username,m.role,a.name,m.active FROM accounts a JOIN memberships m ON a.id=m.account_id '
                         'WHERE m.workspace_id=? ORDER BY a.username',(PRINCIPAL.get()['workspace_id'],)).fetchall()
        con.close()
    return [{'id':r[0],'username':r[1],'role':r[2],'name':r[3],'active':bool(r[4])} for r in rows]

class MemberUpdate(BaseModel):
    active: bool

@app.patch('/api/members/{member_id}')
def member_access(member_id: str,body: MemberUpdate,request: Request):
    role=auth(request,True)
    if member_id==actor_id(role):raise HTTPException(400,'You cannot revoke your own access')
    with LOCK:
        con=connect()
        try:
            updated=con.execute('UPDATE memberships SET active=? WHERE workspace_id=? AND account_id=? RETURNING account_id',
                                (body.active,PRINCIPAL.get()['workspace_id'],member_id)).fetchone()
            if not updated:raise HTTPException(404,'Member not found')
            if not project_memberships(con,member_id):
                con.execute('DELETE FROM sessions WHERE account_id=?',(member_id,))
            con.commit()
        finally:con.close()
    with state(role) as s:audit(s,role,'Changed member access',member_id+' · '+str(body.active))
    return {'ok':True}

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
            c.pop('question_assignee_id', None)
            # Never reveal identifiers of conflicting restricted records.
            c['conflicts']=[x for x in c['conflicts'] if any(p['id']==x and visible(p,s,role) for p in claims)]
            result.append(c)
    return result

def receipt_hash(s):
    return hashlib.sha256(json.dumps({
        'sources': sorted((x['id'],x['access']) for x in s['sources']),
        'actions': sorted((x['id'],x.get('updated_at','')) for x in s.get('actions',[]))
    },sort_keys=True).encode()).hexdigest()

def published_claim(s,claim_id):
    return next((c for c in (s['versions'][-1]['claims'] if s['versions'] else []) if c['id']==claim_id),None)

def accessible_actions(s,role):
    result=[]
    for action in s.get('actions',[]):
        version=next((v for v in s['versions'] if v['number']==action['version']),None)
        claim=next((c for c in version['claims'] if c['id']==action['claim_id']),None) if version else None
        if claim and visible(claim,s,role):
            result.append(action)
    return result


def visible_questions(s, role):
    claims = {c['id']:c for c in s['claims'] if visible(c,s,role)}
    result = []
    for question in s.get('questions', []):
        claim = claims.get(question['claim_id'])
        if not claim:
            continue
        assignee_id = question.get('assignee_id')
        allowed = role == 'reviewer' or (
            assignee_id == actor_id(role) if assignee_id else role == 'leaver' and question['assignee'] == 'leaver'
        )
        if allowed and not (s['sudden_exit'] and role == 'leaver'):
            answers = question.get('answers', [])
            if role != 'reviewer':
                answers = [answer for answer in answers if answer['user_id'] == actor_id(role)]
            open_gap = claim['status'] == 'gap' and claim['review'] == 'pending'
            latest = answers[-1] if answers else None
            result.append({**question, 'prompt':question.get('prompt') or claim['text'],
                           'answers':answers, 'claim_status':claim['status'], 'claim_review':claim['review'],
                           'can_answer':open_gap and (not assignee_id or assignee_id == actor_id(role)),
                           'can_confirm':bool(role == 'reviewer' and open_gap and latest and not latest['follow_up']
                                              and (not assignee_id or latest['user_id'] == assignee_id))})
    return result


def personal_catch_up(s, role):
    if not s['versions']:
        return {'latest_version':None,'baseline':None,'responsibilities':[],'risks':[],'actions':[]}
    versions = {v['number']:v for v in s['versions']}
    latest = s['versions'][-1]
    receipt = max(
        (a for a in s['acks'] if a.get('user_id',a['role']) == actor_id(role) and a['version'] in versions),
        key=lambda a:(a['version'],a['at']), default=None
    )
    previous = versions[receipt['version']]['claims'] if receipt else []
    before = {c['id']:c for c in previous if visible(c,s,role)}
    responsibilities, risks = [], []
    for claim in latest['claims']:
        if not visible(claim,s,role):
            continue
        old = before.get(claim['id'])
        entry = {key:claim[key] for key in ('id','text','owner')}
        if old and old['owner'] != claim['owner']:
            responsibilities.append({**entry,'previous_owner':old['owner']})
        if claim.get('type') == 'risk' and (not old or old.get('type') != 'risk'):
            risks.append(entry)
    today = datetime.now(timezone.utc).date().isoformat()
    actions = []
    for action in accessible_actions(s,role):
        if action['status'] == 'done':
            continue
        overdue = bool(action.get('due') and action['due'] < today)
        if overdue or action['status'] == 'blocked':
            actions.append({**action,'overdue':overdue})
    actions.sort(key=lambda a:(a['due'] or '9999-12-31',a['id']))
    return {'latest_version':latest['number'],
            'baseline':{key:receipt[key] for key in ('version','at','section')} if receipt else None,
            'responsibilities':responsibilities,'risks':risks,'actions':actions}

@app.get('/api/workspace')
def workspace(request: Request):
    role=auth(request)
    with state(role) as s:
        claims = s['claims'] if role in ('reviewer','leaver') else s['versions'][-1]['claims'] if s['versions'] else []
        digest=receipt_hash(s)
        result={'project':s['project'],'user':{'role':role,'name':actor_name(role),'id':actor_id(role)},'claims':filtered(claims,s,role),
                'sources':[{k:v for k,v in x.items() if k!='text'} for x in s['sources'] if x['access'] in ROLES[role][1] and (role in ('reviewer','leaver') or s['versions'])],
                'versions':[{'number':v['number'],'at':v['at'],'by':v['by'],'count':len(v['claims'])} for v in s['versions']],
                'audit':s['audit'][-100:][::-1] if role=='reviewer' else [],
                'acks':[a for a in s['acks'] if (a.get('user_id',a['role'])==actor_id(role) or role=='reviewer') and a.get('access_hash')==digest], 'mode':s['mode'] if role=='reviewer' else 'Approved handover',
                'sudden_exit':s['sudden_exit'],'demo':os.getenv('BATON_DEMO','0')=='1',
                'storage':'Supabase Postgres + RLS' if storage.enabled() else 'Local SQLite',
                'workspace_id':PRINCIPAL.get()['workspace_id'],
                'projects':[{'id':p[0],'name':p[1],'role':p[2]} for p in PRINCIPAL.get()['projects']],
                'can_create_project':bool(PRINCIPAL.get()['account_id']),
                'catch_up':personal_catch_up(s,role),
                'actions':accessible_actions(s,role),
                'approved_claims':filtered(s['versions'][-1]['claims'],s,role) if s['versions'] else [],
                'questions':visible_questions(s,role),
                'receipt_stale':any(a.get('user_id',a['role'])==actor_id(role) and a['version']==len(s['versions']) and a.get('access_hash')!=digest for a in s['acks'])}
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
    with state(role) as s:
        source=add_source(s,body)
        audit(s,role,'Imported source',source['name'])
        return {'id':source['id'],'redactions':source['redactions']}

@app.post('/api/demo')
def demo(request: Request):
    role=auth(request,True)
    with state(role) as s:
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
    with state(role) as s:
        for name,text in [('git-history.txt','\n'.join(lines)),*docs]:
            add_source(s,SourceIn(name=f'{repo}/{name}',text=text[:250000],kind='git',access=body.access,authorised=True))
        audit(s,role,'Imported public GitHub repository',f'{owner}/{repo}; latest 30 commits and README')
    return {'ok':True}

class AccessIn(BaseModel):
    access: Literal['core','technical','leads']

@app.patch('/api/sources/{source_id}')
def access(source_id: str, body: AccessIn, request: Request):
    role=auth(request,True)
    with state(role) as s:
        source=next((x for x in s['sources'] if x['id']==source_id),None)
        if not source: raise HTTPException(404,'Source missing')
        source['access']=body.access
        audit(s,role,'Changed source access',source_id+' → '+body.access)
    return {'ok':True}

@app.delete('/api/sources/{source_id}')
def remove_source(source_id: str, request: Request):
    role=auth(request,True)
    with state(role) as s:
        s['sources']=[x for x in s['sources'] if x['id']!=source_id]
        for c in s['claims']:
            if any(e['source_id']==source_id for e in c['evidence']):
                c.update(status='gap',review='pending',reason='Evidence removed. Reconstruct and review again.')
        audit(s,role,'Removed source',source_id)
    return {'ok':True}

@app.get('/api/evidence/{claim_id}')
def evidence(claim_id: str,request: Request,version: int | None = None):
    role=auth(request)
    with state(role) as s:
        if version is not None:
            snapshot=next((v for v in s['versions'] if v['number']==version),None)
            claims=snapshot['claims'] if snapshot else []
        else:
            claims=s['claims'] if role in ('reviewer','leaver') else s['versions'][-1]['claims'] if s['versions'] else []
        c=next((c for c in claims if c['id']==claim_id),None)
        if not c or not visible(c,s,role): raise HTTPException(404,'Evidence unavailable')
        audit(s,role,'Viewed evidence',claim_id)
        return [{'source':next(x['name'] for x in s['sources'] if x['id']==e['source_id']),**e} for e in c['evidence']]

@app.post('/api/reconstruct')
def run(request: Request):
    role=auth(request,True)
    with state(role) as s:
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
    with state(role) as s:
        c=next((x for x in s['claims'] if x['id']==claim_id),None)
        if not c or not visible(c,s,role): raise HTTPException(404,'Claim missing')
        if role=='leaver' and (body.action!='attest' or c['status']!='gap' or s['sudden_exit']):
            raise HTTPException(403,'Leaver may answer open gap questions only')
        if role == 'leaver' and any(q['claim_id']==claim_id and (q.get('assignee_id') or q['assignee'] != 'leaver')
                                   for q in s['questions']):
            raise HTTPException(403, 'Use the assigned questionnaire to answer this gap')
        if body.action=='approve':
            if c['status'] not in ('verified','attested'): raise HTTPException(400,'Resolve uncertainty or reject this claim before approval')
            c['review']='approved'
        elif body.action=='reject': c['review']='rejected'
        else:
            if not body.text.strip(): raise HTTPException(400,'An attestation needs an answer or correction')
            c['text']=redact(body.text.strip())[0]
            c['owner']=redact(body.owner.strip())[0] or c['owner']
            c['status']='attested'; c['review']='pending'
            c['attestation']={'by':actor_name(role),'at':now()}
            c['reason']='Confirmed by a named person; reviewer approval still required.'
            for question in s.get('questions',[]):
                if question['claim_id']==claim_id:
                    question.update(answered_at=now(),answered_by=actor_name(role))
        audit(s,role,body.action.title()+' claim',claim_id)
    return {'ok':True}

@app.post('/api/approve-verified')
def bulk(request: Request):
    role=auth(request,True)
    with state(role) as s:
        for c in s['claims']:
            if c['status'] in ('verified','attested') and c['review']=='pending': c['review']='approved'
        audit(s,role,'Approved supported claims')
    return {'ok':True}

@app.post('/api/publish')
def publish(request: Request):
    role=auth(request,True)
    with state(role) as s:
        if not s['claims']: raise HTTPException(400,'Reconstruct the project first')
        if any(c['review']=='pending' for c in s['claims']): raise HTTPException(400,'Review every claim: approve supported claims, resolve or reject uncertain ones')
        claims=[c for c in s['claims'] if c['review']=='approved']
        if not claims: raise HTTPException(400,'Approve at least one claim')
        if not all(visible(c,s,'reviewer') for c in claims): raise HTTPException(400,'Some evidence was removed; reconstruct and review again')
        snapshot = copy.deepcopy(claims)
        for item in snapshot:
            item.pop('question_assignee_id', None)
        version={'number':len(s['versions'])+1,'at':now(),'by':actor_name(role),'claims':snapshot}
        s['versions'].append(version)
        audit(s,role,'Published approved handover',f"Version {version['number']}")
        return {'number':version['number']}

class SettingsIn(BaseModel):
    sudden_exit: bool

@app.patch('/api/settings')
def settings(body: SettingsIn,request: Request):
    role=auth(request,True)
    with state(role) as s:
        s['sudden_exit']=body.sudden_exit
        audit(s,role,'Changed departure mode','Sudden exit' if body.sudden_exit else 'Planned exit')
    return {'ok':True}

@app.get('/api/versions/{number}')
def version(number: int,request: Request):
    role=auth(request)
    with state(role) as s:
        v=next((v for v in s['versions'] if v['number']==number),None)
        if not v: raise HTTPException(404,'Version missing')
        previous=s['versions'][number-2]['claims'] if number>1 else []
        before={c['id']:c for c in previous}
        view=filtered(v['claims'],s,role)
        for c in view:
            if not c.get('restricted'):
                old=before.get(c['id'])
                fields=['text','owner','status','type','attestation']
                changed=[field for field in fields if old and c.get(field)!=old.get(field)]
                c['change']='added' if old is None else 'changed' if changed else 'unchanged'
                c['changed_fields']=changed
                c['previous']={field:old.get(field) for field in changed} if old and visible(old,s,role) else {}
        removed=[c for c in previous if c['id'] not in {x['id'] for x in v['claims']} and visible(c,s,role)]
        return {'number':number,'claims':view,'removed_count':len(removed),'removed':filtered(removed,s,role)}

class AckIn(BaseModel):
    section: Literal['decisions','risks','next actions']

@app.post('/api/acknowledge')
def acknowledge(body: AckIn,request: Request):
    role=auth(request)
    with state(role) as s:
        if not s['versions']: raise HTTPException(400,'No published version')
        digest=receipt_hash(s)
        a={'role':role,'user_id':actor_id(role),'by':actor_name(role),'section':body.section,'version':len(s['versions']),'access_hash':digest,'at':now()}
        s['acks'].append(a); audit(s,role,'Acknowledged '+body.section,f"Version {len(s['versions'])}")
    return {'ok':True}

class ActionIn(BaseModel):
    claim_id: str
    title: str = Field(min_length=3,max_length=500)
    owner: str = Field(min_length=1,max_length=100)
    phase: Literal['Day 1','Week 1','Day 30']='Day 1'
    due: date | None = None
    status: Literal['todo','in_progress','blocked','done']='todo'

class ActionUpdate(BaseModel):
    title: str = Field(min_length=3,max_length=500)
    owner: str = Field(min_length=1,max_length=100)
    phase: Literal['Day 1','Week 1','Day 30']
    due: date | None = None
    status: Literal['todo','in_progress','blocked','done']

@app.post('/api/actions')
def create_action(body: ActionIn,request: Request):
    role=auth(request,True)
    with state(role) as s:
        claim=published_claim(s,body.claim_id)
        if not claim or not visible(claim,s,role): raise HTTPException(400,'Choose an accessible claim from the latest approved handover')
        item={**body.model_dump(mode='json'),'id':secrets.token_hex(8),'version':len(s['versions']),
              'title':redact(body.title)[0],'owner':redact(body.owner)[0],'created_at':now(),'updated_at':now()}
        s.setdefault('actions',[]).append(item)
        audit(s,role,'Created continuation action',item['id'])
        return item

@app.patch('/api/actions/{action_id}')
def update_action(action_id: str,body: ActionUpdate,request: Request):
    role=auth(request)
    with state(role) as s:
        item=next((a for a in accessible_actions(s,role) if a['id']==action_id),None)
        if not item: raise HTTPException(404,'Action unavailable')
        if role!='reviewer' and (role=='leaver' or item['owner'].casefold()!=actor_name(role).casefold()):
            raise HTTPException(403,'Only the reviewer or assigned owner can update this action')
        if role!='reviewer' and body.owner!=item['owner']: raise HTTPException(403,'Ask the reviewer to reassign ownership')
        item.update(body.model_dump(mode='json'),title=redact(body.title)[0],owner=redact(body.owner)[0],updated_at=now())
        audit(s,role,'Updated continuation action',action_id)
        return item

class QuestionAssignment(BaseModel):
    claim_id: str
    assignee: Literal['leaver','reviewer']
    priority: Literal['high','medium','low']='medium'
    due: date | None = None
    assignee_id: str | None = Field(default=None,max_length=64)


@app.post('/api/questions/generate')
def generate_questions(request: Request):
    role = auth(request, True)
    with state(role) as s:
        existing = {q['claim_id'] for q in s['questions']}
        generated = []
        for claim in s['claims']:
            if claim['id'] in existing or claim['status'] != 'gap' or claim['review'] != 'pending' or not visible(claim,s,role):
                continue
            prompt, hint = prompt_for(claim)
            question = {'id':secrets.token_hex(8),'claim_id':claim['id'],'assignee':'reviewer',
                        'priority':'medium','due':None,'prompt':prompt,'answer_hint':hint,'updated_at':now()}
            s['questions'].append(question)
            generated.append(question)
        if generated:
            audit(s,role,'Generated gap questionnaire',str(len(generated)))
    return {'created':len(generated)}

@app.post('/api/questions/assign')
def assign_question(body: QuestionAssignment,request: Request):
    role=auth(request,True)
    member = None
    if body.assignee_id:
        con = connect()
        try:
            member = con.execute('SELECT a.name,m.role FROM memberships m JOIN accounts a ON a.id=m.account_id '
                                 'WHERE m.workspace_id=? AND m.account_id=? AND m.active',
                                 (PRINCIPAL.get()['workspace_id'],body.assignee_id)).fetchone()
        finally:
            con.close()
        if not member:
            raise HTTPException(404,'Active project member unavailable')
    with state(role) as s:
        claim=next((c for c in s['claims'] if c['id']==body.claim_id and visible(c,s,role)),None)
        if not claim or claim.get('status')!='gap' or claim['review']!='pending':
            raise HTTPException(400,'Choose an unresolved gap question')
        if member and (not visible(claim,s,member[1]) or (s['sudden_exit'] and member[1]=='leaver')):
            raise HTTPException(400,'Choose a teammate who can access every supporting source and is available to answer')
        assignee='reviewer' if s['sudden_exit'] else body.assignee
        item=next((q for q in s.setdefault('questions',[]) if q['claim_id']==body.claim_id),None)
        if item is None:
            item={'id':secrets.token_hex(8),'claim_id':body.claim_id}
            s['questions'].append(item)
        prompt, hint = prompt_for(claim)
        item.update(assignee=assignee,assignee_id=body.assignee_id,assignee_name=member[0] if member else None,
                    prompt=prompt,answer_hint=hint,priority=body.priority,
                    due=body.due.isoformat() if body.due else None,updated_at=now())
        if member:
            claim['question_assignee_id'] = body.assignee_id
        else:
            claim.pop('question_assignee_id', None)
        audit(s,role,'Assigned gap question',body.claim_id+' → '+assignee)
        return item


def question_context(s, role, question_id):
    if not any(q['id']==question_id for q in visible_questions(s,role)):
        raise HTTPException(404,'Question unavailable')
    question = next(q for q in s['questions'] if q['id']==question_id)
    claim = next(c for c in s['claims'] if c['id']==question['claim_id'])
    return question, claim


@app.get('/api/questions/{question_id}/evidence')
def question_evidence(question_id: str, request: Request):
    role = auth(request)
    with state(role) as s:
        _, claim = question_context(s,role,question_id)
        sources = {source['id']:source['name'] for source in s['sources']}
        return [{**entry,'source':sources[entry['source_id']]} for entry in claim['evidence']]


class GapAnswer(BaseModel):
    text: str = Field(min_length=1,max_length=2000)
    uncertain: bool = False


@app.post('/api/questions/{question_id}/answer')
def answer_question(question_id: str, body: GapAnswer, request: Request):
    role = auth(request)
    with state(role) as s:
        question, claim = question_context(s,role,question_id)
        if claim['status'] != 'gap' or claim['review'] != 'pending':
            raise HTTPException(409,'This gap already has a review decision')
        if question.get('assignee_id') and question['assignee_id'] != actor_id(role):
            raise HTTPException(403,'Only the assigned teammate can answer this question')
        text = redact(body.text.strip())[0]
        if not text:
            raise HTTPException(400,'Enter an answer')
        answer = {'text':text,'user_id':actor_id(role),'by':actor_name(role),'at':now(),
                  'follow_up':follow_up(claim,text,body.uncertain)}
        question['answers'] = [*question.get('answers', [])[-19:],answer]
        audit(s,role,'Answered gap questionnaire',question_id)
        return answer


@app.post('/api/questions/{question_id}/confirm')
def confirm_answer(question_id: str, request: Request):
    role = auth(request,True)
    with state(role) as s:
        question, claim = question_context(s,role,question_id)
        answers = question.get('answers', [])
        latest = answers[-1] if answers else None
        if (claim['status'] != 'gap' or claim['review'] != 'pending' or not latest or latest['follow_up']
                or (question.get('assignee_id') and latest['user_id'] != question['assignee_id'])):
            raise HTTPException(409,'Get a complete answer from the current assignee before confirming')
        claim.update(text=latest['text'],status='attested',review='pending',
                     reason='A reviewer confirmed a named questionnaire answer. Approval is still required.',
                     attestation={'by':latest['by'],'at':latest['at'],'confirmed_by':actor_name(role),'confirmed_at':now()})
        question.update(answered_at=latest['at'],answered_by=latest['by'])
        audit(s,role,'Confirmed questionnaire answer',question_id)
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
    actions=accessible_actions(s,role)
    if actions:
        lines.extend(['## Continuation actions','Current human-owned actions, filtered by current evidence access.',''])
        for action in sorted(actions,key=lambda a:({'Day 1':0,'Week 1':1,'Day 30':2}[a['phase']],a.get('due') or '9999')):
            lines.extend([f"### {action['phase']}: {action['title']}",f"Owner: {action['owner']} | Status: {action['status']} | Due: {action.get('due') or 'Not set'}",f"Supporting approved claim: {action['claim_id']} (version {action['version']})"])
            snapshot=next(v for v in s['versions'] if v['number']==action['version'])
            claim=next(c for c in snapshot['claims'] if c['id']==action['claim_id'])
            for evidence in claim['evidence']:
                source=next(x for x in s['sources'] if x['id']==evidence['source_id'])
                lines.extend([f"> {evidence['quote']}",f"Source: {source['name']} | {evidence['locator']}"])
            lines.append('')
    return '\n'.join(lines)

@app.get('/api/export/{format}')
def export(format: str,request: Request):
    role=auth(request)
    with state(role) as s:
        text=markdown(s,role)
        audit(s,role,'Exported handover',format)
    if format=='md': return Response(text,media_type='text/markdown',headers={'Content-Disposition':'attachment; filename="baton-handover.md"'})
    if format!='pdf': raise HTTPException(400,'Choose md or pdf')
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from xml.sax.saxutils import escape
    output=io.BytesIO(); styles=getSampleStyleSheet()
    styles.add(ParagraphStyle('Receipt',parent=styles['BodyText'],leftIndent=12,fontSize=9,leading=13,textColor=colors.HexColor('#52634c')))
    styles.add(ParagraphStyle('Locator',parent=styles['BodyText'],fontSize=8,leading=12,textColor=colors.HexColor('#6b7564')))
    story=[]; block=[]
    for line in text.splitlines():
        if line.startswith('#') and block:
            story.append(KeepTogether(block));block=[]
        if not line.strip():continue
        style=styles['Heading1'] if line.startswith('# ') else styles['Heading2'] if line.startswith('## ') else styles['Heading3'] if line.startswith('### ') else styles['Receipt'] if line.startswith('> ') else styles['Locator'] if line.startswith('Source:') else styles['BodyText']
        content=line.lstrip('# ') if line.startswith('#') else line[2:] if line.startswith('> ') else line
        block.extend([Paragraph(escape(content),style),Spacer(1,7)])
    if block:story.append(KeepTogether(block))
    def footer(canvas,doc):
        canvas.saveState();canvas.setFillColor(colors.HexColor('#7c857d'));canvas.setFont('Helvetica',8)
        canvas.drawString(72,35,'Baton | Evidence-linked approved handover')
        canvas.drawRightString(doc.pagesize[0]-72,35,'Page '+str(doc.page));canvas.restoreState()
    SimpleDocTemplate(output,title='Baton approved handover').build(story,onFirstPage=footer,onLaterPages=footer)
    return Response(output.getvalue(),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="baton-handover.pdf"'})

class QuestionIn(BaseModel):
    question: str = Field(min_length=3,max_length=400)

@app.post('/api/ask')
def ask(body: QuestionIn,request: Request):
    role=auth(request)
    with state(role) as s:
        claims=s['versions'][-1]['claims'] if s['versions'] else []
        words=set(re.findall(r'\w{4,}',body.question.lower()))
        matches=[c for c in claims if visible(c,s,role) and words.intersection(re.findall(r'\w{4,}',c['text'].lower()))]
        return {'answer':'Relevant approved claims are shown below.' if matches else 'No answer in your authorised approved handover. Ask the reviewer.', 'claims':filtered(matches[:5],s,role)}

@app.get('/api/health')
def health():
    if storage.enabled():
        try:
            with storage.open_connection() as con:con.execute('select 1')
        except Exception:
            return Response('{"status":"database unavailable"}',media_type='application/json',status_code=503)
    return {'status':'ok'}

if Path('dist').is_dir():
    app.mount('/assets',StaticFiles(directory='dist/assets'),name='assets')
    @app.get('/{path:path}')
    def frontend(path: str):
        if path.startswith('api/'): raise HTTPException(404,'Endpoint missing')
        return FileResponse('dist/index.html')
