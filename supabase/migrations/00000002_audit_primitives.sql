-- Minimal audit plumbing so baseline triggers compile
CREATE SCHEMA IF NOT EXISTS audit;

-- no-op trigger fn that satisfies baseline CREATE TRIGGER statements
CREATE OR REPLACE FUNCTION audit.fn_writes()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  -- harmless no-op; adjust later if you want real audit rows
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  ELSE
    RETURN NEW;
  END IF;
END
$$;
