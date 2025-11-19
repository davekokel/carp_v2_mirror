BEGIN;

-- 1) Genotype → plasmids → fusions → fluors/tags, per clutch
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
        trim(b) AS base_code
    FROM clutch_genotypes cg,
         unnest(string_to_array(cg.genotype_base_codes, ',')) AS b
),
plasmid_links AS (
    SELECT
        e.clutch_id,
        p.id AS plasmid_id
    FROM exploded e
    JOIN public.plasmids p
      ON p.plasmid_base_code = e.base_code
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

-- 2) Update mem-histone ROI view to include genotype markers and all_marker_fluor_codes
DROP VIEW IF EXISTS public.v_imaging_mem_histone_rois;

CREATE VIEW public.v_imaging_mem_histone_rois AS
SELECT
    c.id                      AS clutch_id,
    c.clutch_code,
    c.clutch_date,
    c.estimated_egg_count,
    c.notes                   AS clutch_notes,

    -- genotype info
    c.genotype_cross_label,
    c.genotype_base_codes,
    c.genotype_allele_codes,
    c.genotype_pretty,

    gm.genotype_marker_fluor_codes,
    gm.genotype_marker_tag_codes,

    -- treatment + marker info at clutch level
    tr.treatment_id,
    tr.treat_code,
    tr.treat_text,
    tr.kind_code,
    tr.treatment_notes,
    tr.plasmid_base_codes     AS treatment_plasmid_base_codes,
    tr.rna_base_codes         AS treatment_rna_base_codes,
    tr.dye_base_codes         AS treatment_dye_base_codes,
    tr.marker_fluor_codes     AS treatment_marker_fluor_codes,
    tr.marker_tag_codes       AS treatment_marker_tag_codes,

    -- combined marker fluor picture (genotype + treatment)
    TRIM(BOTH ',' FROM
        CONCAT(
            COALESCE(gm.genotype_marker_fluor_codes, ''),
            CASE WHEN gm.genotype_marker_fluor_codes IS NOT NULL
                     AND gm.genotype_marker_fluor_codes <> ''
                     AND tr.marker_fluor_codes IS NOT NULL
                     AND tr.marker_fluor_codes <> ''
                 THEN ',' ELSE '' END,
            COALESCE(tr.marker_fluor_codes, '')
        )
    ) AS all_marker_fluor_codes,

    -- combined base-code picture (genotype + treatment)
    TRIM(BOTH ',' FROM
        CONCAT(
            COALESCE(c.genotype_base_codes, ''),
            CASE WHEN c.genotype_base_codes IS NOT NULL
                     AND c.genotype_base_codes <> ''
                     AND (tr.plasmid_base_codes IS NOT NULL
                          OR tr.rna_base_codes IS NOT NULL
                          OR tr.dye_base_codes IS NOT NULL)
                 THEN ',' ELSE '' END,
            COALESCE(tr.plasmid_base_codes, ''),
            CASE WHEN tr.plasmid_base_codes IS NOT NULL
                     AND tr.plasmid_base_codes <> ''
                     AND tr.rna_base_codes IS NOT NULL
                 THEN ',' ELSE '' END,
            COALESCE(tr.rna_base_codes, ''),
            CASE WHEN (tr.plasmid_base_codes IS NOT NULL
                       OR tr.rna_base_codes IS NOT NULL)
                     AND tr.dye_base_codes IS NOT NULL
                 THEN ',' ELSE '' END,
            COALESCE(tr.dye_base_codes, '')
        )
    ) AS all_base_codes,

    -- membership (one row per imaging sheet row)
    m.id                      AS membership_id,
    m.sheet_row_index,
    m.date_born,
    m.zf_female_genotype_text,
    m.zf_male_genotype_text,
    m.date_mount,
    m.mount_id,
    m.data_location           AS data_path,

    -- simple ROI indexing/name (per mem-histone row)
    1                         AS roi_index,
    regexp_replace(
        regexp_replace(m.data_location, '\\\\', '/', 'g'),
        '^.*/',
        ''
    )                         AS roi_name

FROM public.clutches c
JOIN public.imaging_clutch_memberships m
  ON m.clutch_id = c.id
LEFT JOIN public.v_imaging_clutches_treatments tr
  ON tr.clutch_id = c.id
LEFT JOIN public.v_imaging_clutch_genotype_markers gm
  ON gm.clutch_id = c.id
WHERE c.clutch_code LIKE 'IMG_CLT_%';

COMMIT;
