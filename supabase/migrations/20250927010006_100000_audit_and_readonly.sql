-- Audit table — very small and safe (idempotent create)
create table if not exists public.audit_events (
  id     bigserial primary key,
  ts     timestamptz not null default now(),
  actor  text,             -- e.g., current_user (db role)
  page   text,             -- e.g., "Assign & Labels"
  action text not null,    -- e.g., "print_labels", "assign_tank"
  meta   jsonb             -- free-form details (ids, counts)
);

-- Helpful indexes
create index if not exists audit_events_ts_idx on public.audit_events(ts desc);
create index if not exists audit_events_action_idx on public.audit_events(action);

-- Allow app role to write/read audits
grant select, insert on public.audit_events to carp_app;
