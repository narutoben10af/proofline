-- Run against a disposable local Supabase database after `supabase db reset`:
--   psql postgresql://postgres:postgres@127.0.0.1:54322/postgres \
--     -v ON_ERROR_STOP=1 -f supabase/tests/source_library_rls.sql
-- The transaction is always rolled back. No production project is contacted.

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
  ),
  (
    '30000000-0000-4000-8000-000000000003', 'authenticated', 'authenticated',
    'anonymous-user@example.invalid', '', '{}'::jsonb, '{}'::jsonb, now(), now()
  )
on conflict (id) do nothing;

-- The unauthenticated Data API role has neither table access nor RPC execution.
set local role anon;
do $$
begin
  begin
    perform 1 from public.analysis_sessions;
    raise exception 'anon role reached private metadata';
  exception
    when insufficient_privilege then null;
  end;
  begin
    perform public.create_analysis_session();
    raise exception 'anon role executed lifecycle RPC';
  exception
    when insufficient_privilege then null;
  end;
end
$$;

-- An anonymous Supabase Auth identity still assumes `authenticated`; reject it explicitly.
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub', '30000000-0000-4000-8000-000000000003', true);
select set_config(
  'request.jwt.claims',
  '{"sub":"30000000-0000-4000-8000-000000000003","role":"authenticated","is_anonymous":true}',
  true
);
do $$
begin
  if exists (select 1 from public.analysis_sessions) then
    raise exception 'anonymous Auth user reached private metadata';
  end if;
  begin
    perform public.create_analysis_session();
    raise exception 'anonymous Auth user created a session';
  exception
    when insufficient_privilege then null;
  end;
end
$$;

-- User A: legitimate INSERT/UPDATE occur through RPCs, while direct trust-field writes fail.
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub', '10000000-0000-4000-8000-000000000001', true);
select set_config(
  'request.jwt.claims',
  '{"sub":"10000000-0000-4000-8000-000000000001","role":"authenticated","is_anonymous":false}',
  true
);

do $$
declare
  created_session public.analysis_sessions;
  touched_session public.analysis_sessions;
  created_document public.documents;
  expected_path text;
  changed integer;
begin
  created_session := public.create_analysis_session();
  if created_session.owner_id <> '10000000-0000-4000-8000-000000000001'
    or created_session.state <> 'OPEN'
    or created_session.idle_expires_at > created_session.created_at + interval '30 minutes 1 second'
    or created_session.absolute_expires_at > created_session.created_at + interval '2 hours 1 second'
  then
    raise exception 'same-user RPC insert failed';
  end if;
  perform set_config('proofline_test.session_a', created_session.id::text, true);

  touched_session := public.touch_analysis_session(created_session.id);
  if touched_session.owner_id <> created_session.owner_id
    or touched_session.absolute_expires_at <> created_session.absolute_expires_at
    or touched_session.last_activity_at < created_session.last_activity_at
    or touched_session.idle_expires_at > touched_session.absolute_expires_at
  then
    raise exception 'same-user RPC update failed';
  end if;

  expected_path := created_session.owner_id::text || '/' || created_session.id::text ||
    '/13000000-0000-4000-8000-000000000001';
  created_document := public.register_source_document(
    created_session.id,
    '13000000-0000-4000-8000-000000000001',
    'report_pdf',
    'report.pdf',
    'application/pdf',
    12,
    repeat('a', 64)
  );
  if created_document.owner_id <> created_session.owner_id
    or created_document.validation_status <> 'Checking'
    or created_document.validated_at is not null
    or created_document.storage_object_path <> expected_path
    or created_document.expires_at <> created_session.absolute_expires_at
  then
    raise exception 'same-user document RPC insert failed';
  end if;
  perform set_config('proofline_test.path_a', expected_path, true);

  begin
    insert into public.analysis_sessions (
      owner_id, state, idle_expires_at, absolute_expires_at
    ) values (
      '20000000-0000-4000-8000-000000000002',
      'PROCESSING',
      now() + interval '10 years',
      now() + interval '20 years'
    );
    raise exception 'spoofed owner insert succeeded';
  exception
    when insufficient_privilege then null;
  end;

  begin
    update public.analysis_sessions
    set absolute_expires_at = now() + interval '20 years'
    where id = created_session.id;
    get diagnostics changed = row_count;
    raise exception 'spoofed expiry update succeeded: % rows', changed;
  exception
    when insufficient_privilege then null;
  end;

  begin
    update public.documents
    set validation_status = 'Ready', validated_at = now()
    where id = created_document.id;
    get diagnostics changed = row_count;
    raise exception 'spoofed Ready update succeeded: % rows', changed;
  exception
    when insufficient_privilege then null;
  end;

  begin
    insert into public.documents (
      id, session_id, owner_id, role, display_name, canonical_type, byte_count,
      storage_object_path, content_sha256, validation_status, validated_at, expires_at
    ) values (
      '14000000-0000-4000-8000-000000000001',
      created_session.id,
      '20000000-0000-4000-8000-000000000002',
      'report_pdf',
      'spoof.pdf',
      'application/pdf',
      12,
      '../spoof',
      repeat('f', 64),
      'Ready',
      now(),
      now() + interval '20 years'
    );
    raise exception 'spoofed Ready insert succeeded';
  exception
    when insufficient_privilege then null;
  end;
