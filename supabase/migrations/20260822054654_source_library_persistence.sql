-- Proofline / MagicFin authenticated persistence foundation.
-- This migration intentionally stores metadata only. Raw source bytes belong in the
-- private Storage bucket created below.

create table public.analysis_sessions (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  state text not null default 'OPEN'
    check (state in ('OPEN', 'PROCESSING', 'DELETING', 'DELETED')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_activity_at timestamptz not null default now(),
  idle_expires_at timestamptz not null,
  absolute_expires_at timestamptz not null,
  provider_sent boolean not null default false,
  provider_sent_at timestamptz,
  deletion_requested_at timestamptz,
  deletion_completed_at timestamptz,
  deletion_status text
    check (deletion_status is null or deletion_status in ('complete', 'partial')),
  unique (id, owner_id),
  check (idle_expires_at <= absolute_expires_at),
  check (provider_sent = (provider_sent_at is not null)),
  check (
    (state not in ('DELETING', 'DELETED') and deletion_requested_at is null)
    or (state in ('DELETING', 'DELETED') and deletion_requested_at is not null)
  ),
  check (
    (state <> 'DELETED' and deletion_completed_at is null)
    or (state = 'DELETED' and deletion_completed_at is not null)
  )
);

create table public.documents (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null,
  owner_id uuid not null,
  role text not null check (role in ('report_pdf', 'workbook')),
  display_name text not null check (char_length(display_name) between 1 and 255),
  canonical_type text not null check (
    canonical_type in (
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
  ),
  byte_count bigint not null check (byte_count between 1 and 20971520),
  storage_object_path text not null unique,
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  validation_status text not null default 'Checking'
    check (validation_status in ('Checking', 'Ready', 'Needs attention')),
  validated_at timestamptz,
  uploaded_at timestamptz not null default now(),
  expires_at timestamptz not null,
  unique (id, owner_id, session_id),
  unique (session_id, role),
  foreign key (session_id, owner_id)
    references public.analysis_sessions(id, owner_id) on delete cascade,
  check (storage_object_path = owner_id::text || '/' || session_id::text || '/' || id::text),
  check (
    (validation_status = 'Checking' and validated_at is null)
    or (validation_status in ('Ready', 'Needs attention') and validated_at is not null)
  )
);

create table public.source_spans (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null,
  document_id uuid not null,
  owner_id uuid not null,
  page_number integer check (page_number is null or page_number > 0),
  sheet_name text check (sheet_name is null or char_length(sheet_name) between 1 and 128),
  cell_range text check (cell_range is null or char_length(cell_range) between 1 and 64),
  start_offset integer check (start_offset is null or start_offset >= 0),
  end_offset integer check (end_offset is null or end_offset >= start_offset),
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  foreign key (document_id, owner_id, session_id)
    references public.documents(id, owner_id, session_id) on delete cascade,
  check (
    (page_number is not null and sheet_name is null and cell_range is null)
    or (page_number is null and sheet_name is not null)
  )
);

create table public.analysis_snapshots (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null,
  owner_id uuid not null,
  schema_version text not null,
  status text not null check (status in ('queued', 'processing', 'complete', 'failed')),
  evidence_chain_sha256 text not null check (evidence_chain_sha256 ~ '^[0-9a-f]{64}$'),
  source_span_count integer not null default 0 check (source_span_count >= 0),
  provider_sent boolean not null default false,
  provider_sent_at timestamptz,
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  foreign key (session_id, owner_id)
    references public.analysis_sessions(id, owner_id) on delete cascade,
  check (provider_sent = (provider_sent_at is not null)),
  check ((status = 'complete') = (completed_at is not null))
);

-- Receipts are retained briefly after session metadata is deleted. Authenticated users can
-- read their own receipt; only reviewed backend orchestration writes or prunes this table.
create table public.deletion_receipts (
  receipt_id uuid primary key default gen_random_uuid(),
  session_id uuid not null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  receipt_version text not null default '1.0.0',
  scope_version text not null default 'supabase-source-library-v1',
  requested_at timestamptz not null,
  completed_at timestamptz not null,
  status text not null check (status in ('complete', 'partial')),
  source_files_removed integer not null default 0 check (source_files_removed >= 0),
  source_bytes_removed bigint not null default 0 check (source_bytes_removed >= 0),
  source_spans_removed integer not null default 0 check (source_spans_removed >= 0),
  snapshots_removed integer not null default 0 check (snapshots_removed >= 0),
  metadata_rows_removed integer not null default 0 check (metadata_rows_removed >= 0),
  storage_objects_gone boolean not null,
  provider_sent boolean not null,
  claim text not null default
    'Deletion attempt scoped to MagicFin application-managed database rows and private Storage objects.',
  exclusions text[] not null default array[
    'immutable fixtures',
    'user/browser downloads',
    'infrastructure backups/logs',
    'third-party retention'
  ]::text[],
  retained_until timestamptz not null,
  unique (owner_id, session_id),
  check (
    retained_until > completed_at
    and retained_until <= completed_at + interval '2 hours'
  )
);

create index analysis_sessions_owner_expiry_idx
  on public.analysis_sessions (owner_id, idle_expires_at, absolute_expires_at);
create index documents_owner_session_idx on public.documents (owner_id, session_id);
create index source_spans_owner_session_idx on public.source_spans (owner_id, session_id);
create index analysis_snapshots_owner_session_idx
  on public.analysis_snapshots (owner_id, session_id);
create index deletion_receipts_retention_idx on public.deletion_receipts (retained_until);

alter table public.analysis_sessions enable row level security;
alter table public.documents enable row level security;
alter table public.source_spans enable row level security;
alter table public.analysis_snapshots enable row level security;
alter table public.deletion_receipts enable row level security;

alter table public.analysis_sessions force row level security;
alter table public.documents force row level security;
alter table public.source_spans force row level security;
alter table public.analysis_snapshots force row level security;
alter table public.deletion_receipts force row level security;

revoke all on table public.analysis_sessions from public, anon, authenticated;
revoke all on table public.documents from public, anon, authenticated;
revoke all on table public.source_spans from public, anon, authenticated;
revoke all on table public.analysis_snapshots from public, anon, authenticated;
revoke all on table public.deletion_receipts from public, anon, authenticated;

grant usage on schema public to authenticated;
grant select on public.analysis_sessions to authenticated;
grant select on public.documents to authenticated;
grant select on public.source_spans to authenticated;
grant select on public.analysis_snapshots to authenticated;
grant select on public.deletion_receipts to authenticated;

grant select, insert, update, delete on
  public.analysis_sessions,
  public.documents,
  public.source_spans,
  public.analysis_snapshots,
  public.deletion_receipts
to service_role;

create policy analysis_sessions_select_own
  on public.analysis_sessions for select to authenticated
  using (
    (select auth.uid()) = owner_id
    and not coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false)
  );

create policy documents_select_own
  on public.documents for select to authenticated
  using (
    (select auth.uid()) = owner_id
    and not coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false)
  );

