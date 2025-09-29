-- Ensure the application role exists (safe to re-run)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'carp_app') THEN
    -- NOLOGIN is fine for grants; switch to LOGIN later if needed
    CREATE ROLE carp_app NOLOGIN;
  END IF;
END$$;
