-- Idempotent audit table + grants
CREATE TABLE IF NOT EXISTS public.audit_log (
  id          bigserial PRIMARY KEY,
  at          timestamptz NOT NULL DEFAULT now(),
  actor_email text,
  event       text NOT NULL,
  details     jsonb,
  page        text
);

-- Carp app needs to INSERT
GRANT INSERT, SELECT ON public.audit_log TO carp_app;

-- Helpful index
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='idx_audit_log_at') THEN
    CREATE INDEX idx_audit_log_at ON public.audit_log(at DESC);
  END IF;
END $$;

-- Future-proof: make sure default privs cover new tables (already handled by your grants migration)
