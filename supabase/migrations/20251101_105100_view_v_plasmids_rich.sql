BEGIN;

/* Rich plasmids view:
   - One row per plasmid (plasmids.code)
   - Aggregates fusion names, fluor names, tag names
   - Preserves base fields (nickname, resistance, supports_invitro_rna, notes, created_by, created_at)
*/
CREATE OR REPLACE VIEW public.v_plasmids_rich AS
WITH j AS (
  SELECT
    jpf.plasmid_code,
    jpf.fusion_code
  FROM public.join_plasmid_fusions jpf
),
fx AS (
  SELECT
    j.plasmid_code,
    f.fusion_name,
    fl.fluor_name,
    tg.tag_name
  FROM j
  JOIN public.fusions f   ON f.fusion_code = j.fusion_code
  LEFT JOIN public.fluors fl ON fl.fluor_code = f.fluor_code
  LEFT JOIN public.tags   tg ON tg.tag_code   = f.tag_code
),
agg AS (
  SELECT
    plasmid_code,
    /* Distinct, sorted lists for stable display */
    array_agg(DISTINCT fusion_name ORDER BY fusion_name) AS fusion_names,
    array_agg(DISTINCT fluor_name  ORDER BY fluor_name)  AS fluor_names,
    array_agg(DISTINCT tag_name    ORDER BY tag_name)    AS tag_names
  FROM fx
  GROUP BY plasmid_code
)
SELECT
  p.code                    AS plasmid_code,
  p.name                    AS plasmid_name,
  p.nickname                AS nickname,
  p.resistance              AS resistance,
  p.supports_invitro_rna    AS supports_invitro_rna,
  p.notes                   AS notes,
  p.created_by              AS created_by,
  p.created_at              AS created_at,
  /* Pretty comma-separated strings */
  COALESCE(array_to_string(a.fusion_names, ', '), '') AS fusion_names,
  COALESCE(array_to_string(a.fluor_names,  ', '), '') AS fluor_names,
  COALESCE(array_to_string(a.tag_names,    ', '), '') AS tag_names
FROM public.plasmids p
LEFT JOIN agg a ON a.plasmid_code = p.code
ORDER BY p.code;

COMMIT;
