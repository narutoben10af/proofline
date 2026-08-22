-- Activate the authenticated live upload boundary. The application server validates and
-- normalizes bytes; this transaction persists only owner-scoped evidence and the cited response.

alter table public.source_spans
  add column if not exists source_span_id text;

alter table public.documents
  add column if not exists sanitization_warning text
    check (sanitization_warning is null or char_length(sanitization_warning) between 1 and 500);

create unique index if not exists source_spans_owner_session_external_id_idx
  on public.source_spans (owner_id, session_id, source_span_id);

alter table public.analysis_snapshots
  add column if not exists analysis_response jsonb,
  add column if not exists analysis_response_sha256 text
    check (analysis_response_sha256 is null or analysis_response_sha256 ~ '^[0-9a-f]{64}$');

create table if not exists public.magic_assistant_evidence (
  session_id uuid not null,
  owner_id uuid not null,
  source_id uuid not null,
  source_span_id text not null,
  observation_id text not null,
  issuer text not null check (char_length(issuer) between 1 and 256),
  concept text not null check (concept in (
    'revenue',
    'operating_profit',
    'current_assets',
    'current_liabilities',
    'operating_cash_flow',
    'capex'
  )),
  numeric_value numeric not null,
  display_value text not null check (char_length(display_value) between 1 and 256),
  period_start date,
  period_end date not null,
  duration_weeks integer check (duration_weeks is null or duration_weeks between 1 and 54),
  unit text not null check (char_length(unit) between 1 and 64),
  currency text check (currency is null or currency ~ '^[A-Z]{3}$'),
  created_at timestamptz not null default now(),
  primary key (owner_id, session_id, observation_id),
  foreign key (session_id, owner_id)
    references public.analysis_sessions(id, owner_id) on delete cascade,
  foreign key (source_id, owner_id, session_id)
    references public.documents(id, owner_id, session_id) on delete cascade,
  check (period_start is null or period_start <= period_end)
);

create index if not exists magic_assistant_evidence_owner_session_idx
  on public.magic_assistant_evidence (owner_id, session_id, source_id, period_end);

alter table public.magic_assistant_evidence enable row level security;
alter table public.magic_assistant_evidence force row level security;
revoke all on table public.magic_assistant_evidence from public, anon, authenticated;
grant select on public.magic_assistant_evidence to authenticated;
grant select, insert, update, delete on public.magic_assistant_evidence to service_role;

create policy magic_assistant_evidence_select_own
  on public.magic_assistant_evidence for select to authenticated
  using (
    (select auth.uid()) = owner_id
    and not coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false)
  );

create or replace function public.persist_completed_analysis(
  target_session_id uuid,
  target_owner_id uuid,
  analysis_response jsonb,
  analysis_response_sha256 text,
  normalized_source_spans jsonb,
  normalized_evidence jsonb
)
returns public.analysis_snapshots
language plpgsql
security invoker
set search_path = ''
as $$
declare
  instant timestamptz := clock_timestamp();
  snapshot public.analysis_snapshots;
  span_count integer;
  evidence_count integer;
begin
  if analysis_response is null
    or jsonb_typeof(analysis_response) <> 'object'
    or analysis_response ->> 'schema_version' <> '1.0.0'
    or analysis_response ->> 'output_status' <> 'calculated'
    or analysis_response_sha256 !~ '^[0-9a-f]{64}$'
    or jsonb_typeof(normalized_source_spans) <> 'array'
    or jsonb_typeof(normalized_evidence) <> 'array'
    or jsonb_array_length(normalized_source_spans) not between 1 and 1000
    or jsonb_array_length(normalized_evidence) not between 1 and 500
  then
    raise exception using errcode = '22023', message = 'ANALYSIS_PAYLOAD_INVALID';
  end if;

  perform 1
  from public.analysis_sessions session
  where session.id = target_session_id
    and session.owner_id = target_owner_id
    and session.state in ('OPEN', 'PROCESSING')
    and instant < session.idle_expires_at
    and instant < session.absolute_expires_at
  for update;
  if not found then
    raise exception using errcode = 'P0001', message = 'SESSION_NOT_AVAILABLE';
  end if;

  if (
    select count(*)
    from public.documents document
    where document.session_id = target_session_id
      and document.owner_id = target_owner_id
      and document.validation_status = 'Ready'
  ) <> 2 then
    raise exception using errcode = 'P0001', message = 'REQUIRED_FILES_NOT_READY';
  end if;

  delete from public.analysis_snapshots
  where session_id = target_session_id and owner_id = target_owner_id;
  delete from public.magic_assistant_evidence
  where session_id = target_session_id and owner_id = target_owner_id;
  delete from public.source_spans
  where session_id = target_session_id and owner_id = target_owner_id;

  insert into public.source_spans (
    session_id,
    document_id,
    owner_id,
    source_span_id,
    page_number,
    sheet_name,
    cell_range,
    content_sha256
  )
  select
    target_session_id,
    row.document_id,
    target_owner_id,
    row.source_span_id,
    row.page_number,
    row.sheet_name,
    row.cell_range,
    row.content_sha256
  from jsonb_to_recordset(normalized_source_spans) as row(
    document_id uuid,
    source_span_id text,
    page_number integer,
    sheet_name text,
    cell_range text,
    content_sha256 text
  );
  get diagnostics span_count = row_count;

  insert into public.magic_assistant_evidence (
    session_id,
    owner_id,
    source_id,
    source_span_id,
    observation_id,
    issuer,
    concept,
    numeric_value,
    display_value,
    period_start,
    period_end,
    duration_weeks,
    unit,
    currency
  )
  select
    target_session_id,
    target_owner_id,
    row.source_id,
    row.source_span_id,
    row.observation_id,
    row.issuer,
    row.concept,
    row.numeric_value,
    row.display_value,
    row.period_start,
    row.period_end,
    row.duration_weeks,
    row.unit,
    row.currency
  from jsonb_to_recordset(normalized_evidence) as row(
    source_id uuid,
    source_span_id text,
    observation_id text,
    issuer text,
    concept text,
    numeric_value numeric,
    display_value text,
    period_start date,
    period_end date,
    duration_weeks integer,
    unit text,
    currency text
  );
  get diagnostics evidence_count = row_count;

  if span_count <> jsonb_array_length(normalized_source_spans)
    or evidence_count <> jsonb_array_length(normalized_evidence)
  then
    raise exception using errcode = 'P0001', message = 'ANALYSIS_PERSISTENCE_INCOMPLETE';
  end if;

  insert into public.analysis_snapshots (
    session_id,
    owner_id,
    schema_version,
    status,
    evidence_chain_sha256,
    source_span_count,
    provider_sent,
    created_at,
    completed_at,
    analysis_response,
    analysis_response_sha256
  ) values (
    target_session_id,
    target_owner_id,
    '1.0.0',
    'complete',
    analysis_response_sha256,
    span_count,
    false,
    instant,
    instant,
    analysis_response,
    analysis_response_sha256
  ) returning * into snapshot;

  update public.analysis_sessions
  set
    state = 'OPEN',
    updated_at = instant,
    last_activity_at = instant,
    idle_expires_at = least(instant + interval '30 minutes', absolute_expires_at)
  where id = target_session_id and owner_id = target_owner_id;

  return snapshot;
end;
$$;

revoke execute on function public.persist_completed_analysis(
  uuid, uuid, jsonb, text, jsonb, jsonb
) from public, anon, authenticated;
grant execute on function public.persist_completed_analysis(
  uuid, uuid, jsonb, text, jsonb, jsonb
) to service_role;
