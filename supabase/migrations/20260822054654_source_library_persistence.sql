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
  deletion_requested_at timestamptz,
  deletion_completed_at timestamptz,
  deletion_status text
    check (deletion_status is null or deletion_status in ('complete', 'partial')),
  unique (id, owner_id),
  check (idle_expires_at <= absolute_expires_at),
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
  uploaded_at timestamptz not null default now(),
  expires_at timestamptz not null,
  unique (id, owner_id, session_id),
  unique (session_id, role),
  foreign key (session_id, owner_id)
    references public.analysis_sessions(id, owner_id) on delete cascade,
  check (storage_object_path = owner_id::text || '/' || session_id::text || '/' || id::text)
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
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  foreign key (session_id, owner_id)
    references public.analysis_sessions(id, owner_id) on delete cascade
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
    'Deleted from MagicFin application-managed database rows and private Storage objects.',
  exclusions text[] not null default array[
    'immutable fixtures',
    'user/browser downloads',
    'infrastructure backups/logs',
    'third-party retention'
  ]::text[],
  retained_until timestamptz not null,
  unique (owner_id, session_id),
  check (retained_until > completed_at)
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
grant select, delete on public.analysis_sessions to authenticated;
grant insert (
  id, owner_id, state, created_at, updated_at, last_activity_at,
  idle_expires_at, absolute_expires_at
) on public.analysis_sessions to authenticated;
grant update (state, updated_at, last_activity_at, idle_expires_at)
  on public.analysis_sessions to authenticated;

grant select, insert, delete on public.documents to authenticated;
grant update (display_name, validation_status, expires_at)
  on public.documents to authenticated;
grant select, insert, update, delete on public.source_spans to authenticated;
grant select, insert, update, delete on public.analysis_snapshots to authenticated;
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
  using ((select auth.uid()) = owner_id);
create policy analysis_sessions_insert_own
  on public.analysis_sessions for insert to authenticated
  with check ((select auth.uid()) = owner_id and provider_sent = false);
create policy analysis_sessions_update_own
  on public.analysis_sessions for update to authenticated
  using ((select auth.uid()) = owner_id)
  with check ((select auth.uid()) = owner_id);
create policy analysis_sessions_delete_own
  on public.analysis_sessions for delete to authenticated
  using ((select auth.uid()) = owner_id);

create policy documents_select_own
  on public.documents for select to authenticated
  using ((select auth.uid()) = owner_id);
create policy documents_insert_own
  on public.documents for insert to authenticated
  with check ((select auth.uid()) = owner_id);
create policy documents_update_own
  on public.documents for update to authenticated
  using ((select auth.uid()) = owner_id)
  with check ((select auth.uid()) = owner_id);
create policy documents_delete_own
  on public.documents for delete to authenticated
  using ((select auth.uid()) = owner_id);

create policy source_spans_select_own
  on public.source_spans for select to authenticated
  using ((select auth.uid()) = owner_id);
create policy source_spans_insert_own
  on public.source_spans for insert to authenticated
  with check ((select auth.uid()) = owner_id);
create policy source_spans_update_own
  on public.source_spans for update to authenticated
  using ((select auth.uid()) = owner_id)
  with check ((select auth.uid()) = owner_id);
create policy source_spans_delete_own
  on public.source_spans for delete to authenticated
  using ((select auth.uid()) = owner_id);

create policy analysis_snapshots_select_own
  on public.analysis_snapshots for select to authenticated
  using ((select auth.uid()) = owner_id);
create policy analysis_snapshots_insert_own
  on public.analysis_snapshots for insert to authenticated
  with check ((select auth.uid()) = owner_id and provider_sent = false);
create policy analysis_snapshots_update_own
  on public.analysis_snapshots for update to authenticated
  using ((select auth.uid()) = owner_id)
  with check ((select auth.uid()) = owner_id);
create policy analysis_snapshots_delete_own
  on public.analysis_snapshots for delete to authenticated
  using ((select auth.uid()) = owner_id);

create policy deletion_receipts_select_own
  on public.deletion_receipts for select to authenticated
  using ((select auth.uid()) = owner_id);

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
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );
create policy source_objects_insert_own
  on storage.objects for insert to authenticated
  with check (
    bucket_id = 'proofline-source-library'
    and owner_id = (select auth.uid())::text
    and (storage.foldername(name))[1] = (select auth.uid())::text
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
create policy source_objects_update_own
  on storage.objects for update to authenticated
  using (
    bucket_id = 'proofline-source-library'
    and owner_id = (select auth.uid())::text
    and (storage.foldername(name))[1] = (select auth.uid())::text
  )
  with check (
    bucket_id = 'proofline-source-library'
    and owner_id = (select auth.uid())::text
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );
create policy source_objects_delete_own
  on storage.objects for delete to authenticated
  using (
    bucket_id = 'proofline-source-library'
    and owner_id = (select auth.uid())::text
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );
