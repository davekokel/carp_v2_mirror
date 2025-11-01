-- Create the generic link table used by v_clutch_treatments
DO $$
BEGIN
  IF to_regclass('public.clutch_materials') IS NULL THEN
    EXECUTE '
      CREATE TABLE public.clutch_materials (
        id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        clutch_instance_id  uuid NOT NULL,
        material_type       text NOT NULL,
        material_code       text NOT NULL,
        material_name       text,
        notes               text,
        created_by          text,
        created_at          timestamptz NOT NULL DEFAULT now()
      )';
  END IF;

  -- add the natural de-dup when not present (simple case-sensitive variant)
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'uq_clutch_materials_dedup'
      AND conrelid = 'public.clutch_materials'::regclass
  ) THEN
    EXECUTE '
      ALTER TABLE public.clutch_materials
      ADD CONSTRAINT uq_clutch_materials_dedup
      UNIQUE (clutch_instance_id, material_type, material_code)';
  END IF;
END$$;