end
$$;

-- Valid own Storage insert/select/update (the permissions needed by API upsert) succeeds.
insert into storage.objects (bucket_id, name, owner_id, metadata)
values (
  'proofline-source-library',
  current_setting('proofline_test.path_a'),
  '10000000-0000-4000-8000-000000000001',
  '{"version":1}'::jsonb
);
do $$
declare
  visible integer;
  changed integer;
begin
  select count(*) into visible
  from storage.objects
  where bucket_id = 'proofline-source-library'
    and name = current_setting('proofline_test.path_a');
  if visible <> 1 then
    raise exception 'same-user Storage insert failed';
  end if;

  update storage.objects
  set metadata = '{"version":2}'::jsonb
  where bucket_id = 'proofline-source-library'
    and name = current_setting('proofline_test.path_a');
  get diagnostics changed = row_count;
  if changed <> 1 then
    raise exception 'same-user Storage update failed';
  end if;

  begin
    insert into storage.objects (bucket_id, name, owner_id)
    values (
      'proofline-source-library',
      '10000000-0000-4000-8000-000000000001/' ||
        current_setting('proofline_test.session_a') ||
        '/../13000000-0000-4000-8000-000000000001',
      '10000000-0000-4000-8000-000000000001'
    );
    raise exception 'traversal object insert succeeded';
  exception
    when insufficient_privilege or check_violation then null;
  end;
end
$$;

-- User B cannot use the RPCs or Storage CRUD against A's owner/session/document.
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub', '20000000-0000-4000-8000-000000000002', true);
select set_config(
  'request.jwt.claims',
  '{"sub":"20000000-0000-4000-8000-000000000002","role":"authenticated","is_anonymous":false}',
  true
);
do $$
declare
  visible integer;
  changed integer;
begin
  begin
    perform public.register_source_document(
      current_setting('proofline_test.session_a')::uuid,
      '23000000-0000-4000-8000-000000000002',
      'report_pdf',
      'cross-user.pdf',
      'application/pdf',
      12,
      repeat('b', 64)
    );
    raise exception 'cross-user RPC insert succeeded';
  exception
    when raise_exception then
      if sqlerrm <> 'SESSION_NOT_AVAILABLE' then raise; end if;
  end;

  begin
    perform public.touch_analysis_session(current_setting('proofline_test.session_a')::uuid);
    raise exception 'cross-user RPC update succeeded';
  exception
    when raise_exception then
      if sqlerrm <> 'SESSION_NOT_AVAILABLE' then raise; end if;
  end;

  select count(*) into visible
  from storage.objects
  where bucket_id = 'proofline-source-library'
    and name = current_setting('proofline_test.path_a');
  if visible <> 0 then
    raise exception 'cross-user Storage CRUD succeeded: SELECT';
  end if;

  update storage.objects
  set metadata = '{"attacker":true}'::jsonb
  where bucket_id = 'proofline-source-library'
    and name = current_setting('proofline_test.path_a');
  get diagnostics changed = row_count;
  if changed <> 0 then
    raise exception 'cross-user Storage CRUD succeeded: UPDATE';
  end if;

  delete from storage.objects
  where bucket_id = 'proofline-source-library'
    and name = current_setting('proofline_test.path_a');
  get diagnostics changed = row_count;
  if changed <> 0 then
    raise exception 'cross-user Storage CRUD succeeded: DELETE';
  end if;

  begin
    insert into storage.objects (bucket_id, name, owner_id)
    values (
      'proofline-source-library',
      '20000000-0000-4000-8000-000000000002/' ||
        current_setting('proofline_test.session_a') ||
        '/13000000-0000-4000-8000-000000000001',
      '20000000-0000-4000-8000-000000000002'
    );
    raise exception 'cross-user Storage CRUD succeeded: INSERT';
  exception
    when insufficient_privilege then null;
  end;
