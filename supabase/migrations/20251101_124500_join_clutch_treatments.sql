BEGIN;

-- If the legacy table exists, rename it and normalize column names
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='clutch_materials'
  ) THEN
    -- Rename table
    EXECUTE 'ALTER TABLE public.clutch_materials RENAME TO join_clutch_treatments';

    -- Normalize column names if needed
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='material_type'
    ) THEN
      EXECUTE 'ALTER TABLE public.join_clutch_treatments RENAME COLUMN material_type TO treatment_type';
    END IF;
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='material_code'
    ) THEN
      EXECUTE 'ALTER TABLE public.join_clutch_treatments RENAME COLUMN material_code TO treatment_code';
    END IF;
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='join_clutch_treatments' AND column_name='material_name'
    ) THEN
      EXECUTE 'ALTER TABLE public.join_clutch_treatments RENAME COLUMN material_name TO treatment_name';
    END IF;
  END IF;
END $$;

-- Create the table if it still doesn't exist
CREATE TABLE IF NOT EXISTS public.join_clutch_treatments (
  clutch_instance_id uuid NOT NULL,
  treatment_type     text,
  treatment_code     text,
  treatment_name     text,
  notes              text,
  created_by         text,
  created_at         timestamptz NOT NULL DEFAULT now()
);

-- Minimal FK (soft delete: if you prefer, add ON DELETE CASCADE)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='join_clutch_treatments' AND constraint_name='fk_jct_clutch'
  ) THEN
    ALTER TABLE public.join_clutch_treatments
      ADD CONSTRAINT fk_jct_clutch
      FOREIGN KEY (clutch_instance_id) REFERENCES public.clutch_instances(id) ON DELETE RESTRICT;
  END IF;
END $$;

-- Unique de-dupe per clutch on normalized (type, code)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='join_clutch_treatments' AND indexname='uq_clutch_materials_unique'
  ) THEN
    -- Drop legacy unique index name if present
    EXECUTE 'DROP INDEX public.uq_clutch_materials_unique';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='join_clutch_treatments' AND indexname='uq_jct_unique'
  ) THEN
    EXECUTE $ix$
      CREATE UNIQUE INDEX uq_jct_unique
      ON public.join_clutch_treatments (
        clutch_instance_id,
        lower(coalesce(treatment_type,'')),
        lower(coalesce(treatment_code,''))
      )
    $ix$;
  END IF;
END $$;

-- Helper indexes
CREATE INDEX IF NOT EXISTS ix_jct_clutch ON public.join_clutch_treatments(clutch_instance_id);
CREATE INDEX IF NOT EXISTS ix_jct_type   ON public.join_clutch_treatments(lower(treatment_type));
CREATE INDEX IF NOT EXISTS ix_jct_code   ON public.join_clutch_treatments(lower(treatment_code));

COMMIT;
