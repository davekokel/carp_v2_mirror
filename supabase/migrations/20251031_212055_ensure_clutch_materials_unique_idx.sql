-- Ensure the link table + the exact unique expr index exist
DO $$
BEGIN
  IF to_regclass('public.clutch_materials') IS NULL THEN
    EXECUTE $ct$
      CREATE TABLE public.clutch_materials (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        clutch_instance_id uuid NOT NULL,
        material_type text NOT NULL,
        material_code text NOT NULL,
        material_name text,
        notes text,
        created_by text,
        created_at timestamptz NOT NULL DEFAULT now()
      )
    $ct$;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname='public'
      AND indexname='uq_clutch_materials_expr'
  ) THEN
    EXECUTE $ix$
      CREATE UNIQUE INDEX uq_clutch_materials_expr
      ON public.clutch_materials (
        clutch_instance_id,
        lower(coalesce(material_type,'')),
        lower(coalesce(material_code,''))
      )
    $ix$;
  END IF;
END$$;