create policy source_spans_select_own
  on public.source_spans for select to authenticated
  using (
    (select auth.uid()) = owner_id
    and not coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false)
  );

create policy analysis_snapshots_select_own
  on public.analysis_snapshots for select to authenticated
  using (
    (select auth.uid()) = owner_id
    and not coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false)
  );

create policy deletion_receipts_select_own
  on public.deletion_receipts for select to authenticated
  using (
    (select auth.uid()) = owner_id
    and not coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false)
  );

-- Authenticated callers cannot write lifecycle tables directly. These narrowly granted RPCs
-- derive ownership, clocks, expiry, initial validation state and object paths inside Postgres.
-- SECURITY DEFINER is required because the underlying tables are deliberately read-only to the
-- authenticated role. Every relation is schema-qualified and search_path is empty.
create function public.create_analysis_session()
returns public.analysis_sessions
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller uuid := auth.uid();
  instant timestamptz := clock_timestamp();
  created public.analysis_sessions;
begin
  if caller is null
    or coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false)
  then
    raise exception using errcode = '42501', message = 'AUTHENTICATED_USER_REQUIRED';
  end if;

  insert into public.analysis_sessions (
    owner_id,
    state,
    created_at,
    updated_at,
    last_activity_at,
    idle_expires_at,
    absolute_expires_at
  ) values (
    caller,
    'OPEN',
    instant,
    instant,
    instant,
    instant + interval '30 minutes',
    instant + interval '2 hours'
  ) returning * into created;
  return created;
