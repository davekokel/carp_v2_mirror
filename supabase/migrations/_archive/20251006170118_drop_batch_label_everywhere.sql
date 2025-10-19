BEGIN;

-- 1) Update canonical view to remove batch_label usage (keep seed_batch_id)
DROP VIEW IF EXISTS public.v_fish_overview_canonical CASCADE;
CREATE VIEW public.v_fish_overview_canonical AS
SELECT
    f.fish_code,
    f.name,
    f.nickname,
    f.line_building_stage,
    f.date_birth,
    f.genetic_background,
    f.created_at,
    DATE_PART('day', NOW() - f.date_birth)::int AS age_days,
    NULLIF(
        ARRAY_TO_STRING(
            ARRAY(
                SELECT (fa2.transgene_base_code || '^' || fa2.allele_number::text)
                FROM public.fish_transgene_alleles AS fa2
                WHERE fa2.fish_id = f.id_uuid
                ORDER BY fa2.transgene_base_code, fa2.allele_number
            ),
            '; '
        ),
        ''
    ) AS genotype_text,
    (
        SELECT m.seed_batch_id
        FROM public.fish_seed_batches_map AS m
        WHERE m.fish_id = f.id_uuid
        ORDER BY m.logged_at DESC
        LIMIT 1
    ) AS seed_batch_id
FROM public.fish AS f
ORDER BY f.created_at DESC;

-- 2) Drop the column now that no objects depend on it
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish_seed_batches_map'
      AND column_name='batch_label'
  ) THEN
    ALTER TABLE public.fish_seed_batches_map DROP COLUMN batch_label;
  END IF;
END$$;

-- 3) Rebuild v_fish_overview (no batch columns) + compat alias
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
    DATE_PART('day', NOW() - f.date_birth)::int AS age_days,
    NULLIF(
        ARRAY_TO_STRING(
            ARRAY(
                SELECT (fa2.transgene_base_code || '^' || fa2.allele_number::text)
                FROM public.fish_transgene_alleles AS fa2
                WHERE fa2.fish_id = f.id_uuid
                ORDER BY fa2.transgene_base_code, fa2.allele_number
            ),
            '; '
        ),
        ''
    ) AS genotype_text
FROM public.fish AS f
ORDER BY f.created_at DESC;

DROP VIEW IF EXISTS public.vw_fish_overview_with_label;
CREATE VIEW public.vw_fish_overview_with_label AS
SELECT * FROM public.v_fish_overview;

COMMIT;
