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
    for name,text in [('empty.txt','   '),('bad.json','{broken'),('empty.csv','a,b\n'),('null.json','null'),('number.json','7'),('string.json','"notes"')]:
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

def test_api_retries_fallback_results_but_caches_success(clients,monkeypatch):
    c=clients['reviewer']
    assert c.post('/api/demo').status_code==200
    calls=[]
    def reconstruct(sources):
        calls.append(1)
        return [],'offline fallback · Groq rate limited' if len(calls)==1 else 'Groq · openai/gpt-oss-20b'
    monkeypatch.setattr(main,'reconstruct',reconstruct)
    assert c.post('/api/reconstruct').status_code==200
    assert c.post('/api/reconstruct').status_code==200
    assert c.post('/api/reconstruct').status_code==200
    assert len(calls)==2

def test_owned_actions_and_acknowledgement_invalidation(clients):
    reviewer=clients['reviewer'];setup(reviewer);finish(reviewer)
    ws=reviewer.get('/api/workspace').json()
    claim=next(c for c in ws['approved_claims'] if c.get('type')=='risk')
    payload={'claim_id':claim['id'],'title':'Add a duplicate webhook test','owner':'Meera','phase':'Day 1','due':'2026-11-15','status':'todo'}
    created=reviewer.post('/api/actions',json=payload)
    assert created.status_code==200,created.text
    action=created.json(); successor=clients['successor']
    assert successor.post('/api/acknowledge',json={'section':'next actions'}).status_code==200
    update={k:v for k,v in payload.items() if k!='claim_id'}; update['status']='done'
    assert clients['coordinator'].patch('/api/actions/'+action['id'],json=update).status_code==403
    assert successor.patch('/api/actions/'+action['id'],json=update).status_code==200
    ws=successor.get('/api/workspace').json()
    assert ws['actions'][0]['status']=='done'
    assert ws['receipt_stale'] and not ws['acks']
    hidden=next(c for c in reviewer.get('/api/workspace').json()['approved_claims'] if '42000' in c['text'])
    assert reviewer.post('/api/actions',json={**payload,'claim_id':hidden['id'],'title':'Review college reserve of 42000 INR'}).status_code==200
    assert '42000' not in successor.get('/api/workspace').text
    source=next(x for x in reviewer.get('/api/workspace').json()['sources'] if x['name']=='sync-notes.md')
    assert reviewer.patch('/api/sources/'+source['id'],json={'access':'leads'}).status_code==200
    assert successor.patch('/api/actions/'+action['id'],json=update).status_code==404

def test_question_assignment_and_sudden_exit_fallback(clients):
    reviewer=clients['reviewer'];ws=setup(reviewer)
    gap=next(c for c in ws['claims'] if c['status']=='gap')
    payload={'claim_id':gap['id'],'assignee':'leaver','priority':'high','due':'2026-11-12'}
    assert reviewer.post('/api/questions/assign',json=payload).json()['assignee']=='leaver'
    assert clients['successor'].post('/api/questions/assign',json=payload).status_code==403
    assert clients['leaver'].patch('/api/claims/'+gap['id'],json={'action':'attest','text':'Kabir owns the cron migration.','owner':'Kabir'}).status_code==200
    q=reviewer.get('/api/workspace').json()['questions'][0]
    assert q['answered_by']=='Aarav' and q['answered_at']
    # A new gap remains routed to the reviewer when the departing member is unavailable.
    reviewer.patch('/api/settings',json={'sudden_exit':True})
    with main.state() as s:
        claim=next(c for c in s['claims'] if c['id']==gap['id']);claim['status']='gap'
    assert reviewer.post('/api/questions/assign',json=payload).json()['assignee']=='reviewer'

def test_named_accounts_invites_and_immediate_revocation(clients):
    reviewer=clients['reviewer']
    invitation=reviewer.post('/api/invites',json={'username':'taylor','name':'Taylor','role':'successor'})
    assert invitation.status_code==200,invitation.text
    code=invitation.json()['code']
    member=TestClient(main.app);member.headers['X-Baton-Request']='1'
    assert member.post('/api/register',json={'code':code,'password':'too-short'}).status_code==422
    assert member.post('/api/register',json={'code':code,'password':'synthetic-only-password'}).status_code==200
    assert member.post('/api/register',json={'code':code,'password':'synthetic-only-password'}).status_code==400
    result=member.post('/api/login',json={'username':'taylor','role':'reviewer','password':'synthetic-only-password'})
    assert result.status_code==200 and result.json()['role']=='successor'
    assert member.get('/api/workspace').json()['user']['name']=='Taylor'
    assert member.post('/api/publish').status_code==403
    assert member.get('/api/members').status_code==403
    people=reviewer.get('/api/members').json()
    assert 'password' not in str(people) and 'salt' not in str(people)
    assert reviewer.patch('/api/members/'+people[0]['id'],json={'active':False}).status_code==200
    assert member.get('/api/workspace').status_code==401
    assert member.post('/api/login',json={'username':'taylor','password':'synthetic-only-password'}).status_code==401


