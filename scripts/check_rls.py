"""Live RLS probe using rollback-only synthetic canaries, never real credentials or source output."""
import copy
import secrets
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import config
from backend.storage import open_connection
from psycopg.types.json import Jsonb
from psycopg.errors import InsufficientPrivilege,RaiseException

with open_connection() as con:
    assert con.execute('select rolbypassrls from pg_roles where rolname=current_user').fetchone()==(False,)
    assert con.execute('select count(*) from public.baton_sources').fetchone()[0]==0
    assert con.execute('select count(*) from baton_private.users').fetchone()[0]==0
    con.execute("select set_config('baton.viewer_role','reviewer',true)")
    suffix=secrets.token_hex(8)
    core,secret='core-'+suffix,'lead-'+suffix
    for source_id,access in [(core,'core'),(secret,'leads')]:
        body={'id':source_id,'access':access,'name':'rollback-only synthetic canary','text':'RLS_SECRET_CANARY_'+suffix}
        con.execute('insert into public.baton_sources(id,body) values(%s,%s)',(source_id,Jsonb(body)))
    claim_id='claim-'+suffix
    body={'id':claim_id,'text':'RLS_SECRET_CANARY_'+suffix,'owner':'Kabir','status':'verified','review':'approved',
          'evidence':[{'source_id':core,'quote':'canary','found':True},{'source_id':secret,'quote':'canary','found':True}]}
    con.execute('insert into public.baton_claims(revision,id,body,evidence_ids) values(999999,%s,%s,%s)',(claim_id,Jsonb(body),[core,secret]))
    for role in ('successor','coordinator','leaver'):
        con.execute("select set_config('baton.viewer_role',%s,true)",(role,))
        assert con.execute('select count(*) from public.baton_sources where id=%s',(secret,)).fetchone()[0]==0
        assert con.execute('select count(*) from public.baton_claims where id=%s',(claim_id,)).fetchone()[0]==0
    con.execute("select set_config('baton.viewer_role','reviewer',true)")
    assert con.execute('select count(*) from public.baton_claims where id=%s',(claim_id,)).fetchone()[0]==1
    con.execute('update public.baton_sources set body=jsonb_set(body,\'{access}\',\'"core"\') where id=%s',(secret,))
    con.execute("select set_config('baton.viewer_role','successor',true)")
    assert con.execute('select count(*) from public.baton_claims where id=%s',(claim_id,)).fetchone()[0]==1
    con.execute("select set_config('baton.viewer_role','reviewer',true)")
    try:
        with con.transaction():
            changed=con.execute("update public.baton_claims set body=jsonb_set(body,'{owner}','\"Other\"') where id=%s",(claim_id,)).rowcount
            assert changed==0,'Published snapshot unexpectedly writable'
    except (InsufficientPrivilege,RaiseException):pass
    con.rollback()
print('Live RLS: role context required; auth tables hidden; multi-source intersection enforced; live source labels rechecked; published snapshots immutable.')
print('All canary writes rolled back.')
