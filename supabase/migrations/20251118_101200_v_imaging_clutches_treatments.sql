BEGIN;

CREATE OR REPLACE VIEW public.v_imaging_clutches_treatments AS
SELECT
    c.id                      AS clutch_id,
    t.id                      AS treatment_id,
    t.treat_code,
    t.kind_code,
    t.treat_text,
    t.notes                   AS treatment_notes,
    COALESCE(
        string_agg(DISTINCT p.plasmid_base_code, ',' ORDER BY p.plasmid_base_code),
        ''
    ) AS plasmid_base_codes,
    COALESCE(
        string_agg(DISTINCT r.rna_base_code, ',' ORDER BY r.rna_base_code),
        ''
    ) AS rna_base_codes,
    COALESCE(
        string_agg(DISTINCT d.dye_base_code, ',' ORDER BY d.dye_base_code),
        ''
    ) AS dye_base_codes

FROM public.clutches c
JOIN public.join_clutch_treatments jct
  ON jct.clutch_id = c.id
JOIN public.treatments t
  ON t.id = jct.treatment_id
LEFT JOIN public.join_treatment_plasmids jtp
  ON jtp.treatment_id = t.id
LEFT JOIN public.plasmids p
  ON p.id = jtp.plasmid_id
LEFT JOIN public.join_treatment_rnas jtr
  ON jtr.treatment_id = t.id
LEFT JOIN public.rnas r
  ON r.id = jtr.rna_id
LEFT JOIN public.join_treatment_dyes jtd
  ON jtd.treatment_id = t.id
LEFT JOIN public.dyes d
  ON d.id = jtd.dye_id

WHERE c.clutch_code LIKE 'IMG_CLT_%'
GROUP BY
    c.id,
    t.id,
    t.treat_code,
    t.kind_code,
    t.treat_text,
    t.notes;

COMMIT;
