-- Run against a disposable local Supabase database after `supabase db reset`:
--   psql postgresql://postgres:postgres@127.0.0.1:54322/postgres \
--     -v ON_ERROR_STOP=1 -f supabase/tests/source_library_rls.sql
-- The transaction is always rolled back.

begin;

insert into auth.users (
  id, aud, role, email, encrypted_password, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
)
values
  (
    '10000000-0000-4000-8000-000000000001', 'authenticated', 'authenticated',
    'source-a@example.invalid', '', '{}'::jsonb, '{}'::jsonb, now(), now()
  ),
  (
    '20000000-0000-4000-8000-000000000002', 'authenticated', 'authenticated',
    'source-b@example.invalid', '', '{}'::jsonb, '{}'::jsonb, now(), now()
  )
on conflict (id) do nothing;

set local role authenticated;
select set_config('request.jwt.claim.sub', '10000000-0000-4000-8000-000000000001', true);
select set_config(
  'request.jwt.claims',
  '{"sub":"10000000-0000-4000-8000-000000000001","role":"authenticated"}',
  true
);

insert into public.analysis_sessions (
  id, owner_id, idle_expires_at, absolute_expires_at
)
values (
  '11000000-0000-4000-8000-000000000001',
  '10000000-0000-4000-8000-000000000001',
  now() + interval '30 minutes',
  now() + interval '2 hours'
);

reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub', '20000000-0000-4000-8000-000000000002', true);
select set_config(
  'request.jwt.claims',
  '{"sub":"20000000-0000-4000-8000-000000000002","role":"authenticated"}',
  true
);

insert into public.analysis_sessions (
  id, owner_id, idle_expires_at, absolute_expires_at
)
values (
  '22000000-0000-4000-8000-000000000002',
  '20000000-0000-4000-8000-000000000002',
  now() + interval '30 minutes',
  now() + interval '2 hours'
);

insert into public.documents (
  id, session_id, owner_id, role, display_name, canonical_type, byte_count,
  storage_object_path, content_sha256, validation_status, expires_at
)
values (
  '23000000-0000-4000-8000-000000000002',
  '22000000-0000-4000-8000-000000000002',
  '20000000-0000-4000-8000-000000000002',
  'report_pdf',
  'report.pdf',
  'application/pdf',
  12,
  '20000000-0000-4000-8000-000000000002/22000000-0000-4000-8000-000000000002/23000000-0000-4000-8000-000000000002',
  repeat('b', 64),
  'Ready',
  now() + interval '30 minutes'
);

insert into storage.objects (bucket_id, name, owner_id)
values (
  'proofline-source-library',
  '20000000-0000-4000-8000-000000000002/22000000-0000-4000-8000-000000000002/23000000-0000-4000-8000-000000000002',
  '20000000-0000-4000-8000-000000000002'
);

reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub', '10000000-0000-4000-8000-000000000001', true);
select set_config(
  'request.jwt.claims',
  '{"sub":"10000000-0000-4000-8000-000000000001","role":"authenticated"}',
  true
);

do $$
declare
  visible_count integer;
  removed_count integer;
begin
  select count(*) into visible_count
  from public.analysis_sessions
  where id = '22000000-0000-4000-8000-000000000002';
  if visible_count <> 0 then
    raise exception 'RLS failure: user A can read user B session';
  end if;

  select count(*) into visible_count
  from public.documents
  where id = '23000000-0000-4000-8000-000000000002';
  if visible_count <> 0 then
    raise exception 'RLS failure: user A can read user B document';
  end if;

  select count(*) into visible_count
  from storage.objects
  where bucket_id = 'proofline-source-library'
    and name like '20000000-0000-4000-8000-000000000002/%';
  if visible_count <> 0 then
    raise exception 'RLS failure: user A can read user B object';
  end if;

  delete from public.analysis_sessions
  where id = '22000000-0000-4000-8000-000000000002';
  get diagnostics removed_count = row_count;
  if removed_count <> 0 then
    raise exception 'RLS failure: user A deleted user B session';
  end if;

  delete from storage.objects
  where bucket_id = 'proofline-source-library'
    and name like '20000000-0000-4000-8000-000000000002/%';
  get diagnostics removed_count = row_count;
  if removed_count <> 0 then
    raise exception 'RLS failure: user A deleted user B object';
  end if;
end
$$;

reset role;

do $$
begin
  if not exists (
    select 1 from public.analysis_sessions
    where id = '22000000-0000-4000-8000-000000000002'
  ) then
    raise exception 'cross-user session delete unexpectedly persisted';
  end if;
  if not exists (
    select 1 from storage.objects
    where bucket_id = 'proofline-source-library'
      and name like '20000000-0000-4000-8000-000000000002/%'
  ) then
    raise exception 'cross-user object delete unexpectedly persisted';
  end if;
end
$$;

rollback;
