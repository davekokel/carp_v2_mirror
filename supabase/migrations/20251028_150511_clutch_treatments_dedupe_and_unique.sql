BEGIN;

WITH d AS (
  SELECT ctid
  FROM (
    SELECT
      ctid,
      ROW_NUMBER() OVER (
        PARTITION BY
          clutch_instance_id,
          lower(coalesce(material_type,'')),
          lower(coalesce(material_code,''))
        ORDER BY created_at DESC NULLS LAST
      ) AS rn
    FROM public.clutch_instance_treatments
  ) s
  WHERE rn > 1
)
DELETE FROM public.clutch_instance_treatments
WHERE ctid IN (SELECT ctid FROM d);

CREATE UNIQUE INDEX IF NOT EXISTS uq_clutch_instance_treatments_dedup
ON public.clutch_instance_treatments (
  clutch_instance_id,
  lower(coalesce(material_type,'')),
  lower(coalesce(material_code,''))
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='con_uq_clutch_instance_treatments_dedup'
  ) THEN
    EXECUTE 'ALTER TABLE public.clutch_instance_treatments
             ADD CONSTRAINT con_uq_clutch_instance_treatments_dedup
             UNIQUE USING INDEX uq_clutch_instance_treatments_dedup';
  END IF;
END $$;

COMMIT;
