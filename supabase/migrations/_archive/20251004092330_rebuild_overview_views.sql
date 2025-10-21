BEGIN;

CREATE OR REPLACE VIEW public.v_fish_overview_with_label AS
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
        f.created_by AS created_by_enriched
    FROM public.v_fish_overview AS v
    LEFT JOIN public.fish AS f
        ON v.id = f.id_uuid
),

prefer_seed AS (
    SELECT
        b.*,
        coalesce(
            (
                SELECT ll.seed_batch_id
                FROM public.load_log_fish AS ll
                WHERE ll.fish_id = b.id
                ORDER BY ll.logged_at DESC
                LIMIT 1
            ),
            regexp_replace(b.fish_code, '^FSH-([0-9]{8}-[0-9]{6})-.*$', '\1')
        ) AS batch_label
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
    null::text AS rna_injections_text
FROM prefer_seed AS p;

COMMIT;
