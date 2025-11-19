BEGIN;

CREATE OR REPLACE VIEW public.v_imaging_treatments_markers AS
WITH fusions_from_plasmids AS (
    SELECT DISTINCT jtp.treatment_id, jpf.fusion_id
    FROM public.join_treatment_plasmids jtp
    JOIN public.join_plasmid_fusions jpf
      ON jpf.plasmid_id = jtp.plasmid_id
),
fusions_from_rnas AS (
    SELECT DISTINCT jtr.treatment_id, jrf.fusion_id
    FROM public.join_treatment_rnas jtr
    JOIN public.join_rna_fusions jrf
      ON jrf.rna_id = jtr.rna_id
),
all_fusions AS (
    SELECT treatment_id, fusion_id FROM fusions_from_plasmids
    UNION
    SELECT treatment_id, fusion_id FROM fusions_from_rnas
)
SELECT
    af.treatment_id,
    COALESCE(
        string_agg(DISTINCT fl.fluor_code, ',' ORDER BY fl.fluor_code),
        ''
    ) AS fluor_codes,
    COALESCE(
        string_agg(DISTINCT fl.fluor_name, ',' ORDER BY fl.fluor_name),
        ''
    ) AS fluor_names,
    COALESCE(
        string_agg(DISTINCT tg.tag_code, ',' ORDER BY tg.tag_code),
        ''
    ) AS tag_codes,
    COALESCE(
        string_agg(DISTINCT tg.tag_name, ',' ORDER BY tg.tag_name),
        ''
    ) AS tag_names
FROM all_fusions af
JOIN public.fusions f
  ON f.id = af.fusion_id
LEFT JOIN public.fluors fl
  ON fl.id = f.fluor_id
LEFT JOIN public.tags tg
  ON tg.id = f.tag_id
GROUP BY af.treatment_id;

COMMIT;
