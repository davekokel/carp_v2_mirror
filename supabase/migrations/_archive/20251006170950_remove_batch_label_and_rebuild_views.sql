BEGIN;

-- 1) Drop any views that reference fish_seed_batches_map.batch_label
DROP VIEW IF EXISTS public.v_fish_overview_canonical CASCADE;

-- 2) Recreate the canonical overview WITHOUT batch_label (keep seed_batch_id only)
CREATE VIEW public.v_fish_overview_canonical AS
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

-- 3) Now drop the column safely
ALTER TABLE public.fish_seed_batches_map
  DROP COLUMN IF EXISTS batch_label;

-- 4) Rebuild v_fish_overview (no batch columns) + compat alias
DROP VIEW IF EXISTS public.v_fish_overview CASCADE;

CREATE VIEW public.v_fish_overview AS
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
  DATE_PART('day', now() - f.date_birth)::int AS age_days
FROM public.fish f
ORDER BY f.created_at DESC;

DROP VIEW IF EXISTS public.vw_fish_overview_with_label;
CREATE VIEW public.vw_fish_overview_with_label AS
SELECT * FROM public.v_fish_overview;

COMMIT;
