BEGIN;
CREATE UNIQUE INDEX IF NOT EXISTS uq_clutch_instance_treatments_dedup
ON public.clutch_instance_treatments (
  clutch_instance_id,
  lower(coalesce(material_type,'')),
  lower(coalesce(material_code,''))
);
COMMIT;
