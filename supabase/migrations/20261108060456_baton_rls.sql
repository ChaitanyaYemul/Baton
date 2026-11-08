-- Baton: normalised persistence and defence-in-depth RLS.
-- Runtime credentials are provisioned separately and never belong in this migration.
create role baton_runtime nologin nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
create schema baton_private;
revoke all on schema baton_private from public, anon, authenticated;
grant usage on schema public, baton_private to baton_runtime;

create function baton_private.viewer_role() returns text
language sql stable security invoker set search_path = ''
as $$ select nullif(current_setting('baton.viewer_role', true), '') $$;
revoke all on function baton_private.viewer_role() from public;
grant execute on function baton_private.viewer_role() to baton_runtime;

create function baton_private.source_ids(value jsonb) returns text[]
language sql immutable security invoker set search_path = ''
as $$ select coalesce(array_agg(e->>'source_id'), '{}'::text[]) from jsonb_array_elements(coalesce(value->'evidence','[]'::jsonb)) e $$;
revoke all on function baton_private.source_ids(jsonb) from public;
grant execute on function baton_private.source_ids(jsonb) to baton_runtime;

create table public.baton_workspace (
  id integer primary key check (id = 1), body jsonb not null
);
insert into public.baton_workspace values (1, '{"project":"Fest registration portal","mode":"Not reconstructed","sudden_exit":false}');
create table public.baton_sources (
  id text primary key, body jsonb not null,
  access text generated always as (body->>'access') stored,
  check (id=body->>'id'), check (access in ('core','technical','leads'))
);
create table public.baton_versions (
  number integer primary key check(number>0), body jsonb not null
);
create table public.baton_claim_index (
  revision integer not null, id text not null, primary key (revision,id)
);
create table public.baton_claims (
  revision integer not null check(revision>=0), id text not null, body jsonb not null,
  evidence_ids text[] not null,
  primary key(revision,id),
  check(id=body->>'id'),
  check(evidence_ids=baton_private.source_ids(body)),
  check(revision=0 or (body->>'review'='approved' and body->>'status' in ('verified','attested')))
);
create index baton_claims_evidence_idx on public.baton_claims using gin(evidence_ids);
create table public.baton_audit (id text primary key, body jsonb not null);
create table public.baton_acknowledgements (id text primary key, body jsonb not null);
create table public.baton_actions (id text primary key, claim_id text not null, revision integer not null, body jsonb not null);
create table public.baton_questions (id text primary key, claim_id text not null, body jsonb not null);
create table baton_private.cache (id text primary key, body jsonb not null);
create table baton_private.users (role text primary key, salt text not null, password text not null);
create table baton_private.sessions (token text primary key, role text not null, expires double precision not null, account_id text, name text);
create index baton_sessions_expiry_idx on baton_private.sessions(expires);
create table baton_private.accounts (id text primary key, username text unique not null, role text not null check(role in ('reviewer','successor','coordinator','leaver')), name text not null, salt text not null, password text not null, active boolean not null default true);
create table baton_private.login_attempts (address text primary key, body jsonb not null);

-- Prevent edits to published content and audit history even by the application role.
create function baton_private.protect_snapshot() returns trigger
language plpgsql security invoker set search_path = '' as $$
begin
  if old.revision>0 then raise exception 'Published snapshots are immutable'; end if;
  return coalesce(new,old);
end $$;
revoke all on function baton_private.protect_snapshot() from public;
grant execute on function baton_private.protect_snapshot() to baton_runtime;
create trigger immutable_snapshot before update or delete on public.baton_claims
for each row execute function baton_private.protect_snapshot();

alter table public.baton_workspace enable row level security;
alter table public.baton_workspace force row level security;
alter table public.baton_sources enable row level security;
alter table public.baton_sources force row level security;
alter table public.baton_versions enable row level security;
alter table public.baton_versions force row level security;
alter table public.baton_claim_index enable row level security;
alter table public.baton_claim_index force row level security;
alter table public.baton_claims enable row level security;
alter table public.baton_claims force row level security;
alter table public.baton_audit enable row level security;
alter table public.baton_audit force row level security;
alter table public.baton_acknowledgements enable row level security;
alter table public.baton_acknowledgements force row level security;
alter table public.baton_actions enable row level security;
alter table public.baton_actions force row level security;
alter table public.baton_questions enable row level security;
alter table public.baton_questions force row level security;
alter table baton_private.cache enable row level security;
alter table baton_private.cache force row level security;
alter table baton_private.users enable row level security;
alter table baton_private.users force row level security;
alter table baton_private.sessions enable row level security;
alter table baton_private.sessions force row level security;
alter table baton_private.accounts enable row level security;
alter table baton_private.accounts force row level security;
alter table baton_private.login_attempts enable row level security;
alter table baton_private.login_attempts force row level security;

