BEGIN;

-- 1) Lightweight load log keyed by batch (CSV filename) + row_key
CREATE TABLE IF NOT EXISTS public.load_log_fish (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fish_id uuid NOT NULL REFERENCES public.fish (id) ON DELETE CASCADE,
    seed_batch_id text NOT NULL,
    row_key text NOT NULL,                     -- stable hash of normalized row
    logged_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (seed_batch_id, row_key)
);

-- 2) Recreate the overview view so batch_label prefers the seed_batch_id when present
DROP VIEW IF EXISTS public.v_fish_overview_with_label;

CREATE VIEW public.v_fish_overview_with_label AS
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
        f.nickname,
        f.line_building_stage,
        f.date_birth,
        coalesce(f.created_by, v.created_by) AS created_by_enriched
    FROM public.v_fish_overview AS v
    LEFT JOIN public.fish AS f ON v.fish_code = f.fish_code
),

batch AS (
    SELECT
        fish_id,
        max(seed_batch_id) AS seed_batch_id
    FROM public.load_log_fish
    GROUP BY fish_id
),

prefer AS (
    SELECT
        b.*,
        coalesce(
            bt.seed_batch_id,
            substring(b.fish_code FROM '^FSH-([0-9]{2}[0-9A-Z]{4,})'),
            b.fish_code
        ) AS batch_label
    FROM base AS b
    LEFT JOIN batch AS bt ON b.id = bt.fish_id
),

links AS (
    SELECT
        fta.fish_id,
        string_agg(DISTINCT coalesce(fta.zygosity, 'unknown'), ', ' ORDER BY coalesce(fta.zygosity, 'unknown'))
            AS zygosity_text,
        string_agg(DISTINCT coalesce(reg.allele_nickname, ''), ', ' ORDER BY coalesce(reg.allele_nickname, ''))
            AS link_nicknames_text
    FROM public.fish_transgene_alleles AS fta
    LEFT JOIN public.transgene_allele_registry AS reg
        ON
            fta.transgene_base_code = reg.transgene_base_code
            AND fta.allele_number = reg.allele_number
    GROUP BY fta.fish_id
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
    l.zygosity_text,
    l.link_nicknames_text,
    (p.transgene_base_code_filled || ' : ' || p.allele_name_filled) AS genotype_display,
    CASE WHEN p.date_birth IS NOT NULL THEN (current_date - p.date_birth) END AS age_days,
    CASE WHEN p.date_birth IS NOT NULL THEN floor(((current_date - p.date_birth)::numeric) / 7)::int END AS age_weeks
FROM prefer AS p
LEFT JOIN links AS l ON p.id = l.fish_id;

COMMIT;
