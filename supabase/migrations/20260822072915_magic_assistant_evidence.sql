-- Owner-isolated, numeric-free evidence index for the authenticated Magic Assistant.
-- Authoritative Decimal values remain in the reviewed AnalysisResponse and are resolved by the
-- frontend; neither Gemma nor this relation can author or duplicate financial values.

create table public.magic_assistant_evidence (
  analysis_session_id uuid not null,
  document_id uuid not null,
  owner_id uuid not null,
  session_id text not null check (session_id ~ '^src-[A-Za-z0-9_-]{32}$'),
  source_id text not null check (source_id ~ '^file-[A-Za-z0-9_-]{24}$'),
  observation_id text not null check (observation_id ~ '^fact:[0-9a-f]{20}$'),
  issuer text not null
    check (char_length(issuer) between 1 and 256 and issuer = btrim(issuer)),
  concept text not null check (
    concept in (
      'revenue',
      'operating_profit',
      'current_assets',
      'current_liabilities',
      'operating_cash_flow',
      'capex'
    )
  ),
  period_start date,
  period_end date not null,
  duration_weeks smallint check (duration_weeks is null or duration_weeks between 1 and 54),
  unit text not null check (char_length(unit) between 1 and 64 and unit = btrim(unit)),
  currency text check (currency is null or currency ~ '^[A-Z]{3}$'),
  created_at timestamptz not null default now(),
  primary key (owner_id, session_id, observation_id),
  foreign key (analysis_session_id, owner_id)
    references public.analysis_sessions(id, owner_id) on delete cascade,
  foreign key (document_id, owner_id, analysis_session_id)
    references public.documents(id, owner_id, session_id) on delete cascade,
  check (period_start is null or period_start <= period_end)
);

create index magic_assistant_evidence_owner_session_source_idx
  on public.magic_assistant_evidence (owner_id, session_id, source_id);

alter table public.magic_assistant_evidence enable row level security;
alter table public.magic_assistant_evidence force row level security;

revoke all on table public.magic_assistant_evidence from public, anon, authenticated;
grant select on public.magic_assistant_evidence to authenticated;
grant select on public.magic_assistant_evidence to service_role;

create policy magic_assistant_evidence_select_active_own
  on public.magic_assistant_evidence for select to authenticated
  using (
    (select auth.uid()) = owner_id
    and not coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false)
    and exists (
      select 1
      from public.analysis_sessions as owned_session
      where owned_session.id = analysis_session_id
        and owned_session.owner_id = owner_id
        and owned_session.state in ('OPEN', 'PROCESSING')
        and now() < owned_session.idle_expires_at
        and now() < owned_session.absolute_expires_at
    )
  );

-- Only reviewed backend orchestration can replace one complete evidence index. The exact payload
-- excludes numeric/display values, file bytes, excerpts, formulas, URLs and model-authored prose.
create function public.replace_magic_assistant_evidence(
  target_analysis_session_id uuid,
  target_owner_id uuid,
  external_session_id text,
  evidence_rows jsonb
)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  instant timestamptz := clock_timestamp();
  inserted_count integer;
begin
  if coalesce(auth.role(), '') <> 'service_role' then
    raise exception using errcode = '42501', message = 'SERVICE_ROLE_REQUIRED';
  end if;
  if external_session_id !~ '^src-[A-Za-z0-9_-]{32}$' then
    raise exception using errcode = '22023', message = 'EXTERNAL_SESSION_ID_INVALID';
  end if;
  if jsonb_typeof(evidence_rows) <> 'array'
    or jsonb_array_length(evidence_rows) not between 1 and 24
  then
    raise exception using errcode = '22023', message = 'EVIDENCE_ROW_COUNT_INVALID';
  end if;

  if exists (
    select 1
    from jsonb_array_elements(evidence_rows) as candidate(item)
    where jsonb_typeof(candidate.item) <> 'object'
      or not candidate.item ?& array[
        'document_id', 'source_id', 'observation_id', 'issuer', 'concept',
        'period_start', 'period_end', 'duration_weeks', 'unit', 'currency'
      ]
      or exists (
        select 1
        from jsonb_object_keys(candidate.item) as supplied(key)
        where supplied.key <> all (array[
          'document_id', 'source_id', 'observation_id', 'issuer', 'concept',
          'period_start', 'period_end', 'duration_weeks', 'unit', 'currency'
        ])
      )
  ) then
    raise exception using errcode = '22023', message = 'EVIDENCE_ROW_SHAPE_INVALID';
  end if;

  perform 1
  from public.analysis_sessions as target_session
  where target_session.id = target_analysis_session_id
    and target_session.owner_id = target_owner_id
    and target_session.state in ('OPEN', 'PROCESSING')
    and instant < target_session.idle_expires_at
    and instant < target_session.absolute_expires_at
  for update;
  if not found then
    raise exception using errcode = 'P0001', message = 'SESSION_NOT_AVAILABLE';
  end if;

  if exists (
    select 1
    from jsonb_to_recordset(evidence_rows) as candidate(
      document_id uuid,
      source_id text,
      observation_id text,
      issuer text,
      concept text,
      period_start date,
      period_end date,
      duration_weeks smallint,
      unit text,
      currency text
    )
    left join public.documents as source_document
      on source_document.id = candidate.document_id
      and source_document.owner_id = target_owner_id
      and source_document.session_id = target_analysis_session_id
      and source_document.validation_status = 'Ready'
    where source_document.id is null
  ) then
    raise exception using errcode = 'P0001', message = 'READY_SOURCE_DOCUMENT_REQUIRED';
  end if;

  if (
    select count(distinct candidate.issuer)
    from jsonb_to_recordset(evidence_rows) as candidate(issuer text)
  ) <> 1 then
    raise exception using errcode = '22023', message = 'SINGLE_ISSUER_REQUIRED';
  end if;

  delete from public.magic_assistant_evidence
  where analysis_session_id = target_analysis_session_id
    and owner_id = target_owner_id;

  insert into public.magic_assistant_evidence (
    analysis_session_id,
    document_id,
    owner_id,
    session_id,
    source_id,
    observation_id,
    issuer,
    concept,
    period_start,
    period_end,
    duration_weeks,
    unit,
    currency
  )
  select
    target_analysis_session_id,
    candidate.document_id,
    target_owner_id,
    external_session_id,
    candidate.source_id,
    candidate.observation_id,
    candidate.issuer,
    candidate.concept,
    candidate.period_start,
    candidate.period_end,
    candidate.duration_weeks,
    candidate.unit,
    candidate.currency
  from jsonb_to_recordset(evidence_rows) as candidate(
    document_id uuid,
    source_id text,
    observation_id text,
    issuer text,
    concept text,
    period_start date,
    period_end date,
    duration_weeks smallint,
    unit text,
    currency text
  );

  get diagnostics inserted_count = row_count;
  if inserted_count <> jsonb_array_length(evidence_rows) then
    raise exception using errcode = 'P0001', message = 'EVIDENCE_REPLACEMENT_INCOMPLETE';
  end if;
  return inserted_count;
end;
$$;

revoke all on function public.replace_magic_assistant_evidence(uuid, uuid, text, jsonb)
  from public, anon, authenticated;
grant execute on function public.replace_magic_assistant_evidence(uuid, uuid, text, jsonb)
  to service_role;
