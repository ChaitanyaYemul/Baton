import json
import pytest
from fastapi.testclient import TestClient
from backend import main
from backend.engine import Candidate, DEMO, parse_source, redact, reconstruct, verify

@pytest.fixture
def clients(tmp_path,monkeypatch):
    monkeypatch.setenv('BATON_DEMO','1')
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    monkeypatch.setattr(main,'DB',tmp_path/'test.sqlite3')
    main.FAILURES.clear()
    clients={}
    for role in main.ROLES:
        c=TestClient(main.app)
        c.headers['X-Baton-Request']='1'
        assert c.post('/api/login',json={'role':role,'password':'baton-demo-2026'}).status_code==200
        clients[role]=c
    return clients

def setup(c):
    assert c.post('/api/demo').status_code==200
    assert c.post('/api/reconstruct').status_code==200
    return c.get('/api/workspace').json()

def finish(c):
    ws=c.get('/api/workspace').json()
    for claim in ws['claims']:
        if claim['status']=='gap':
            assert c.patch('/api/claims/'+claim['id'],json={'action':'attest','text':'Kabir owns the nightly cleanup cron; move it to the shared runner.','owner':'Kabir'}).status_code==200
        elif claim['status']=='conflicting':
            assert c.patch('/api/claims/'+claim['id'],json={'action':'reject'}).status_code==200
    assert c.post('/api/approve-verified').status_code==200
    result=c.post('/api/publish')
    assert result.status_code==200,result.text

def test_judge_journey_and_immutable_snapshot(clients):
    c=clients['reviewer']; ws=setup(c)
    assert len(ws['sources'])==5
    assert len([x for x in ws['claims'] if x['status']=='conflicting'])==4
    assert len([x for x in ws['claims'] if x['status']=='gap'])>=1
    assert c.post('/api/publish').status_code==400
    assert clients['successor'].get('/api/workspace').json()['claims']==[]
    finish(c)
    view=clients['successor'].get('/api/workspace').json()
    assert view['claims']
    claim=next(x for x in view['claims'] if not x.get('restricted'))
    assert clients['successor'].get('/api/evidence/'+claim['id']).status_code==200
    before=clients['successor'].get('/api/versions/1').json()
    assert c.patch('/api/claims/'+claim['id'],json={'action':'attest','text':'Updated only in draft','owner':'Kabir'}).status_code==200
    assert clients['successor'].get('/api/versions/1').json()==before
    assert clients['successor'].post('/api/acknowledge',json={'section':'decisions'}).status_code==200
    assert clients['successor'].get('/api/export/md').status_code==200
    assert clients['successor'].get('/api/export/pdf').content.startswith(b'%PDF')

@pytest.mark.parametrize('role',['successor','coordinator','leaver'])
def test_permissions_and_leak_matrix(clients,role):
    reviewer=clients['reviewer']; setup(reviewer); finish(reviewer)
    c=clients[role]
    restricted=next(x for x in reviewer.get('/api/workspace').json()['claims'] if '42000' in x['text'])
    for path in ['/api/workspace','/api/versions/1','/api/export/md']:
        response=c.get(path)
        assert '42000' not in response.text
        assert 'provider liaison is Neha' not in response.text
        assert 'synthetic_demo_secret' not in response.text
    assert c.get('/api/evidence/'+restricted['id']).status_code==404
    assert '42000' not in c.post('/api/ask',json={'question':'What is the payment reserve 42000?'}).text
    assert c.post('/api/publish').status_code==403
    assert c.post('/api/reconstruct').status_code==403
    if role=='coordinator':
        assert 'abc1234' not in c.get('/api/workspace').text

def test_access_revocation_rechecks_history_and_exports(clients):
    c=clients['reviewer']; setup(c); finish(c)
    successor=clients['successor']
    source=next(s for s in c.get('/api/workspace').json()['sources'] if s['kind']=='git')
    assert 'abc1234' in successor.get('/api/workspace').text
    assert c.patch('/api/sources/'+source['id'],json={'access':'leads'}).status_code==200
    for path in ['/api/workspace','/api/versions/1','/api/export/md']:
        assert 'abc1234' not in successor.get(path).text
    assert c.delete('/api/sources/'+source['id']).status_code==200
    assert 'abc1234' not in c.get('/api/export/md').text

def test_quote_forgery_and_paraphrase_do_not_verify():
    sources=[{'id':'s','text':'Decision: use a shared runner. Owner: Kabir.','created_at':'2026-11-08T00:00:00Z'}]
    def candidate(text,quote,source='s'):
        return Candidate(text=text,quote=quote,source_id=source,type='decision')
    assert verify(candidate('Invented claim','Invented quote'),sources)['status']=='inferred'
    assert verify(candidate('Unrelated paraphrase',sources[0]['text']),sources)['status']=='inferred'
    assert verify(candidate('Claim','Quote','nonexistent'),sources) is None
    assert verify(candidate(sources[0]['text'],sources[0]['text']),sources)['status']=='verified'

