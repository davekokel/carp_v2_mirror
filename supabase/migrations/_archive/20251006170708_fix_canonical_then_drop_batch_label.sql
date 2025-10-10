BEGIN;

-- 1) Recreate the canonical view WITHOUT batch_label (keep only seed_batch_id)
CREATE OR REPLACE VIEW public.v_fish_overview_canonical AS
SELECT
  f.fish_code,
  f.name,
  f.nickname,
  f.line_building_stage,
  f.date_birth,
  f.genetic_background,
  f.created_at,
  NULLIF(
    array_to_string(
      ARRAY(
        SELECT (fa2.transgene_base_code || '^' || fa2.allele_number::text)
        FROM public.fish_transgene_alleles fa2
        WHERE fa2.fish_id = f.id_uuid
        ORDER BY fa2.transgene_base_code, fa2.allele_number
      ),
      '; '
    ),
    ''
  ) AS genotype_text,
  DATE_PART('day', now() - f.date_birth)::int AS age_days,
  (
    SELECT m.seed_batch_id
    FROM public.fish_seed_batches_map m
    WHERE m.fish_id = f.id_uuid
    ORDER BY m.logged_at DESC
    LIMIT 1
  ) AS seed_batch_id
FROM public.fish f
ORDER BY f.created_at DESC;

-- 2) Now it is safe to drop the column
ALTER TABLE public.fish_seed_batches_map
  DROP COLUMN IF EXISTS batch_label;

COMMIT;
