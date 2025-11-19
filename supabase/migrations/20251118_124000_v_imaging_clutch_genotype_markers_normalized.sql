BEGIN;

DROP VIEW IF EXISTS public.v_imaging_clutch_genotype_markers;

CREATE VIEW public.v_imaging_clutch_genotype_markers AS
WITH clutch_genotypes AS (
    SELECT
        c.id AS clutch_id,
        c.genotype_base_codes
    FROM public.clutches c
    WHERE c.clutch_code LIKE 'IMG_CLT_%'
      AND c.genotype_base_codes IS NOT NULL
      AND c.genotype_base_codes <> ''
),
exploded AS (
    SELECT
        cg.clutch_id,
        trim(b) AS raw_code,
        CASE
            -- pDQM005 -> PDQM-5
            WHEN trim(b) ~* '^pDQM[0-9]+' THEN
                'PDQM-' || (regexp_replace(trim(b), '^pDQM', '', 'i')::int)::text
            ELSE trim(b)
        END AS norm_code
    FROM clutch_genotypes cg,
         unnest(string_to_array(cg.genotype_base_codes, ',')) AS b
),
plasmid_links AS (
    SELECT
        e.clutch_id,
        p.id AS plasmid_id
    FROM exploded e
    JOIN public.plasmids p
      ON p.plasmid_base_code = e.norm_code
),
fusion_links AS (
    SELECT DISTINCT
        pl.clutch_id,
        f.id        AS fusion_id,
        fl.id       AS fluor_id,
        fl.fluor_code,
        tg.id       AS tag_id,
        tg.tag_code
    FROM plasmid_links pl
    JOIN public.join_plasmid_fusions jpf
      ON jpf.plasmid_id = pl.plasmid_id
    JOIN public.fusions f
      ON f.id = jpf.fusion_id
    LEFT JOIN public.fluors fl
      ON fl.id = f.fluor_id
    LEFT JOIN public.tags tg
      ON tg.id = f.tag_id
)
SELECT
    clutch_id,
    COALESCE(
        string_agg(DISTINCT fluor_code, ',' ORDER BY fluor_code),
        ''
    ) AS genotype_marker_fluor_codes,
    COALESCE(
        string_agg(DISTINCT tag_code, ',' ORDER BY tag_code),
        ''
    ) AS genotype_marker_tag_codes
FROM fusion_links
GROUP BY clutch_id;

COMMIT;
