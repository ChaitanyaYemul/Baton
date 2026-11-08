"""Exercise the installed Supabase backend with synthetic sources only. Never prints credentials."""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['LLM_PROVIDER']='offline'
from fastapi.testclient import TestClient
from backend import main
from backend.engine import DEMO,parse_source,redact
import hashlib

if not main.storage.enabled():raise SystemExit('DATABASE_URL is not configured')
client=TestClient(main.app)
client.headers['X-Baton-Request']='1'
login=client.post('/api/login',json={'role':'reviewer','password':os.getenv('BATON_REVIEWER_PASSWORD','baton-demo-2026')})
assert login.status_code==200, f'Login failed ({login.status_code})'
ws=client.get('/api/workspace')
assert ws.status_code==200, f'Workspace failed ({ws.status_code})'
data=ws.json()
if not data['sources']:
    assert client.post('/api/demo').status_code==200
else:
    expected={hashlib.sha256(redact(parse_source(name,text))[0].encode()).hexdigest() for name,_,_,text in DEMO}
    if {s['hash'] for s in data['sources']}!=expected:
        raise SystemExit('Workspace contains non-fixture data; no mutation performed')
result=client.post('/api/reconstruct')
assert result.status_code==200,f'Reconstruction failed ({result.status_code})'
ws=client.get('/api/workspace').json()
print('Storage:',ws['storage'])
print('Persisted synthetic sources:',len(ws['sources']))
print('Draft claims:',len(ws['claims']))
for role in ('successor','coordinator','leaver'):
    reader=TestClient(main.app);reader.headers['X-Baton-Request']='1'
    assert reader.post('/api/login',json={'role':role,'password':os.getenv('BATON_'+role.upper()+'_PASSWORD','baton-demo-2026')}).status_code==200
    result=reader.get('/api/workspace')
    assert result.status_code==200
    assert '42000' not in result.text
print('Role read checks: passed')
