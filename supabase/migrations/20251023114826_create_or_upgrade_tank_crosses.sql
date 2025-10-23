BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1) Base table (if missing)
DO $$
BEGIN
  IF to_regclass('public.tank_crosses') IS NULL THEN
    CREATE TABLE public.tank_crosses (
      cross_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tank_id          uuid NOT NULL,
      mom_fish_code    text NOT NULL,
      dad_fish_code    text NOT NULL,
      date_crossed     date NOT NULL,
      note             text,
      created_by       uuid,
      created_at       timestamptz NOT NULL DEFAULT now()
    );

    CREATE UNIQUE INDEX uq_tank_crosses_tank_date
      ON public.tank_crosses(tank_id, date_crossed);

    CREATE INDEX idx_tank_crosses_mom  ON public.tank_crosses(mom_fish_code);
    CREATE INDEX idx_tank_crosses_dad  ON public.tank_crosses(dad_fish_code);
    CREATE INDEX idx_tank_crosses_date ON public.tank_crosses(date_crossed);
  END IF;
END$$;

-- 2) Core FKs (safe if already present)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='tank_crosses_tank_fkey'
  ) AND to_regclass('public.tanks') IS NOT NULL THEN
    ALTER TABLE public.tank_crosses
      ADD CONSTRAINT tank_crosses_tank_fkey
      FOREIGN KEY (tank_id) REFERENCES public.tanks(tank_id) ON DELETE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='tank_crosses_mom_fkey'
  ) AND to_regclass('public.fish') IS NOT NULL THEN
    ALTER TABLE public.tank_crosses
      ADD CONSTRAINT tank_crosses_mom_fkey
      FOREIGN KEY (mom_fish_code) REFERENCES public.fish(fish_code);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='tank_crosses_dad_fkey'
  ) AND to_regclass('public.fish') IS NOT NULL THEN
    ALTER TABLE public.tank_crosses
      ADD CONSTRAINT tank_crosses_dad_fkey
      FOREIGN KEY (dad_fish_code) REFERENCES public.fish(fish_code);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='tank_crosses_parents_distinct'
  ) THEN
    ALTER TABLE public.tank_crosses
      ADD CONSTRAINT tank_crosses_parents_distinct
      CHECK (mom_fish_code <> dad_fish_code);
  END IF;
END$$;

-- 3) Parent tank columns + FKs
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_crosses' AND column_name='mom_tank_id'
  ) THEN
    ALTER TABLE public.tank_crosses ADD COLUMN mom_tank_id uuid;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tank_crosses' AND column_name='dad_tank_id'
  ) THEN
    ALTER TABLE public.tank_crosses ADD COLUMN dad_tank_id uuid;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='tank_crosses_mom_tank_fkey'
  ) AND to_regclass('public.tanks') IS NOT NULL THEN
    ALTER TABLE public.tank_crosses
      ADD CONSTRAINT tank_crosses_mom_tank_fkey
      FOREIGN KEY (mom_tank_id) REFERENCES public.tanks(tank_id)
      ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='tank_crosses_dad_tank_fkey'
  ) AND to_regclass('public.tanks') IS NOT NULL THEN
    ALTER TABLE public.tank_crosses
      ADD CONSTRAINT tank_crosses_dad_tank_fkey
      FOREIGN KEY (dad_tank_id) REFERENCES public.tanks(tank_id)
      ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;
  END IF;
END$$;

-- 4) Validation trigger: parent tanks belong to specified fish; tanks must differ
CREATE OR REPLACE FUNCTION public.tg_cross_parent_tanks_validate() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  mom_code text;
  dad_code text;
BEGIN
  IF NEW.mom_tank_id IS NOT NULL THEN
    SELECT fish_code INTO mom_code FROM public.tanks WHERE tank_id = NEW.mom_tank_id;
    IF mom_code IS NULL OR mom_code <> NEW.mom_fish_code THEN
      RAISE EXCEPTION 'mom_tank_id % does not belong to mom_fish_code %', NEW.mom_tank_id, NEW.mom_fish_code;
    END IF;
  END IF;

  IF NEW.dad_tank_id IS NOT NULL THEN
    SELECT fish_code INTO dad_code FROM public.tanks WHERE tank_id = NEW.dad_tank_id;
    IF dad_code IS NULL OR dad_code <> NEW.dad_fish_code THEN
      RAISE EXCEPTION 'dad_tank_id % does not belong to dad_fish_code %', NEW.dad_tank_id, NEW.dad_fish_code;
    END IF;
  END IF;

  IF NEW.mom_tank_id IS NOT NULL AND NEW.dad_tank_id IS NOT NULL AND NEW.mom_tank_id = NEW.dad_tank_id THEN
    RAISE EXCEPTION 'mom_tank_id and dad_tank_id must be different';
  END IF;

  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS tg_cross_parent_tanks_validate ON public.tank_crosses;
CREATE CONSTRAINT TRIGGER tg_cross_parent_tanks_validate
AFTER INSERT OR UPDATE OF mom_tank_id, dad_tank_id, mom_fish_code, dad_fish_code
ON public.tank_crosses
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION public.tg_cross_parent_tanks_validate();

-- 5) Convenience view
CREATE OR REPLACE VIEW public.v_crosses AS
SELECT
  c.cross_id,
  c.tank_id,
  t.tank_code,
  c.mom_fish_code,
  fm.name       AS mom_name,
  fm.nickname   AS mom_nickname,
  c.mom_tank_id,
  tm.tank_code  AS mom_tank_code,
  c.dad_fish_code,
  fd.name       AS dad_name,
  fd.nickname   AS dad_nickname,
  c.dad_tank_id,
  td.tank_code  AS dad_tank_code,
  c.date_crossed,
  c.note,
  c.created_by,
  c.created_at
FROM public.tank_crosses c
JOIN public.tanks t  ON t.tank_id  = c.tank_id
LEFT JOIN public.fish fm ON fm.fish_code = c.mom_fish_code
LEFT JOIN public.fish fd ON fd.fish_code = c.dad_fish_code
LEFT JOIN public.tanks tm ON tm.tank_id = c.mom_tank_id
LEFT JOIN public.tanks td ON td.tank_id = c.dad_tank_id
ORDER BY c.date_crossed DESC, t.tank_code;

COMMIT;