end;
$$;

create function public.touch_analysis_session(target_session_id uuid)
returns public.analysis_sessions
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller uuid := auth.uid();
  instant timestamptz := clock_timestamp();
  touched public.analysis_sessions;
begin
  if caller is null
    or coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false)
  then
    raise exception using errcode = '42501', message = 'AUTHENTICATED_USER_REQUIRED';
  end if;

  update public.analysis_sessions
  set
    updated_at = instant,
    last_activity_at = instant,
    idle_expires_at = least(instant + interval '30 minutes', absolute_expires_at)
  where id = target_session_id
    and owner_id = caller
    and state = 'OPEN'
    and instant < idle_expires_at
    and instant < absolute_expires_at
  returning * into touched;
  if touched.id is null then
    raise exception using errcode = 'P0001', message = 'SESSION_NOT_AVAILABLE';
  end if;
  return touched;
end;
$$;

create function public.register_source_document(
  target_session_id uuid,
  target_document_id uuid,
  document_role text,
  document_display_name text,
  document_canonical_type text,
  document_byte_count bigint,
  document_content_sha256 text
)
returns public.documents
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller uuid := auth.uid();
  instant timestamptz := clock_timestamp();
  session_row public.analysis_sessions;
  created public.documents;
begin
  if caller is null
    or coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false)
  then
    raise exception using errcode = '42501', message = 'AUTHENTICATED_USER_REQUIRED';
  end if;

  select * into session_row
  from public.analysis_sessions
  where id = target_session_id
    and owner_id = caller
    and state = 'OPEN'
    and instant < idle_expires_at
    and instant < absolute_expires_at
  for update;
  if session_row.id is null then
    raise exception using errcode = 'P0001', message = 'SESSION_NOT_AVAILABLE';
  end if;

  insert into public.documents (
    id,
    session_id,
    owner_id,
    role,
    display_name,
    canonical_type,
    byte_count,
    storage_object_path,
    content_sha256,
    validation_status,
    validated_at,
    uploaded_at,
    expires_at
  ) values (
    target_document_id,
    target_session_id,
    caller,
    document_role,
    document_display_name,
    document_canonical_type,
    document_byte_count,
    caller::text || '/' || target_session_id::text || '/' || target_document_id::text,
    document_content_sha256,
    'Checking',
    null,
    instant,
    session_row.absolute_expires_at
  ) returning * into created;
  return created;
end;
$$;

create function public.request_analysis_session_deletion(target_session_id uuid)
returns public.analysis_sessions
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller uuid := auth.uid();
  instant timestamptz := clock_timestamp();
  requested public.analysis_sessions;
begin
  if caller is null
    or coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false)
  then
    raise exception using errcode = '42501', message = 'AUTHENTICATED_USER_REQUIRED';
  end if;

  update public.analysis_sessions
  set
    state = 'DELETING',
    updated_at = instant,
    deletion_requested_at = instant
  where id = target_session_id
    and owner_id = caller
    and state in ('OPEN', 'PROCESSING')
  returning * into requested;
  if requested.id is null then
    raise exception using errcode = 'P0001', message = 'SESSION_NOT_AVAILABLE';
  end if;
  return requested;
end;
$$;

revoke execute on function public.create_analysis_session() from public, anon;
revoke execute on function public.touch_analysis_session(uuid) from public, anon;
revoke execute on function public.register_source_document(uuid, uuid, text, text, text, bigint, text)
  from public, anon;
