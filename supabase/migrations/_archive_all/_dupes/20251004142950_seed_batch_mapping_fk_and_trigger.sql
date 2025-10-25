BEGIN;

-- 1) Create table if missing
CREATE TABLE IF NOT EXISTS public.fish_seed_batches (
    fish_id uuid PRIMARY KEY,
    seed_batch_id text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- 2) Ensure FK → fish(id), DEFERRABLE INITIALLY DEFERRED
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='fish_seed_batches'
      AND constraint_type='FOREIGN KEY'
  ) THEN
    EXECUTE (
      SELECT 'ALTER TABLE public.fish_seed_batches DROP CONSTRAINT ' || quote_ident(tc.constraint_name)
      FROM information_schema.table_constraints tc
      WHERE tc.table_schema='public' AND tc.table_name='fish_seed_batches'
        AND tc.constraint_type='FOREIGN KEY'
      LIMIT 1
    );
  END IF;

  ALTER TABLE public.fish_seed_batches
    ADD CONSTRAINT fk_fsb_fish
      FOREIGN KEY (fish_id) REFERENCES public.fish(id)
      ON DELETE CASCADE
      DEFERRABLE INITIALLY DEFERRED;
END$$;

-- 3) Upsert trigger fn
CREATE OR REPLACE FUNCTION public.tg_upsert_fish_seed_maps()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO public.fish_seed_batches (fish_id, seed_batch_id, updated_at)
  VALUES (NEW.fish_id, NEW.seed_batch_id, now())
  ON CONFLICT (fish_id)
  DO UPDATE SET seed_batch_id = EXCLUDED.seed_batch_id,
                updated_at    = EXCLUDED.updated_at;
  RETURN NULL;
END
$$;

-- 4) AFTER INSERT trigger on load_log_fish
DROP TRIGGER IF EXISTS tg_upsert_fish_seed_maps ON public.load_log_fish;
CREATE TRIGGER tg_upsert_fish_seed_maps
AFTER INSERT ON public.load_log_fish
FOR EACH ROW
EXECUTE FUNCTION public.tg_upsert_fish_seed_maps();

COMMIT;
