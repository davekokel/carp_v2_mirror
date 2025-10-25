DROP VIEW IF EXISTS public.v_fish_overview CASCADE;
-- Compat view for the UI: expose the columns load_fish_overview() expects.
CREATE OR REPLACE VIEW public.v_fish_overview AS
SELECT
    v.fish_code,
    null::text AS genetic_background,
    null::date AS date_birth,
    null::timestamptz AS created_at,
    coalesce(v.name, '') AS name,
    coalesce(v.nickname, '') AS nickname,
    coalesce(
        coalesce('', '', ''),
        '',
        v.allele_name_filled,
        v.allele_code_filled,
        ''
    ) AS genotype,
    coalesce(v.line_building_stage, '') AS stage,
    coalesce(v.created_by, '') AS created_by,
    coalesce(v.batch_label, '') AS batch_display
FROM public.v_fish_overview_with_label AS v;
