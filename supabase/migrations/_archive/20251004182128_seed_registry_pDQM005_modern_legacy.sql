BEGIN;

-- Upsert canonical mapping for pDQM005:304 (modern + legacy in the same row)
INSERT INTO public.transgene_allele_registry
  (transgene_base_code, allele_nickname, allele_number, base_code, legacy_label)
VALUES
  ('pDQM005', '304', 304, 'pDQM005', '304')
ON CONFLICT (transgene_base_code, allele_nickname)
DO UPDATE SET
  allele_number = EXCLUDED.allele_number,
  base_code     = EXCLUDED.base_code,
  legacy_label  = EXCLUDED.legacy_label;

-- Optional hygiene: remove any legacy-only rows with NULL modern keys (shouldn't exist now, but safe)
DELETE FROM public.transgene_allele_registry
WHERE base_code IS NOT NULL AND legacy_label IS NOT NULL
  AND transgene_base_code IS NULL AND allele_nickname IS NULL;

COMMIT;
