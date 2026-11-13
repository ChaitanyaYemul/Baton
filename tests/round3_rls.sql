-- Execute only against a disposable database after applying all migrations.
begin;
set local role baton_runtime;
select set_config('baton.auth_phase','1',true);
insert into baton_private.projects values (31001,'Project A'), (31002,'Project B');
select set_config('baton.viewer_role','reviewer',true);
select set_config('baton.workspace_id','31001',true);
insert into public.baton_workspace values (31001,'{"project":"Project A","sudden_exit":false}');
insert into public.baton_sources(id,body) values ('shared-id','{"id":"shared-id","access":"core","text":"project-a-only"}');
insert into public.baton_versions(number,body) values (1,'{"number":1,"project":"Project A"}');

select set_config('baton.workspace_id','31002',true);
insert into public.baton_workspace values (31002,'{"project":"Project B","sudden_exit":false}');
insert into public.baton_sources(id,body) values ('shared-id','{"id":"shared-id","access":"core","text":"project-b-only"}');
insert into public.baton_versions(number,body) values (1,'{"number":1,"project":"Project B"}');
insert into public.baton_claims(revision,id,body,evidence_ids) values
  (0,'assigned-gap','{"id":"assigned-gap","status":"gap","review":"pending","question_assignee_id":"member-b","evidence":[{"source_id":"shared-id"}]}',array['shared-id']);
insert into public.baton_claim_index(revision,id) values (0,'assigned-gap');
insert into public.baton_questions(id,claim_id,body) values
  ('question-b','assigned-gap','{"assignee":"reviewer","assignee_id":"member-b"}');

select set_config('baton.auth_phase','0',true);
do $$
begin
  if (select count(*) from public.baton_sources) <> 1
    or exists(select 1 from public.baton_sources where body->>'text' = 'project-a-only')
    or exists(select 1 from public.baton_versions where body->>'project' = 'Project A') then
    raise exception 'Cross-project visibility';
  end if;
  begin
    insert into public.baton_sources(id,body,workspace_id)
    values ('wrong-project','{"id":"wrong-project","access":"core"}',31001);
    raise exception 'Cross-project write succeeded';
  exception when insufficient_privilege then null;
  end;
end $$;

select set_config('baton.viewer_role','successor',true);
select set_config('baton.viewer_id','member-b',true);
do $$
begin
  if (select count(*) from public.baton_questions) <> 1
    or (select count(*) from public.baton_claim_index where id = 'assigned-gap') <> 1 then
    raise exception 'Assigned question was hidden';
  end if;
  update public.baton_questions set body = body || '{"answers":[{"text":"Recorded answer"}]}'::jsonb
    where id = 'question-b';
  if not found then raise exception 'Assigned answer write was denied'; end if;
end $$;

select set_config('baton.viewer_id','other-member',true);
do $$
begin
  if exists(select 1 from public.baton_questions)
    or exists(select 1 from public.baton_claims where id = 'assigned-gap') then
    raise exception 'Named question visible to an unrelated member';
  end if;
end $$;

select set_config('baton.viewer_role','reviewer',true);
update public.baton_sources set body = body || '{"access":"leads"}'::jsonb where id = 'shared-id';
select set_config('baton.viewer_role','successor',true);
select set_config('baton.viewer_id','member-b',true);
do $$
begin
  if exists(select 1 from public.baton_questions)
    or exists(select 1 from public.baton_claims where id = 'assigned-gap') then
    raise exception 'Question or evidence still visible after source access changed';
  end if;
end $$;
rollback;