-- Source visibility is live; no JWT user_metadata is trusted for authorization.
create policy source_read on public.baton_sources for select to baton_runtime using (
  baton_private.viewer_role()='reviewer' or
  (baton_private.viewer_role() in ('successor','leaver') and access in ('core','technical')) or
  (baton_private.viewer_role()='coordinator' and access='core')
);
create policy source_write on public.baton_sources for all to baton_runtime
using(baton_private.viewer_role()='reviewer') with check(baton_private.viewer_role()='reviewer');
create policy claim_read on public.baton_claims for select to baton_runtime using (
  (revision>0 or baton_private.viewer_role() in ('reviewer','leaver')) and
  cardinality(evidence_ids)>0 and
  not exists(select 1 from unnest(evidence_ids) sid where not exists(select 1 from public.baton_sources s where s.id=sid))
);
create policy claim_write on public.baton_claims for all to baton_runtime
using(baton_private.viewer_role()='reviewer' and revision=0)
with check(baton_private.viewer_role()='reviewer');
create policy leaver_answer on public.baton_claims for update to baton_runtime
using(revision=0 and baton_private.viewer_role()='leaver' and body->>'status'='gap' and
  not exists(select 1 from unnest(evidence_ids) sid where not exists(select 1 from public.baton_sources s where s.id=sid)))
with check(revision=0 and baton_private.viewer_role()='leaver' and body->>'status'='attested' and body->>'review'='pending');

create policy meta_read on public.baton_workspace for select to baton_runtime using(baton_private.viewer_role() in ('reviewer','successor','coordinator','leaver'));
create policy meta_write on public.baton_workspace for update to baton_runtime using(baton_private.viewer_role()='reviewer') with check(baton_private.viewer_role()='reviewer');
create policy versions_read on public.baton_versions for select to baton_runtime using(baton_private.viewer_role() in ('reviewer','successor','coordinator','leaver'));
create policy versions_insert on public.baton_versions for insert to baton_runtime with check(baton_private.viewer_role()='reviewer');
create policy index_read on public.baton_claim_index for select to baton_runtime using(revision>0 or baton_private.viewer_role() in ('reviewer','leaver'));
create policy index_write on public.baton_claim_index for all to baton_runtime using(baton_private.viewer_role()='reviewer' and revision=0) with check(baton_private.viewer_role()='reviewer');
create policy audit_read on public.baton_audit for select to baton_runtime using(baton_private.viewer_role()='reviewer');
create policy audit_append on public.baton_audit for insert to baton_runtime with check(baton_private.viewer_role() in ('reviewer','successor','coordinator','leaver'));
create policy ack_read on public.baton_acknowledgements for select to baton_runtime using(baton_private.viewer_role()='reviewer' or body->>'role'=baton_private.viewer_role());
create policy ack_append on public.baton_acknowledgements for insert to baton_runtime with check(body->>'role'=baton_private.viewer_role());
create policy actions_read on public.baton_actions for select to baton_runtime using(exists(select 1 from public.baton_claims c where c.id=claim_id and c.revision=baton_actions.revision));
create policy actions_insert on public.baton_actions for insert to baton_runtime with check(baton_private.viewer_role()='reviewer' and exists(select 1 from public.baton_claims c where c.id=claim_id and c.revision=baton_actions.revision));
create policy actions_update on public.baton_actions for update to baton_runtime
using(baton_private.viewer_role() in ('reviewer','successor','coordinator') and exists(select 1 from public.baton_claims c where c.id=claim_id and c.revision=baton_actions.revision))
with check(baton_private.viewer_role() in ('reviewer','successor','coordinator') and exists(select 1 from public.baton_claims c where c.id=claim_id and c.revision=baton_actions.revision));
create policy questions_read on public.baton_questions for select to baton_runtime using(exists(select 1 from public.baton_claims c where c.id=claim_id and c.revision=0));
create policy questions_write on public.baton_questions for all to baton_runtime using(baton_private.viewer_role()='reviewer') with check(baton_private.viewer_role()='reviewer');
create policy cache_reviewer on baton_private.cache for all to baton_runtime using(baton_private.viewer_role()='reviewer') with check(baton_private.viewer_role()='reviewer');
-- Credentials never enter the Data API. Only the server's auth transaction can access these rows.
create policy credentials_backend on baton_private.users for all to baton_runtime using(current_setting('baton.auth_phase',true)='1') with check(current_setting('baton.auth_phase',true)='1');
create policy sessions_backend on baton_private.sessions for all to baton_runtime using(current_setting('baton.auth_phase',true)='1') with check(current_setting('baton.auth_phase',true)='1');
create policy accounts_backend on baton_private.accounts for all to baton_runtime using(current_setting('baton.auth_phase',true)='1') with check(current_setting('baton.auth_phase',true)='1');
create policy attempts_backend on baton_private.login_attempts for all to baton_runtime using(current_setting('baton.auth_phase',true)='1') with check(current_setting('baton.auth_phase',true)='1');

revoke all on all tables in schema baton_private from public, anon, authenticated;
revoke all on public.baton_workspace,public.baton_sources,public.baton_versions,public.baton_claim_index,public.baton_claims,public.baton_audit,public.baton_acknowledgements,public.baton_actions,public.baton_questions from public,anon,authenticated;
grant select,insert,update,delete on all tables in schema baton_private to baton_runtime;
grant select,insert,update,delete on public.baton_workspace,public.baton_sources,public.baton_claim_index,public.baton_claims,public.baton_actions,public.baton_questions to baton_runtime;
grant select,insert on public.baton_versions,public.baton_audit,public.baton_acknowledgements to baton_runtime;
