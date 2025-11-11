BEGIN;

-- 0) Refuse to proceed if any tank is not linked to a fish
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM public.tanks WHERE fish_id IS NULL) THEN
    RAISE EXCEPTION 'tanks.fish_id contains NULLs; backfill before enforcing NOT NULL';
  END IF;
END$$;

-- 1) Recreate FK as ON DELETE RESTRICT, ON UPDATE CASCADE (drop if present)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_tanks_fish' AND conrelid='public.tanks'::regclass
  ) THEN
    ALTER TABLE public.tanks DROP CONSTRAINT fk_tanks_fish;
  END IF;
END$$;

ALTER TABLE public.tanks
  ADD CONSTRAINT fk_tanks_fish
  FOREIGN KEY (fish_id) REFERENCES public.fish(id)
  ON UPDATE CASCADE
  ON DELETE RESTRICT;

-- 2) Enforce NOT NULL (forward-only)
ALTER TABLE public.tanks
  ALTER COLUMN fish_id SET NOT NULL;

-- 3) Strict view: no parsing, pure FK join
DROP VIEW IF EXISTS public.v_tanks_overview CASCADE;
CREATE VIEW public.v_tanks_overview AS
SELECT
  t.id::text            AS id,
  t.tank_code::text     AS tank_code,
  f.fish_code::text     AS fish_code,
  COALESCE(t.status::text,'') AS status,
  t.created_at::timestamptz   AS created_at
FROM public.tanks t
JOIN public.fish f ON f.id = t.fish_id;

COMMIT;
