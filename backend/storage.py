"""Supabase Postgres adapter. Every state transaction uses the authenticated role under RLS."""
import copy
import hashlib
import json
import os
from contextlib import contextmanager
import psycopg
from psycopg.types.json import Jsonb

def enabled():
    return bool(os.getenv('DATABASE_URL'))

def open_connection():
    # Supavisor transaction mode requires prepared statements to remain disabled.
    return psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=10, prepare_threshold=None)

class AuthConnection:
    """Small compatibility surface for the existing SQLite authentication code."""
    def __init__(self):
        self.connection = open_connection()
        self.begin()
    def begin(self):
        self.connection.execute("set local search_path = baton_private, pg_catalog")
        self.connection.execute("select set_config('baton.auth_phase','1',true)")
    def execute(self, sql, params=()):
        sql = sql.replace('?', '%s')
        if sql.startswith('INSERT OR REPLACE INTO users'):
            sql = sql.replace('INSERT OR REPLACE', 'INSERT')+' ON CONFLICT(role) DO UPDATE SET salt=excluded.salt,password=excluded.password'
        if sql.startswith('INSERT OR REPLACE INTO login_attempts'):
            sql = sql.replace('INSERT OR REPLACE', 'INSERT')+' ON CONFLICT(address) DO UPDATE SET body=excluded.body'
        return self.connection.execute(sql, params)
    def commit(self):
        self.connection.commit()
        self.begin()
    def close(self):
        self.connection.close()

def _event_id(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()

def _stub(claim_id):
    return {'id':claim_id,'text':'Restricted knowledge','owner':'Kabir','reason':'Ask the reviewer for access.',
            'evidence':[],'conflicts':[],'restricted':True}

def _rows(connection, table):
    # Callers choose from hard-coded internal table names, never request input.
    return [r[0] for r in connection.execute('select body from '+table).fetchall()]

def _load(connection, initial):
    result=initial()
    row=connection.execute('select body from public.baton_workspace where id=1').fetchone()
    if not row:
        raise PermissionError('Workspace access denied by database policy')
    result.update(row[0])
    result['sources']=_rows(connection,'public.baton_sources')
    records={(r[0],r[1]):r[2] for r in connection.execute('select revision,id,body from public.baton_claims')}
    index=connection.execute('select revision,id from public.baton_claim_index order by revision,id').fetchall()
    by_revision={}
    for rev,cid in index:
        by_revision.setdefault(rev,[]).append(records.get((rev,cid),_stub(cid)))
    result['claims']=by_revision.get(0,[])
    result['versions']=sorted(_rows(connection,'public.baton_versions'),key=lambda v:v['number'])
    for v in result['versions']:
        v['claims']=by_revision.get(v['number'],[])
    result['audit']=sorted(_rows(connection,'public.baton_audit'),key=lambda e:e['at'])
    result['acks']=_rows(connection,'public.baton_acknowledgements')
    result['actions']=_rows(connection,'public.baton_actions')
    result['questions']=_rows(connection,'public.baton_questions')
    result['cache']={r[0]:r[1] for r in connection.execute('select id,body from baton_private.cache')}
    return result

def _sync_records(con, table, before, after, allow_delete=False, extra=None):
    old={x['id']:x for x in before}
    new={x['id']:x for x in after}
    if allow_delete:
        for key in old.keys()-new.keys():
            con.execute('delete from '+table+' where id=%s',(key,))
    for key,value in new.items():
        if old.get(key)==value:
            continue
        fields, values = (extra(value) if extra else ([],[]))
        names=['id','body',*fields]
        args=[key,Jsonb(value),*values]
        if key in old:
            assignments=','.join(n+'=%s' for n in names[1:])
            con.execute('update '+table+' set '+assignments+' where id=%s',[*args[1:],key])
        else:
            con.execute('insert into '+table+'('+','.join(names)+') values('+','.join(['%s']*len(names))+')',args)

def _save(con,before,after,role):
    meta={k:after[k] for k in ('project','mode','sudden_exit')}
    if any(before.get(k)!=v for k,v in meta.items()):
        con.execute('update public.baton_workspace set body=%s where id=1',(Jsonb(meta),))
    _sync_records(con,'public.baton_sources',before['sources'],after['sources'],allow_delete=role=='reviewer')
    old_claims={(0,c['id']):c for c in before['claims']}
    new_claims={(0,c['id']):c for c in after['claims']}
    for version in before['versions']:
        old_claims.update({(version['number'],c['id']):c for c in version['claims']})
    for version in after['versions']:
        new_claims.update({(version['number'],c['id']):c for c in version['claims']})
    for (rev,cid) in old_claims.keys()-new_claims.keys():
        if rev==0 and role=='reviewer':
            con.execute('delete from public.baton_claims where revision=0 and id=%s',(cid,))
            con.execute('delete from public.baton_claim_index where revision=0 and id=%s',(cid,))
    for key,claim in new_claims.items():
        if old_claims.get(key)==claim or claim.get('restricted'):
            continue
        rev,cid=key
        ids=[e['source_id'] for e in claim['evidence']]
        if key in old_claims:
            con.execute('update public.baton_claims set body=%s,evidence_ids=%s where revision=%s and id=%s',(Jsonb(claim),ids,rev,cid))
        else:
            con.execute('insert into public.baton_claims(revision,id,body,evidence_ids) values(%s,%s,%s,%s)',(rev,cid,Jsonb(claim),ids))
            con.execute('insert into public.baton_claim_index values(%s,%s)',(rev,cid))
    for version in after['versions']:
        if not any(v['number']==version['number'] for v in before['versions']):
            body={k:v for k,v in version.items() if k!='claims'}
            body['count']=len(version['claims'])
            con.execute('insert into public.baton_versions values(%s,%s)',(version['number'],Jsonb(body)))
    for table,key in [('public.baton_audit','audit'),('public.baton_acknowledgements','acks')]:
        previous={_event_id(e) for e in before[key]}
        for event in after[key]:
            eid=_event_id(event)
            if eid not in previous:
                con.execute('insert into '+table+' values(%s,%s) on conflict do nothing',(eid,Jsonb(event)))
    _sync_records(con,'public.baton_actions',before.get('actions',[]),after.get('actions',[]),
                  extra=lambda v:(['claim_id','revision'],[v['claim_id'],v['version']]))
    _sync_records(con,'public.baton_questions',before.get('questions',[]),after.get('questions',[]),
                  extra=lambda v:(['claim_id'],[v['claim_id']]))
    if role=='reviewer':
        for key,value in after['cache'].items():
            if before['cache'].get(key)!=value:
                con.execute('insert into baton_private.cache values(%s,%s) on conflict(id) do update set body=excluded.body',(key,Jsonb(value)))

@contextmanager
def remote_state(initial,role,user_id=None,name=None):
    if role not in ('reviewer','successor','coordinator','leaver'):
        raise PermissionError('Authenticated role required')
    with open_connection() as con:
        con.execute("select set_config('baton.viewer_role',%s,true)",(role,))
        con.execute("select set_config('baton.viewer_id',%s,true)",(user_id or role,))
        con.execute("select set_config('baton.viewer_name',%s,true)",(name or '',))
        con.execute('select pg_advisory_xact_lock(7261401)')
        state=_load(con,initial)
        before=copy.deepcopy(state)
        yield state
        _save(con,before,state,role)
