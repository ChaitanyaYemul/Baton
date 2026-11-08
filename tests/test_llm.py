import json
import httpx
import pytest
from backend.engine import Extraction, extract, reconstruct, redact
from backend.llm import configuration, cache_identity, strict_schema

SOURCE = {'id':'s','text':'Decision: keep payments in test mode. Owner: Kabir.','created_at':'2026-11-08T00:00:00Z'}

def content():
    return {'claims':[{'text':SOURCE['text'],'source_id':'s','quote':SOURCE['text'],'type':'decision',
                      'owner':'Kabir','subject':'payments','predicate':'mode','value':'test'}]}

def response(status=200, data=None, headers=None):
    return httpx.Response(status, json=data if data is not None else {
        'choices':[{'finish_reason':'stop','message':{'content':json.dumps(content())}}]},
        headers=headers, request=httpx.Request('POST','https://api.groq.com/openai/v1/chat/completions'))

@pytest.fixture
def groq(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','gsk_synthetic_test_key_not_real')
    monkeypatch.setattr('backend.llm.time.sleep',lambda _:None)

def test_groq_success_has_strict_schema_and_verifies_quote(groq,monkeypatch):
    def post(url,**kwargs):
        assert url=='https://api.groq.com/openai/v1/chat/completions'
        assert kwargs['headers']['Authorization']=='Bearer gsk_synthetic_test_key_not_real'
        body=kwargs['json']
        assert body['model']=='openai/gpt-oss-20b'
        assert body['response_format']['json_schema']['strict'] is True
        assert 'gsk_' not in json.dumps(body)
        schema=body['response_format']['json_schema']['schema']
        assert schema['additionalProperties'] is False
        candidate=schema['$defs']['Candidate']
        assert set(candidate['required'])==set(candidate['properties'])
        assert candidate['additionalProperties'] is False
        assert 'created_at' not in body['messages'][1]['content']
        return response()
    monkeypatch.setattr(httpx,'post',post)
    claims,mode=reconstruct([SOURCE])
    assert mode=='Groq · openai/gpt-oss-20b'
    assert claims[0]['status']=='verified'

@pytest.mark.parametrize('status',[400,401,403,404])
def test_permanent_failures_do_not_retry_or_leak_response(groq,monkeypatch,status):
    calls=[]
    def post(*args,**kwargs):
        calls.append(1)
        return response(status,{'error':{'message':'gsk_do_not_echo_upstream_secret'}})
    monkeypatch.setattr(httpx,'post',post)
    claims,mode=extract([SOURCE])
    assert claims and mode.startswith('offline fallback')
    assert len(calls)==1
    assert 'gsk_' not in mode

def test_short_rate_limit_retries_once(groq,monkeypatch):
    responses=iter([response(429,{}, {'retry-after':'1'}),response()])
    monkeypatch.setattr(httpx,'post',lambda *a,**kw:next(responses))
    _,mode=extract([SOURCE])
    assert mode.startswith('Groq')

def test_long_rate_limit_falls_back_without_sleep(groq,monkeypatch):
    def no_sleep(_): raise AssertionError('Must not wait for long rate limits')
    monkeypatch.setattr('backend.llm.time.sleep',no_sleep)
    monkeypatch.setattr(httpx,'post',lambda *a,**kw:response(429,{}, {'retry-after':'60'}))
    claims,mode=extract([SOURCE])
    assert claims and 'rate limited' in mode

def test_timeouts_are_bounded_and_retry_once(groq,monkeypatch):
    calls=[]
    def post(*a,**kw):
        assert kw['timeout'].read==15
        calls.append(1)
        raise httpx.ReadTimeout('gsk_never_echo_transport_details')
    monkeypatch.setattr(httpx,'post',post)
    claims,mode=extract([SOURCE])
    assert len(calls)==2 and claims
    assert 'timeout' in mode and 'gsk_' not in mode

@pytest.mark.parametrize('data',[
    {'choices':[{'finish_reason':'length','message':{'content':json.dumps(content())}}]},
    {'choices':[{'finish_reason':'stop','message':{'content':'{broken'}}]},
    {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'claims':[]})}}]},
    {'choices':None},
    {'choices':[{'finish_reason':'stop','message':{'content':None}}]},
])
def test_bad_or_truncated_model_output_is_offline(groq,monkeypatch,data):
    monkeypatch.setattr(httpx,'post',lambda *a,**kw:response(data=data))
    claims,mode=extract([SOURCE])
    assert claims and mode.startswith('offline fallback')

def test_gemini_cloud_fallback_is_explicit_opt_in(groq,monkeypatch):
    calls=[]
    monkeypatch.setenv('GEMINI_API_KEY','synthetic_gemini_key')
    def post(url,**kwargs):
        calls.append(url)
        if 'groq.com' in url:return response(401,{})
        return response(data={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(content())}]}}]})
    monkeypatch.setattr(httpx,'post',post)
    _,mode=extract([SOURCE])
    assert mode.startswith('offline fallback') and len(calls)==1
    monkeypatch.setenv('LLM_FALLBACK_PROVIDER','gemini')
    _,mode=extract([SOURCE])
    assert mode=='Gemini · gemini-2.5-flash · fallback'
    assert len(calls)==3

def test_missing_key_and_explicit_offline_do_not_make_calls(monkeypatch):
    def no_request(*a,**kw):raise AssertionError('No network request expected')
    monkeypatch.setattr(httpx,'post',no_request)
    monkeypatch.setenv('LLM_PROVIDER','groq')
    _,mode=extract([SOURCE])
    assert 'API key missing' in mode
    monkeypatch.setenv('GROQ_API_KEY','fake')
    monkeypatch.setenv('LLM_PROVIDER','offline')
    assert extract([SOURCE])[1]=='offline · extractive rules'

def test_cache_identity_tracks_provider_model_but_never_keys(groq,monkeypatch):
    original=cache_identity()
    monkeypatch.setenv('GROQ_API_KEY','a_different_secret')
    assert cache_identity()==original
    monkeypatch.setenv('GROQ_MODEL','openai/gpt-oss-120b')
    assert cache_identity()!=original
    assert 'a_different_secret' not in cache_identity()
    assert redact('key is gsk_abcdefghijklmnop1234567890')[0]=='key is [REDACTED]'

