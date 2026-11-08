-- Consolidate SELECT and mutation policies and cache request-level checks once per statement.
drop policy source_write on public.baton_sources;
create policy source_insert on public.baton_sources for insert to baton_runtime with check((select baton_private.viewer_role())='reviewer');
create policy source_update on public.baton_sources for update to baton_runtime using((select baton_private.viewer_role())='reviewer') with check((select baton_private.viewer_role())='reviewer');
create policy source_delete on public.baton_sources for delete to baton_runtime using((select baton_private.viewer_role())='reviewer');

drop policy index_write on public.baton_claim_index;
drop policy index_read on public.baton_claim_index;
create policy index_read on public.baton_claim_index for select to baton_runtime using((select baton_private.viewer_role()) in ('reviewer','successor','coordinator','leaver') and (revision>0 or (select baton_private.viewer_role()) in ('reviewer','leaver')));
create policy index_insert on public.baton_claim_index for insert to baton_runtime with check((select baton_private.viewer_role())='reviewer');
create policy index_delete on public.baton_claim_index for delete to baton_runtime using((select baton_private.viewer_role())='reviewer' and revision=0);

drop policy claim_write on public.baton_claims;
drop policy leaver_answer on public.baton_claims;
drop policy claim_read on public.baton_claims;
create policy claim_read on public.baton_claims for select to baton_runtime using(
 ((select baton_private.viewer_role())='reviewer' and revision=0) or
 ((select baton_private.viewer_role()) in ('reviewer','successor','coordinator','leaver') and
 (revision>0 or (select baton_private.viewer_role()) in ('reviewer','leaver')) and cardinality(evidence_ids)>0 and
 not exists(select 1 from unnest(evidence_ids) sid where not exists(select 1 from public.baton_sources s where s.id=sid)))
);
create policy claim_insert on public.baton_claims for insert to baton_runtime with check((select baton_private.viewer_role())='reviewer');
create policy claim_delete on public.baton_claims for delete to baton_runtime using((select baton_private.viewer_role())='reviewer' and revision=0);
create policy claim_update on public.baton_claims for update to baton_runtime
using(revision=0 and ((select baton_private.viewer_role())='reviewer' or
 ((select baton_private.viewer_role())='leaver' and body->>'status'='gap' and
 not coalesce((select (w.body->>'sudden_exit')::boolean from public.baton_workspace w where w.id=1),true) and
 not exists(select 1 from unnest(evidence_ids) sid where not exists(select 1 from public.baton_sources s where s.id=sid)))))
with check(revision=0 and ((select baton_private.viewer_role())='reviewer' or
 ((select baton_private.viewer_role())='leaver' and body->>'status'='attested' and body->>'review'='pending' and
 not exists(select 1 from unnest(evidence_ids) sid where not exists(select 1 from public.baton_sources s where s.id=sid)))));

drop policy questions_write on public.baton_questions;
drop policy question_answer_metadata on public.baton_questions;
create policy question_insert on public.baton_questions for insert to baton_runtime with check((select baton_private.viewer_role())='reviewer');
create policy question_delete on public.baton_questions for delete to baton_runtime using((select baton_private.viewer_role())='reviewer');
create policy question_update on public.baton_questions for update to baton_runtime
using((select baton_private.viewer_role())='reviewer' or ((select baton_private.viewer_role())='leaver' and body->>'assignee'='leaver' and exists(select 1 from public.baton_claims c where c.id=claim_id and c.revision=0)))
with check((select baton_private.viewer_role())='reviewer' or ((select baton_private.viewer_role())='leaver' and body->>'assignee'='leaver'));

alter policy credentials_backend on baton_private.users using((select current_setting('baton.auth_phase',true))='1') with check((select current_setting('baton.auth_phase',true))='1');
alter policy sessions_backend on baton_private.sessions using((select current_setting('baton.auth_phase',true))='1') with check((select current_setting('baton.auth_phase',true))='1');
alter policy accounts_backend on baton_private.accounts using((select current_setting('baton.auth_phase',true))='1') with check((select current_setting('baton.auth_phase',true))='1');
alter policy attempts_backend on baton_private.login_attempts using((select current_setting('baton.auth_phase',true))='1') with check((select current_setting('baton.auth_phase',true))='1');
alter policy invites_backend on baton_private.invites using((select current_setting('baton.auth_phase',true))='1') with check((select current_setting('baton.auth_phase',true))='1');

alter policy ack_read on public.baton_acknowledgements using((select baton_private.viewer_role())='reviewer' or coalesce(body->>'user_id',body->>'role')=(select current_setting('baton.viewer_id',true)));
alter policy ack_append on public.baton_acknowledgements with check(body->>'role'=(select baton_private.viewer_role()) and coalesce(body->>'user_id',body->>'role')=(select current_setting('baton.viewer_id',true)));
alter policy actions_update on public.baton_actions
using((select baton_private.viewer_role()) in ('reviewer','successor','coordinator') and
 ((select baton_private.viewer_role())='reviewer' or lower(body->>'owner')=lower((select current_setting('baton.viewer_name',true)))) and
 exists(select 1 from public.baton_claims c where c.id=claim_id and c.revision=baton_actions.revision))
with check((select baton_private.viewer_role()) in ('reviewer','successor','coordinator') and
 ((select baton_private.viewer_role())='reviewer' or lower(body->>'owner')=lower((select current_setting('baton.viewer_name',true)))) and
 exists(select 1 from public.baton_claims c where c.id=claim_id and c.revision=baton_actions.revision));
