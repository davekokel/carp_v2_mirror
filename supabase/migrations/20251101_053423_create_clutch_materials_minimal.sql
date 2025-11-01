-- Minimal generic link for treatments → clutches
CREATE TABLE IF NOT EXISTS public.clutch_materials (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_instance_id uuid NOT NULL,
  material_type      text NOT NULL,
  material_code      text NOT NULL,
  material_name      text,
  notes              text,
  created_by         text,
  created_at         timestamptz NOT NULL DEFAULT now()
);

-- De-dup per clutch: (type, code) case-insensitive
CREATE UNIQUE INDEX IF NOT EXISTS uq_clutch_materials_expr
  ON public.clutch_materials (
    clutch_instance_id,
    lower(coalesce(material_type,'')),
    lower(coalesce(material_code,''))
  );