revoke execute on function public.request_analysis_session_deletion(uuid) from public, anon;

grant execute on function public.create_analysis_session() to authenticated;
grant execute on function public.touch_analysis_session(uuid) to authenticated;
grant execute on function public.register_source_document(uuid, uuid, text, text, text, bigint, text)
  to authenticated;
grant execute on function public.request_analysis_session_deletion(uuid) to authenticated;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'proofline-source-library',
  'proofline-source-library',
  false,
  20971520,
  array[
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  ]
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

create policy source_objects_select_own
  on storage.objects for select to authenticated
  using (
    bucket_id = 'proofline-source-library'
    and owner_id = (select auth.uid())::text
    and not coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false)
    and (storage.foldername(name))[1] = (select auth.uid())::text
    and array_length(storage.foldername(name), 1) = 2
    and (storage.foldername(name))[2] ~
      '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    and storage.filename(name) ~
      '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    and exists (
      select 1
      from public.documents document
      where document.owner_id = (select auth.uid())
        and document.session_id::text = (storage.foldername(name))[2]
        and document.id::text = storage.filename(name)
        and document.storage_object_path = name
    )
  );
create policy source_objects_insert_own
  on storage.objects for insert to authenticated
  with check (
    bucket_id = 'proofline-source-library'
    and owner_id = (select auth.uid())::text
    and not coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false)
    and (storage.foldername(name))[1] = (select auth.uid())::text
    and array_length(storage.foldername(name), 1) = 2
    and (storage.foldername(name))[2] ~
      '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    and storage.filename(name) ~
      '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    and exists (
      select 1
      from public.documents document
      where document.owner_id = (select auth.uid())
        and document.session_id::text = (storage.foldername(name))[2]
        and document.id::text = storage.filename(name)
        and document.storage_object_path = name
        and document.validation_status = 'Checking'
    )
  );
create policy source_objects_update_own
  on storage.objects for update to authenticated
  using (
    bucket_id = 'proofline-source-library'
    and owner_id = (select auth.uid())::text
    and not coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false)
    and (storage.foldername(name))[1] = (select auth.uid())::text
    and array_length(storage.foldername(name), 1) = 2
    and (storage.foldername(name))[2] ~
      '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    and storage.filename(name) ~
      '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    and exists (
      select 1
      from public.documents document
      where document.owner_id = (select auth.uid())
        and document.session_id::text = (storage.foldername(name))[2]
        and document.id::text = storage.filename(name)
        and document.storage_object_path = name
        and document.validation_status = 'Checking'
    )
  )
  with check (
    bucket_id = 'proofline-source-library'
    and owner_id = (select auth.uid())::text
    and not coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false)
    and (storage.foldername(name))[1] = (select auth.uid())::text
    and array_length(storage.foldername(name), 1) = 2
    and (storage.foldername(name))[2] ~
      '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    and storage.filename(name) ~
      '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    and exists (
      select 1
      from public.documents document
      where document.owner_id = (select auth.uid())
        and document.session_id::text = (storage.foldername(name))[2]
        and document.id::text = storage.filename(name)
        and document.storage_object_path = name
        and document.validation_status = 'Checking'
    )
  );
create policy source_objects_delete_own
  on storage.objects for delete to authenticated
  using (
    bucket_id = 'proofline-source-library'
    and owner_id = (select auth.uid())::text
    and not coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false)
    and (storage.foldername(name))[1] = (select auth.uid())::text
    and array_length(storage.foldername(name), 1) = 2
    and (storage.foldername(name))[2] ~
      '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    and storage.filename(name) ~
      '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    and exists (
      select 1
      from public.documents document
      where document.owner_id = (select auth.uid())
        and document.session_id::text = (storage.foldername(name))[2]
        and document.id::text = storage.filename(name)
        and document.storage_object_path = name
        and (
          document.validation_status = 'Checking'
          or exists (
            select 1
            from public.analysis_sessions session
            where session.id = document.session_id
              and session.owner_id = document.owner_id
              and session.state = 'DELETING'
          )
        )
    )
  );