def test_redaction_preserves_chat_dates_and_categories():
    from backend.engine import classify
    text='2026-11-02 10:15 Aarav: API decision. Phone +91 9876543210'
    result,count=redact(text)
    assert '2026-11-02 10:15' in result
    assert '9876543210' not in result
    assert count==1
    assert classify('Recurring: webhook timeout happened again. Owner: Meera.')=='recurring'
    assert classify('Dependency: move cron | status: Todo | owner: Aarav')=='dependency'

def test_multisource_visibility_intersection_and_ack_invalidation(clients):
    c=clients['reviewer']; setup(c); finish(c)
    successor=clients['successor']
    assert successor.post('/api/acknowledge',json={'section':'risks'}).status_code==200
    assert successor.get('/api/workspace').json()['acks']
    with main.state() as s:
        lead=next(x for x in s['claims'] if '42000' in x['text'])
        public=next(x for x in s['versions'][0]['claims'] if 'Payments stay' in x['text'])
        public['evidence'].extend(lead['evidence'])
    view=successor.get('/api/workspace').json()
    assert 'Payments stay' not in json.dumps(view)
    assert 'Payments stay' not in successor.get('/api/export/md').text
    source=next(x for x in c.get('/api/workspace').json()['sources'] if x['kind']=='git')
    assert c.patch('/api/sources/'+source['id'],json={'access':'leads'}).status_code==200
    assert successor.get('/api/workspace').json()['acks']==[]

def test_model_error_falls_back_to_labelled_offline(monkeypatch):
    from backend.engine import extract
    import httpx
    monkeypatch.setenv('GEMINI_API_KEY','fake_test_key')
    def unavailable(*args,**kwargs): raise httpx.ConnectError('unavailable')
    monkeypatch.setattr(httpx,'post',unavailable)
    claims,mode=extract([{'id':'s','text':'Decision: use a shared runner. Owner: Kabir.'}])
    assert claims and 'fallback' in mode

def test_repeated_lines_and_invalid_dates_are_safe(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    line='2026-99-99 Decision: use a shared runner. Owner: Kabir.'
    claims,_=reconstruct([{'id':'s','text':line+'\n'+line,'created_at':'2026-11-08T00:00:00Z'}])
    assert len(claims)==1
    assert claims[0]['date']=='2026-11-08'

def test_import_failures_and_redaction(clients):
    c=clients['reviewer']
    for name,text in [('empty.txt','   '),('bad.json','{broken'),('empty.csv','a,b\n')]:
        assert c.post('/api/sources',json={'name':name,'text':text,'authorised':True}).status_code==400
    assert c.post('/api/sources',json={'name':'note.md','text':'Decision: keep this private.','authorised':False}).status_code==400
    data={'name':'note.md','text':'Decision: test payments. Owner: Aarav. Email demo@example.com API_KEY=secret1234567890','authorised':True}
    assert c.post('/api/sources',json=data).status_code==200
    assert c.post('/api/sources',json=data).status_code==409
    assert c.post('/api/reconstruct').status_code==200
    assert 'secret1234567890' not in c.get('/api/workspace').text
    assert 'demo@example.com' not in c.get('/api/workspace').text
    assert c.post('/api/github',json={'url':'http://127.0.0.1/private','authorised':True}).status_code==400

def test_leaver_answer_and_sudden_exit(clients):
    reviewer=clients['reviewer']; ws=setup(reviewer)
    gap=next(c for c in ws['claims'] if c['status']=='gap')
    leaver=clients['leaver']
    assert leaver.patch('/api/claims/'+gap['id'],json={'action':'attest','text':'Kabir owns this job.','owner':'Kabir'}).status_code==200
    c=next(c for c in reviewer.get('/api/workspace').json()['claims'] if c['id']==gap['id'])
    assert c['status']=='attested' and c['review']=='pending' and c['attestation']['by']=='Aarav'
    assert reviewer.patch('/api/settings',json={'sudden_exit':True}).status_code==200
    assert leaver.patch('/api/claims/'+gap['id'],json={'action':'attest','text':'New answer'}).status_code==403

def test_authentication_and_request_protection(clients):
    anonymous=TestClient(main.app)
    assert anonymous.get('/api/workspace').status_code==401
    c=clients['reviewer']
    del c.headers['X-Baton-Request']
    assert c.post('/api/demo').status_code==403
    assert anonymous.post('/api/login',json={'role':'reviewer','password':'wrong'}).status_code==401
