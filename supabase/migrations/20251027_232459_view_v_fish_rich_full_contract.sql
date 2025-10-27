DROP VIEW IF EXISTS public.v_fish_rich CASCADE;

CREATE VIEW public.v_fish_rich AS
SELECT
  f.fish_uuid::uuid                  AS fish_uuid,
  f.fish_code::text                  AS fish_code,
  NULL::text                         AS fish_name,
  NULL::text                         AS fish_nickname,
  NULL::text                         AS genetic_background,
  NULL::text                         AS line_building_stage,
  NULL::date                         AS date_birth,
  0::int                             AS allele_number,
  NULL::text                         AS allele_code,
  0::int                             AS n_active_tanks,
  NULL::text                         AS transgene_pretty,
  NULL::text                         AS genotype_rollup,
  f.created_at::timestamptz          AS created_at
FROM public.fish f;
