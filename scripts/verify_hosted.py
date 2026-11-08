"""Synthetic-only release probe. Temporary named accounts are revoked before exit."""
import hashlib
import os
from pathlib import Path
import secrets
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values
import httpx
from backend.engine import DEMO,parse_source,redact

BASE='https://baton-ruddy.vercel.app'
values=dotenv_values('.env')
admin=httpx.Client(base_url=BASE,headers={'X-Baton-Request':'1'},timeout=90)
temporary=[]
def call(client,method,path,body=None):
    response=client.request(method,path,json=body)
    if response.status_code>=400:raise RuntimeError(path+' failed: HTTP '+str(response.status_code))
    return response

try:
    assert call(admin,'GET','/api/health').json()['status']=='ok'
    call(admin,'POST','/api/login',{'role':'reviewer','password':values['BATON_REVIEWER_PASSWORD']})
    ws=call(admin,'GET','/api/workspace').json()
    expected={hashlib.sha256(redact(parse_source(name,text))[0].encode()).hexdigest() for name,_,_,text in DEMO}
    if {s['hash'] for s in ws['sources']}!=expected:raise RuntimeError('Non-fixture source detected; no mutation performed')
    if ws['versions']:raise RuntimeError('Snapshot already exists; use a read-only release check instead of replaying the fixture')
    suffix=secrets.token_hex(4)
    readers={}
    for role in ('leaver','successor','coordinator'):
        name='QA '+role.title()+' '+suffix
        username='qa-'+role+'-'+suffix
        invite=call(admin,'POST','/api/invites',{'username':username,'name':name,'role':role}).json()
        password=secrets.token_urlsafe(24)
        call(admin,'POST','/api/register',{'code':invite['code'],'password':password})
        members=call(admin,'GET','/api/members').json()
        temporary.append(next(m['id'] for m in members if m['username']==username))
        client=httpx.Client(base_url=BASE,headers={'X-Baton-Request':'1'},timeout=90)
        call(client,'POST','/api/login',{'username':username,'role':'reviewer','password':password})
        readers[role]=(client,name)
    print('Hosted private login and named invitation/registration: passed',flush=True)
    gap=next(c for c in ws['claims'] if c['status']=='gap')
    call(admin,'POST','/api/questions/assign',{'claim_id':gap['id'],'assignee':'leaver','priority':'high','due':'2026-11-15'})
    call(readers['leaver'][0],'PATCH','/api/claims/'+gap['id'],{'action':'attest','text':'Kabir owns the nightly cleanup handover. Move it to the shared runner before the next registration cycle.','owner':'Kabir'})
    for claim in ws['claims']:
        if claim['status']=='conflicting':call(admin,'PATCH','/api/claims/'+claim['id'],{'action':'reject'})
    call(admin,'POST','/api/approve-verified')
    call(admin,'POST','/api/publish')
    ws=call(admin,'GET','/api/workspace').json()
    print('Hosted gap answer, review gate and approved snapshot: passed',flush=True)
    for role,(client,_) in readers.items():
        for path in ('/api/workspace','/api/versions/1','/api/export/md'):
            response=call(client,'GET',path)
            assert '42000' not in response.text and 'provider liaison is Neha' not in response.text
        if role=='coordinator':assert 'abc1234' not in call(client,'GET','/api/workspace').text
    successor,successor_name=readers['successor']
    risk=next(c for c in ws['approved_claims'] if c.get('type')=='risk')
    action={'claim_id':risk['id'],'title':'Confirm the webhook duplicate-event test with the reviewer','owner':successor_name,'phase':'Day 1','due':'2026-11-15','status':'todo'}
    created=call(admin,'POST','/api/actions',action).json()
    call(successor,'POST','/api/acknowledge',{'section':'next actions'})
    update={k:v for k,v in action.items() if k!='claim_id'};update['status']='done'
    call(successor,'PATCH','/api/actions/'+created['id'],update)
    assert call(successor,'GET','/api/workspace').json()['receipt_stale']
    markdown=call(successor,'GET','/api/export/md').text
    assert 'Continuation actions' in markdown and created['title'] in markdown
    pdf=call(successor,'GET','/api/export/pdf')
    assert pdf.content.startswith(b'%PDF')
    target=Path('tmp/hosted-handover.pdf');target.parent.mkdir(exist_ok=True);target.write_bytes(pdf.content)
    print('Hosted role leaks, owned actions, receipt invalidation and exports: passed',flush=True)
    result=call(admin,'POST','/api/reconstruct').json()
    print('Hosted reconstruction provider:',result['mode'],flush=True)
    print('Hosted reconstruction candidates:',result['count'],flush=True)
finally:
    for member_id in temporary:
        response=admin.patch('/api/members/'+member_id,json={'active':False})
        if response.status_code!=200:print('Temporary account revocation needs follow-up: HTTP '+str(response.status_code),flush=True)
    if temporary:print('Temporary QA accounts revoked.',flush=True)
