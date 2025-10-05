DO $$
DECLARE
  rna_pk_col text := CASE
    WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='rnas' AND column_name='id')
      THEN 'id'
    WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='rnas' AND column_name='id_uuid')
      THEN 'id_uuid'
    ELSE NULL
  END;
BEGIN
  IF to_regclass('public.fish') IS NULL OR to_regclass('public.rnas') IS NULL THEN
    RAISE NOTICE 'Skipping fish_rnas: deps missing.';
    RETURN;
  END IF;

  -- Create table if missing (FK added below once we know the PK col)
  IF to_regclass('public.fish_rnas') IS NULL THEN
    EXECUTE '
      CREATE TABLE public.fish_rnas(
        fish_id uuid NOT NULL,
        rna_id  uuid NOT NULL,
        PRIMARY KEY (fish_id, rna_id)
      )';
  END IF;

  -- Ensure FK -> fish(id)
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_fish_rnas_fish') THEN
    EXECUTE '
      ALTER TABLE public.fish_rnas
        ADD CONSTRAINT fk_fish_rnas_fish
        FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE';
  END IF;

  -- Ensure FK -> rnas(id or id_uuid)
  IF rna_pk_col IS NULL THEN
    RAISE NOTICE 'Skipping FK to rnas: no id/id_uuid column found.';
    RETURN;
  END IF;

  -- Drop any incorrect FK on rna_id, then add the correct one
  PERFORM 1 FROM pg_constraint WHERE conname='fk_fish_rnas_rna';
  IF FOUND THEN
    EXECUTE 'ALTER TABLE public.fish_rnas DROP CONSTRAINT fk_fish_rnas_rna';
  END IF;

  EXECUTE format(
    'ALTER TABLE public.fish_rnas
       ADD CONSTRAINT fk_fish_rnas_rna
       FOREIGN KEY (rna_id) REFERENCES public.rnas(%I) ON DELETE RESTRICT',
    rna_pk_col
  );
END
$$;
