-- Existing records and invitations remain in project 1.
create table baton_private.projects (
  id integer primary key check (id > 0),
  name text not null
);
insert into baton_private.projects select id, body->>'project' from public.baton_workspace;

create table baton_private.memberships (
  workspace_id integer not null references baton_private.projects(id),
  account_id text not null references baton_private.accounts(id),
  role text not null check (role in ('reviewer','successor','coordinator','leaver')),
  active boolean not null default true,
  primary key (workspace_id, account_id)
);
create index baton_memberships_account_idx on baton_private.memberships(account_id, workspace_id) where active;
insert into baton_private.memberships select 1, id, role, active from baton_private.accounts;
alter table baton_private.invites add column workspace_id integer not null default 1 references baton_private.projects(id);

alter table baton_private.projects enable row level security;
alter table baton_private.projects force row level security;
alter table baton_private.memberships enable row level security;
alter table baton_private.memberships force row level security;
revoke all on baton_private.projects, baton_private.memberships from public, anon, authenticated;
grant select, insert on baton_private.projects to baton_runtime;
grant select, insert, update on baton_private.memberships to baton_runtime;
create policy projects_backend on baton_private.projects for all to baton_runtime
using ((select current_setting('baton.auth_phase', true)) = '1')
with check ((select current_setting('baton.auth_phase', true)) = '1');
create policy memberships_backend on baton_private.memberships for all to baton_runtime
using ((select current_setting('baton.auth_phase', true)) = '1')
with check ((select current_setting('baton.auth_phase', true)) = '1');

create function baton_private.workspace_scope() returns integer
language sql stable security invoker set search_path = ''
as $$ select coalesce(nullif(current_setting('baton.workspace_id', true), '')::integer, 1) $$;
revoke all on function baton_private.workspace_scope() from public;
grant execute on function baton_private.workspace_scope() to baton_runtime;

alter table public.baton_workspace drop constraint baton_workspace_id_check;
alter table public.baton_workspace add foreign key (id) references baton_private.projects(id);
create policy workspace_scope on public.baton_workspace as restrictive for all to baton_runtime
using (id = (select baton_private.workspace_scope()))
with check (id = (select baton_private.workspace_scope()));
create policy workspace_create on public.baton_workspace for insert to baton_runtime
with check ((select current_setting('baton.auth_phase', true)) = '1'
  and (select baton_private.viewer_role()) = 'reviewer');

-- Scope applies in addition to the existing role and source policies.
do $$
declare
  scoped record;
begin
  for scoped in
    select * from (values
      ('public','baton_sources','id'),
      ('public','baton_versions','number'),
      ('public','baton_claim_index','revision,id'),
      ('public','baton_claims','revision,id'),
      ('public','baton_audit','id'),
      ('public','baton_acknowledgements','id'),
      ('public','baton_actions','id'),
      ('public','baton_questions','id'),
      ('baton_private','cache','id')
    ) as entries(schema_name,table_name,key_columns)
  loop
    execute format('alter table %I.%I add column workspace_id integer not null default 1 references public.baton_workspace(id)',
      scoped.schema_name, scoped.table_name);
    execute format('alter table %I.%I alter column workspace_id set default baton_private.workspace_scope()',
      scoped.schema_name, scoped.table_name);
    execute format('alter table %I.%I drop constraint %I, add primary key (workspace_id,%s)',
      scoped.schema_name, scoped.table_name, scoped.table_name || '_pkey', scoped.key_columns);
    execute format('create policy workspace_scope on %I.%I as restrictive for all to baton_runtime
      using (workspace_id = (select baton_private.workspace_scope()))
      with check (workspace_id = (select baton_private.workspace_scope()))',
      scoped.schema_name, scoped.table_name);
  end loop;
end $$;

-- The existing early deployment can still write its workspace-1 cache during migration.
-- New project cache keys already incorporate independently generated source IDs.
create unique index baton_cache_legacy_id on baton_private.cache(id);

alter policy claim_update on public.baton_claims
using (revision = 0 and ((select baton_private.viewer_role()) = 'reviewer' or
  ((select baton_private.viewer_role()) = 'leaver' and body->>'status' = 'gap'
   and body->>'question_assignee_id' is null
   and not coalesce((select (w.body->>'sudden_exit')::boolean from public.baton_workspace w
                     where w.id = (select baton_private.workspace_scope())), true)
   and cardinality(evidence_ids) > 0
   and not exists (select 1 from unnest(evidence_ids) sid
                   where not exists (select 1 from public.baton_sources s where s.id = sid)))));

create policy assigned_gap_read on public.baton_claims for select to baton_runtime
using (revision = 0 and body->>'question_assignee_id' = (select current_setting('baton.viewer_id',true))
  and (select baton_private.viewer_role()) in ('reviewer','successor','coordinator','leaver')
  and cardinality(evidence_ids) > 0
  and not exists (select 1 from unnest(evidence_ids) sid
                  where not exists (select 1 from public.baton_sources s where s.id = sid)));

create policy assigned_gap_index on public.baton_claim_index for select to baton_runtime
using (revision = 0 and exists (
  select 1 from public.baton_claims c
  where c.revision = 0 and c.id = baton_claim_index.id
    and c.body->>'question_assignee_id' = (select current_setting('baton.viewer_id',true))
));

alter policy questions_read on public.baton_questions using (
  ((select baton_private.viewer_role()) = 'reviewer'
    or body->>'assignee_id' = (select current_setting('baton.viewer_id',true))
    or ((select baton_private.viewer_role()) = 'leaver' and body->>'assignee_id' is null and body->>'assignee' = 'leaver'))
  and exists (select 1 from public.baton_claims c where c.id = claim_id and c.revision = 0)
);
create policy named_question_answer on public.baton_questions for update to baton_runtime
using (body->>'assignee_id' = (select current_setting('baton.viewer_id',true))
  and exists (select 1 from public.baton_claims c where c.id = claim_id and c.revision = 0))
with check (body->>'assignee_id' = (select current_setting('baton.viewer_id',true))
  and exists (select 1 from public.baton_claims c where c.id = claim_id and c.revision = 0));
