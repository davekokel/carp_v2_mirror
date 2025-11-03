BEGIN;

-- Legacy-safe: only ensure the table exists with the modern minimal columns.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='join_clutch_treatments'
  ) THEN
    CREATE TABLE public.join_clutch_treatments (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      clutch_instance_id uuid NOT NULL,
      created_by text,
      created_at timestamptz NOT NULL DEFAULT now(),
      treatment_id uuid
    );
  END IF;
END$$;

-- Do NOT create legacy columns (treatment_type/name/code or *_norm) here.
-- Later migrations handle FKs, views, and backfills.

COMMIT;
