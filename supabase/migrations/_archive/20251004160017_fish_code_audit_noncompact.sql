BEGIN;

CREATE TABLE IF NOT EXISTS public.fish_code_audit (
  id bigserial primary key,
  at timestamptz not null default now(),
  fish_id uuid,
  fish_code text,
  app_name text,
  client_addr inet,
  pid int,
  note text
);

-- Log ONLY when client supplies a non-compact code on INSERT
CREATE OR REPLACE FUNCTION public.fish_code_audit_noncompact()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.fish_code IS NOT NULL AND btrim(NEW.fish_code) <> '' AND NEW.fish_code !~ '^FSH-[0-9]{2}[0-9A-Z]{4,}$' THEN
    INSERT INTO public.fish_code_audit (fish_id, fish_code, app_name, client_addr, pid, note)
    VALUES (NEW.id, NEW.fish_code, current_setting('application_name', true), inet_client_addr(), pg_backend_pid(),
            'non-compact fish_code supplied on INSERT');
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_fish_code_audit_noncompact ON public.fish;
CREATE TRIGGER trg_fish_code_audit_noncompact
BEFORE INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.fish_code_audit_noncompact();

COMMIT;
