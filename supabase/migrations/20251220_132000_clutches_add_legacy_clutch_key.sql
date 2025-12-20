BEGIN;

ALTER TABLE public.clutches
  ADD COLUMN IF NOT EXISTS legacy_clutch_key text;

CREATE UNIQUE INDEX IF NOT EXISTS uniq_clutches_legacy_clutch_key__legacy_imaging
ON public.clutches (legacy_clutch_key)
WHERE source_system = 'legacy_imaging'
  AND legacy_clutch_key IS NOT NULL
  AND btrim(legacy_clutch_key) <> '';

COMMIT;
