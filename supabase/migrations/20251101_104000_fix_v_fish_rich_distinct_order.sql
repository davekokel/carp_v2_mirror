BEGIN;

DO $$
BEGIN
  IF to_regclass('public.v_fish_overview_id') IS NULL THEN
    RAISE NOTICE '104000: v_fish_overview_id not present yet — skipping wrapper creation';
    RETURN;
  END IF;
END$$;

DROP VIEW IF EXISTS public.v_fish_rich;

CREATE VIEW public.v_fish_rich AS
SELECT
  f.id                          AS fish_uuid,
  o.fish_code                   AS fish_code,
  o.nickname                    AS fish_nickname,
  o.nickname                    AS fish_name,
  o.genetic_background          AS genetic_background,
  o.line_building_stage         AS line_building_stage,
  o.birthday                    AS dob,
  o.allele_count                AS allele_number,
  o.allele_codes                AS allele_code,
  o.transgenes                  AS transgene,
  o.genotype_rollup             AS genotype_rollup,
  0::int                        AS n_active_tanks,
  o.created_at                  AS created_at
FROM public.v_fish_overview_id o
JOIN public.fish f ON f.fish_code = o.fish_code;

COMMIT;
