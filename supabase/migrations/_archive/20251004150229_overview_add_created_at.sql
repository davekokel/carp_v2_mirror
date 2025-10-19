BEGIN;

DROP VIEW IF EXISTS public.vw_fish_overview_with_label;

CREATE VIEW public.vw_fish_overview_with_label AS
WITH base AS (
    SELECT
        v.id,
        v.fish_code,
        v.name,
        v.transgene_base_code_filled,
        v.allele_code_filled,
        v.allele_name_filled,
        v.created_at,                  -- << keep created_at in the view
        v.created_by,
        f.nickname,
        f.line_building_stage,
        f.date_birth,
        COALESCE(f.created_by, v.created_by) AS created_by_enriched
    FROM public.v_fish_overview AS v
    LEFT JOIN public.fish AS f ON v.fish_code = f.fish_code
),

batch AS (
    SELECT
        fish_id,
        MAX(seed_batch_id) AS seed_batch_id
    FROM public.load_log_fish
    GROUP BY fish_id
),

prefer AS (
    SELECT
        b.*,
        COALESCE(
            bt.seed_batch_id,
            SUBSTRING(b.fish_code FROM '^FSH-([0-9]{2}[0-9A-Z]{4,})'),
            b.fish_code
        ) AS batch_label
    FROM base AS b
    LEFT JOIN batch AS bt ON b.id = bt.fish_id
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
    NULL::timestamptz AS last_plasmid_injection_at,
    NULL::text AS plasmid_injections_text,
    NULL::timestamptz AS last_rna_injection_at,
    NULL::text AS rna_injections_text,
    CASE WHEN p.date_birth IS NOT NULL THEN (CURRENT_DATE - p.date_birth) END AS age_days,
    CASE WHEN p.date_birth IS NOT NULL THEN FLOOR(((CURRENT_DATE - p.date_birth)::numeric) / 7)::int END AS age_weeks
FROM prefer AS p;

COMMIT;