end
$$;

-- User A may delete/recreate its own object while the server status is still Checking.
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub', '10000000-0000-4000-8000-000000000001', true);
select set_config(
  'request.jwt.claims',
  '{"sub":"10000000-0000-4000-8000-000000000001","role":"authenticated","is_anonymous":false}',
  true
);
do $$
declare
  changed integer;
begin
  delete from storage.objects
  where bucket_id = 'proofline-source-library'
    and name = current_setting('proofline_test.path_a');
  get diagnostics changed = row_count;
  if changed <> 1 then
    raise exception 'same-user Storage delete failed';
  end if;

  insert into storage.objects (bucket_id, name, owner_id, metadata)
  values (
    'proofline-source-library',
    current_setting('proofline_test.path_a'),
    '10000000-0000-4000-8000-000000000001',
    '{"version":3}'::jsonb
  );
end
$$;

-- The backend-only role authors validated state and the bounded receipt.
reset role;
set local role service_role;
do $$
declare
  changed integer;
begin
  update public.documents
  set validation_status = 'Ready', validated_at = now(), byte_count = 12,
      content_sha256 = repeat('a', 64)
  where id = '13000000-0000-4000-8000-000000000001';
  get diagnostics changed = row_count;
  if changed <> 1 then
    raise exception 'service-role Ready write failed';
  end if;

  insert into public.deletion_receipts (
    session_id,
    owner_id,
    requested_at,
    completed_at,
    status,
    storage_objects_gone,
    provider_sent,
    retained_until
  ) values (
    current_setting('proofline_test.session_a')::uuid,
    '10000000-0000-4000-8000-000000000001',
    now(),
    now(),
    'complete',
    true,
    false,
    now() + interval '2 hours'
  );
  if not exists (
    select 1 from public.deletion_receipts
    where session_id = current_setting('proofline_test.session_a')::uuid
  ) then
    raise exception 'service-role receipt write failed';
  end if;
end
$$;

-- Receipt reads are owner-only; authenticated writes remain prohibited.
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub', '20000000-0000-4000-8000-000000000002', true);
select set_config(
  'request.jwt.claims',
  '{"sub":"20000000-0000-4000-8000-000000000002","role":"authenticated","is_anonymous":false}',
  true
);
do $$
begin
  if exists (
    select 1 from public.deletion_receipts
    where session_id = current_setting('proofline_test.session_a')::uuid
  ) then
    raise exception 'cross-user receipt became visible';
  end if;
end
$$;

reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub', '10000000-0000-4000-8000-000000000001', true);
select set_config(
  'request.jwt.claims',
  '{"sub":"10000000-0000-4000-8000-000000000001","role":"authenticated","is_anonymous":false}',
  true
);
do $$
declare
  changed integer;
begin
  if not exists (
    select 1 from public.deletion_receipts
    where session_id = current_setting('proofline_test.session_a')::uuid
  ) then
    raise exception 'same-user receipt read failed';
  end if;

  begin
    insert into public.deletion_receipts (
      session_id, owner_id, requested_at, completed_at, status,
      storage_objects_gone, provider_sent, retained_until
    ) values (
      current_setting('proofline_test.session_a')::uuid,
      '10000000-0000-4000-8000-000000000001',
      now(), now(), 'complete', true, false, now() + interval '2 hours'
    );
    raise exception 'authenticated receipt write succeeded';
  exception
    when insufficient_privilege then null;
  end;

  update storage.objects
  set metadata = '{"post_validation_spoof":true}'::jsonb
  where bucket_id = 'proofline-source-library'
    and name = current_setting('proofline_test.path_a');
  get diagnostics changed = row_count;
  if changed <> 0 then
    raise exception 'Ready Storage upsert succeeded';
  end if;

  delete from storage.objects
  where bucket_id = 'proofline-source-library'
    and name = current_setting('proofline_test.path_a');
  get diagnostics changed = row_count;
  if changed <> 0 then
    raise exception 'Ready Storage delete succeeded';
  end if;
end
$$;

rollback;