def join_project(reviewer, username, role='successor', member=None):
    if member is None:
        member = TestClient(main.app, headers={'X-Baton-Request':'1'})
    password = 'synthetic-only-password'
    invitation = reviewer.post('/api/invites',json={'username':username,'name':username.title(),'role':role})
    assert invitation.status_code == 200, invitation.text
    registration = member.post('/api/register',json={'code':invitation.json()['code'],'password':password})
    assert registration.status_code == 200, registration.text
    login = member.post('/api/login',json={'username':username,'password':password})
    assert login.status_code == 200, login.text
    member_id = next(m['id'] for m in reviewer.get('/api/members').json() if m['username'] == username)
    return member, member_id


def test_project_memberships_keep_sources_history_and_exports_separate(clients):
    demo = clients['reviewer']
    taylor, taylor_id = join_project(demo,'taylor')
    assert demo.post('/api/projects',json={'name':'Shared account project'}).status_code == 403
    first = setup(demo)
    finish(demo)

    project = taylor.post('/api/projects',json={'name':'Second project'})
    assert project.status_code == 201, project.text
    project_id = project.json()['id']
    taylor.headers['X-Baton-Project'] = str(project_id)
    assert taylor.get('/api/workspace').json()['sources'] == []
    assert taylor.get('/api/workspace').json()['user']['role'] == 'reviewer'
    second = setup(taylor)
    finish(taylor)
    taylor_claim = next(c for c in second['claims'] if c['status'] == 'verified')
    demo_claim = next(c for c in first['claims'] if c['status'] == 'verified')
    assert taylor.get(f"/api/evidence/{demo_claim['id']}?version=1").status_code == 404
    assert demo.get(f"/api/evidence/{taylor_claim['id']}?version=1").status_code == 404
    assert 'Second project' in taylor.get(f'/api/export/md?project={project_id}').text
    assert taylor.get('/api/versions/1').json()['number'] == 1
    assert demo.get('/api/versions/1').json()['number'] == 1

    sam, sam_id = join_project(taylor,'sam')
    sam.headers['X-Baton-Project'] = str(project_id)
    assert sam.get('/api/workspace').json()['user']['role'] == 'successor'
    denied = {'X-Baton-Project':'1'}
    for path in ('/api/workspace','/api/versions/1','/api/export/md','/api/members',
                 f"/api/evidence/{demo_claim['id']}?version=1"):
        assert sam.get(path, headers=denied).status_code == 404
    del sam.headers['X-Baton-Project']
    assert sam.get('/api/export/pdf?project=1').status_code == 404
    assert sam.get(f'/api/export/pdf?project={project_id}').content.startswith(b'%PDF')
    assert demo.patch(f'/api/members/{sam_id}',json={'active':False}).status_code == 404

    join_project(demo,'sam','coordinator',member=sam)
    assert sam.get('/api/workspace',headers=denied).json()['user']['role'] == 'coordinator'
    assert sam.get('/api/workspace',headers={'X-Baton-Project':str(project_id)}).json()['user']['role'] == 'successor'
    assert demo.patch(f'/api/members/{taylor_id}',json={'active':False}).status_code == 200
    assert taylor.get('/api/workspace',headers=denied).status_code == 404
    assert taylor.get('/api/workspace').json()['user']['role'] == 'reviewer'


def test_adaptive_questions_require_named_answer_and_reviewer_confirmation(clients):
    reviewer = clients['reviewer']
    ws = setup(reviewer)
    member, member_id = join_project(reviewer,'casey')
    assert reviewer.post('/api/questions/generate').json()['created'] >= 1
    assert reviewer.post('/api/questions/generate').json()['created'] == 0
    question = reviewer.get('/api/workspace').json()['questions'][0]
    assert question['prompt'] and question['answer_hint']
    assert question['claim_id'] in {c['id'] for c in ws['claims'] if c['status'] == 'gap'}
    result = reviewer.post('/api/questions/assign',json={
        'claim_id':question['claim_id'],'assignee':'reviewer','assignee_id':member_id,'priority':'high',
    })
    assert result.status_code == 200, result.text
    route = f"/api/questions/{question['id']}"
    assert member.get('/api/workspace').json()['claims'] == []
    assert member.get(route+'/evidence').json()[0]['quote']
    assert clients['successor'].get(route+'/evidence').status_code == 404
    assert clients['successor'].post(route+'/answer',json={'text':'Not sure'}).status_code == 404
    assert reviewer.post(route+'/confirm').status_code == 409
    assert member.post(route+'/answer',json={'text':'Not sure'}).json()['follow_up']
    assert reviewer.post(route+'/confirm').status_code == 409
    answer = 'Casey will own the nightly cleanup job. The steps are in the operations notes.'
    assert member.post(route+'/answer',json={'text':answer}).json()['follow_up'] is None
    assert reviewer.post('/api/publish').status_code == 400
    assert reviewer.post(route+'/confirm').status_code == 200
    claim = next(c for c in reviewer.get('/api/workspace').json()['claims'] if c['id']==question['claim_id'])
    assert claim['status'] == 'attested' and claim['review'] == 'pending'
    assert claim['text'] == answer
    assert claim['attestation']['by'] == 'Casey'
    finish(reviewer)
    approved = member.get('/api/workspace').json()['approved_claims']
    assert any(c.get('text') == answer for c in approved)
    assert not any('Not sure' in c.get('text','') for c in approved)


