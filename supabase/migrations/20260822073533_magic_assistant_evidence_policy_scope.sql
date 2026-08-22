-- Live follow-up for projects where the initial evidence migration was already applied.
-- A fresh database receives the same explicit qualification and grants from the base migration.

revoke all on table public.magic_assistant_evidence from service_role;
grant select on public.magic_assistant_evidence to service_role;

alter policy magic_assistant_evidence_select_active_own
  on public.magic_assistant_evidence
  using (
    (select auth.uid()) = owner_id
    and not coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false)
    and exists (
      select 1
      from public.analysis_sessions as owned_session
      where owned_session.id = analysis_session_id
        and owned_session.owner_id = magic_assistant_evidence.owner_id
        and owned_session.state in ('OPEN', 'PROCESSING')
        and now() < owned_session.idle_expires_at
        and now() < owned_session.absolute_expires_at
    )
  );
