-- Authenticated, owner-isolated demo metadata for the Magic Assistant.
-- This bootstrap stores no file bytes, excerpts, formulas, or financial values. It only creates
-- the stable identifiers needed for a cited chart proposal against the public synthetic fixture.

alter table public.magic_assistant_evidence
  alter column document_id drop not null,
  add column is_demo boolean not null default false,
  add constraint magic_assistant_evidence_document_or_demo_check check (
    (is_demo and document_id is null)
    or (not is_demo and document_id is not null)
  );

create function public.bootstrap_magic_assistant_demo()
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  caller uuid := auth.uid();
  instant timestamptz := clock_timestamp();
  demo_analysis_session_id uuid := (
    substr(md5('magicfin-assistant-demo-session:' || caller::text), 1, 8) || '-' ||
    substr(md5('magicfin-assistant-demo-session:' || caller::text), 9, 4) || '-' ||
    substr(md5('magicfin-assistant-demo-session:' || caller::text), 13, 4) || '-' ||
    substr(md5('magicfin-assistant-demo-session:' || caller::text), 17, 4) || '-' ||
    substr(md5('magicfin-assistant-demo-session:' || caller::text), 21, 12)
  )::uuid;
  demo_session_id constant text := 'src-4d6167696346696e44656d6f32303235';
  demo_source_id constant text := 'file-4d6167696346696e44656d6f';
begin
  if caller is null
    or coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false)
  then
    raise exception using errcode = '42501', message = 'AUTHENTICATED_USER_REQUIRED';
  end if;

  insert into public.analysis_sessions (
    id,
    owner_id,
    state,
    created_at,
    updated_at,
    last_activity_at,
    idle_expires_at,
    absolute_expires_at,
    provider_sent,
    provider_sent_at,
    deletion_requested_at,
    deletion_completed_at,
    deletion_status
  ) values (
    demo_analysis_session_id,
    caller,
    'OPEN',
    instant,
    instant,
    instant,
    instant + interval '30 minutes',
    instant + interval '2 hours',
    false,
    null,
    null,
    null,
    null
  )
  on conflict (id) do update set
    state = 'OPEN',
    updated_at = excluded.updated_at,
    last_activity_at = excluded.last_activity_at,
    idle_expires_at = excluded.idle_expires_at,
    absolute_expires_at = excluded.absolute_expires_at,
    provider_sent = false,
    provider_sent_at = null,
    deletion_requested_at = null,
    deletion_completed_at = null,
    deletion_status = null
  where public.analysis_sessions.owner_id = caller;

  if not exists (
    select 1 from public.analysis_sessions
    where id = demo_analysis_session_id and owner_id = caller
  ) then
    raise exception using errcode = 'P0001', message = 'DEMO_SESSION_UNAVAILABLE';
  end if;

  delete from public.magic_assistant_evidence
  where owner_id = caller and session_id = demo_session_id;

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
    currency,
    is_demo
  ) values
    (demo_analysis_session_id, null, caller, demo_session_id, demo_source_id,
      'fact:72657632303232000000', 'Northstar Industrial plc', 'revenue',
      date '2022-01-01', date '2022-12-31', 52, 'USD millions', 'USD', true),
    (demo_analysis_session_id, null, caller, demo_session_id, demo_source_id,
      'fact:72657632303233000000', 'Northstar Industrial plc', 'revenue',
      date '2023-01-01', date '2023-12-31', 52, 'USD millions', 'USD', true),
    (demo_analysis_session_id, null, caller, demo_session_id, demo_source_id,
      'fact:72657632303234000000', 'Northstar Industrial plc', 'revenue',
      date '2024-01-01', date '2024-12-31', 52, 'USD millions', 'USD', true),
    (demo_analysis_session_id, null, caller, demo_session_id, demo_source_id,
      'fact:72657632303235000000', 'Northstar Industrial plc', 'revenue',
      date '2025-01-01', date '2025-12-31', 52, 'USD millions', 'USD', true);

  return jsonb_build_object(
    'mode', 'verified_demo',
    'assistantContext', jsonb_build_object(
      'sessionId', demo_session_id,
      'sourceIds', jsonb_build_array(demo_source_id)
    ),
    'disclosure', 'Synthetic public demo metadata; no file was uploaded or stored.'
  );
end;
$$;

revoke all on function public.bootstrap_magic_assistant_demo() from public, anon;
grant execute on function public.bootstrap_magic_assistant_demo() to authenticated;
