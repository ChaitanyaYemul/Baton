create table baton_private.invites (
 token text primary key, username text not null, role text not null check(role in ('reviewer','successor','coordinator','leaver')),
 name text not null, expires double precision not null, used integer not null default 0
);
alter table baton_private.invites enable row level security;
alter table baton_private.invites force row level security;
revoke all on baton_private.invites from public,anon,authenticated;
grant select,insert,update,delete on baton_private.invites to baton_runtime;
create policy invites_backend on baton_private.invites for all to baton_runtime
using(current_setting('baton.auth_phase',true)='1') with check(current_setting('baton.auth_phase',true)='1');
create policy question_answer_metadata on public.baton_questions for update to baton_runtime
using(baton_private.viewer_role()='leaver' and body->>'assignee'='leaver' and exists(select 1 from public.baton_claims c where c.id=claim_id and c.revision=0))
with check(baton_private.viewer_role()='leaver' and body->>'assignee'='leaver');