def test_catch_up_uses_personal_receipts_and_current_source_permissions(clients):
    reviewer = clients['reviewer']
    setup(reviewer)
    finish(reviewer)
    early, _ = join_project(reviewer,'early')
    later, _ = join_project(reviewer,'later')
    assert early.post('/api/acknowledge',json={'section':'decisions'}).status_code == 200
    old = next(c for c in reviewer.get('/api/workspace').json()['approved_claims'] if c.get('type') == 'risk')
    assert reviewer.patch('/api/claims/'+old['id'],json={
        'action':'attest','text':old['text'],'owner':'Casey',
    }).status_code == 200
    assert reviewer.post('/api/sources',json={
        'name':'release.md','text':'Risk: The nightly registration job is blocked by the release freeze. Owner: Casey.',
        'kind':'notes','access':'core','authorised':True,
    }).status_code == 200
    assert reviewer.post('/api/reconstruct').status_code == 200
    finish(reviewer)
    risk = next(c for c in reviewer.get('/api/workspace').json()['approved_claims'] if 'release freeze' in c['text'])
    assert reviewer.post('/api/actions',json={
        'claim_id':risk['id'],'title':'Resolve release freeze','owner':'Casey','status':'blocked','due':'2020-01-01',
    }).status_code == 200
    assert later.post('/api/acknowledge',json={'section':'risks'}).status_code == 200
    first = early.get('/api/workspace').json()['catch_up']
    second = later.get('/api/workspace').json()['catch_up']
    assert first['baseline']['version'] == 1 and second['baseline']['version'] == 2
    assert first['responsibilities'][0]['owner'] == 'Casey' and second['responsibilities'] == []
    assert [r['id'] for r in first['risks']] == [risk['id']] and second['risks'] == []
    assert first['actions'][0]['overdue'] and first['actions'][0]['status'] == 'blocked'
    evidence = f"/api/evidence/{risk['id']}?version=2"
    assert early.get(evidence).status_code == 200
    assert reviewer.patch('/api/sources/'+risk['evidence'][0]['source_id'],json={'access':'leads'}).status_code == 200
    restricted = early.get('/api/workspace').json()['catch_up']
    assert restricted['risks'] == [] and restricted['actions'] == []
    assert early.get(evidence).status_code == 404

def test_repeating_publish_and_acknowledgement_keeps_one_record(clients):
    reviewer = clients['reviewer']
    successor = clients['successor']
    setup(reviewer)
    finish(reviewer)
    assert reviewer.post('/api/publish').json() == {'number':1,'unchanged':True}
    for _ in range(2):
        assert successor.post('/api/acknowledge',json={'section':'decisions'}).status_code == 200
    workspace = successor.get('/api/workspace').json()
    assert len(workspace['versions']) == 1
    assert len(workspace['acks']) == 1


def test_disabling_demo_rejects_previously_seeded_demo_passwords(clients,monkeypatch):
    monkeypatch.setenv('BATON_DEMO','0')
    for role in main.ROLES:
        c=TestClient(main.app)
        assert c.post('/api/login',json={'role':role,'password':'baton-demo-2026'}).status_code==401
    assert c.get('/api/config').json()=={'demo':False,'roles':[]}
    monkeypatch.setenv('BATON_REVIEWER_PASSWORD','synthetic-private-password')
    assert c.get('/api/config').json()=={'demo':False,'roles':['reviewer']}

def test_version_diff_includes_owner_and_historical_receipts(clients):
    reviewer=clients['reviewer'];setup(reviewer);finish(reviewer)
    claim=next(c for c in reviewer.get('/api/workspace').json()['approved_claims'] if c['status']=='verified')
    reviewer.patch('/api/claims/'+claim['id'],json={'action':'attest','text':claim['text'],'owner':'New owner'})
    reviewer.post('/api/approve-verified'); assert reviewer.post('/api/publish').status_code==200
    version=reviewer.get('/api/versions/2').json()
    changed=next(c for c in version['claims'] if c['id']==claim['id'])
    assert changed['change']=='changed' and 'owner' in changed['changed_fields']
    assert changed['previous']['owner']==claim['owner']
    assert reviewer.get('/api/evidence/'+claim['id']+'?version=1').status_code==200
