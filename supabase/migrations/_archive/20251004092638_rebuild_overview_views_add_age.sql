BEGIN;

CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
WITH base AS (
    SELECT
        v.id,
        v.fish_code,
        v.name,
        v.transgene_base_code_filled,
        v.allele_code_filled,
        v.allele_name_filled,
        v.created_at,
        v.created_by,
        null::text AS nickname,
        null::text AS line_building_stage,
        f.date_birth,
        coalesce(f.created_by, v.created_by) AS created_by_enriched
    FROM public.v_fish_overview AS v
    LEFT JOIN public.fish AS f
        ON v.fish_code = f.fish_code
),

prefer_code AS (
    SELECT
        b.*,
        coalesce(substring(b.fish_code FROM '^FSH-([0-9]{8}-[0-9]{6})'), b.fish_code) AS batch_label
    FROM base AS b
)

SELECT
    p.id,
    p.fish_code,
    p.name,
    p.transgene_base_code_filled,
    p.allele_code_filled,
    p.allele_name_filled,
    p.created_at,
    p.created_by,
    p.nickname,
    p.line_building_stage,
    p.date_birth,
    p.batch_label,
    p.created_by_enriched,
    null::timestamptz AS last_plasmid_injection_at,
    null::text AS plasmid_injections_text,
    null::timestamptz AS last_rna_injection_at,
    null::text AS rna_injections_text,
    CASE WHEN p.date_birth IS NOT null THEN (current_date - p.date_birth) END AS age_days,
    CASE WHEN p.date_birth IS NOT null THEN floor((current_date - p.date_birth)::numeric / 7)::int END
        AS age_weeks
FROM prefer_code AS p;

COMMIT;
