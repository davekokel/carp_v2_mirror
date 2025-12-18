BEGIN;

INSERT INTO public.genotypes_v11 (
  genotype_code,
  genotype_basecodes,
  genotype_pretty,
  legacy_label,
  source_system,
  nickname,
  display_name
)
VALUES (
  'G-MGCO-01',
  'mgco-1',
  'MGCO-01',
  'legacy_infer:mem-mito',
  'legacy_infer',
  NULL,
  'MGCO-01'
)
ON CONFLICT (genotype_code) DO UPDATE
SET
  genotype_basecodes = EXCLUDED.genotype_basecodes,
  genotype_pretty = COALESCE(EXCLUDED.genotype_pretty, public.genotypes_v11.genotype_pretty),
  legacy_label = COALESCE(EXCLUDED.legacy_label, public.genotypes_v11.legacy_label),
  source_system = COALESCE(EXCLUDED.source_system, public.genotypes_v11.source_system),
  display_name = COALESCE(EXCLUDED.display_name, public.genotypes_v11.display_name);

UPDATE public.clutches c
SET genotype_v11_id = g.id
FROM public.genotypes_v11 g
WHERE c.genotype_v11_id IS NULL
  AND g.genotype_code = 'G-MGCO-01'
  AND c.clutch_code IN (
    SELECT DISTINCT clutch_code
    FROM public.v_roi_overview_rollups
    WHERE experiment_name ILIKE '%mem-mito%'
      AND clutch_code IS NOT NULL
      AND btrim(clutch_code) <> ''
  );

COMMIT;
