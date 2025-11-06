BEGIN;

-- lookups
CREATE OR REPLACE VIEW public.v_fluors_lu AS
SELECT fluor_code AS code, COALESCE(fluor_name, fluor_code) AS label FROM public.fluors;
CREATE OR REPLACE VIEW public.v_tags_lu AS
SELECT tag_code AS code, COALESCE(tag_name, tag_code) AS label FROM public.tags;
CREATE OR REPLACE VIEW public.v_dyes_lu AS
SELECT dye_code AS code, COALESCE(dye_name, dye_code) AS label FROM public.dyes;

-- FT markers (uses final table names)
CREATE OR REPLACE VIEW public.v_fluorescent_treatment_markers AS
SELECT
  pm.ft_code,
  'protein'::text AS marker_kind,
  pm.fluor_code,
  pm.tag_code,
  vf.label        AS fluor_label,
  vt.label        AS tag_label,
  NULL::text      AS dye_code,
  NULL::text      AS dye_label,
  pm.created_at   AS created_at
FROM public.ft_proteins pm
LEFT JOIN public.v_fluors_lu vf ON vf.code = pm.fluor_code
LEFT JOIN public.v_tags_lu   vt ON vt.code = pm.tag_code
UNION ALL
SELECT
  d.ft_code,
  'dye'::text     AS marker_kind,
  NULL::text      AS fluor_code,
  NULL::text      AS tag_code,
  NULL::text      AS fluor_label,
  NULL::text      AS tag_label,
  d.dye_code,
  vd.label        AS dye_label,
  d.created_at    AS created_at
FROM public.join_dyes_fluorescent_treatments d
LEFT JOIN public.v_dyes_lu vd ON vd.code = d.dye_code;

-- Fish rollups (PK-first)
CREATE OR REPLACE VIEW public.v_fish_marker_rollup_by_ids
(fish_id, marker_count, fusion_rollup, fluor_rollup, tag_rollup, dye_rollup) AS
WITH links AS (
  SELECT
    j.fish_id,
    m.fluor_label,
    m.tag_label,
    m.dye_label,
    CASE
      WHEN COALESCE(m.fluor_label,'')<>'' AND COALESCE(m.tag_label,'')<>'' THEN m.fluor_label||'::'||m.tag_label
      WHEN COALESCE(m.fluor_label,'')<>'' THEN m.fluor_label
      WHEN COALESCE(m.dye_label,'')<>''   THEN m.dye_label
      ELSE '' END AS fusion_label
  FROM public.join_fish_fluorescent_treatments j
  JOIN public.v_fluorescent_treatment_markers m ON m.ft_code=j.ft_code
)
SELECT fish_id,
       COUNT(*)::int AS marker_count,
       COALESCE(NULLIF(string_agg(DISTINCT fusion_label, ', '),''),'') AS fusion_rollup,
       COALESCE(NULLIF(string_agg(DISTINCT COALESCE(fluor_label,''), ', '),''),'') AS fluor_rollup,
       COALESCE(NULLIF(string_agg(DISTINCT COALESCE(tag_label,''),   ', '),''),'') AS tag_rollup,
       COALESCE(NULLIF(string_agg(DISTINCT COALESCE(dye_label,''),   ', '),''),'') AS dye_rollup
FROM links
GROUP BY fish_id;

CREATE OR REPLACE VIEW public.v_fish_genotype_rollup_by_ids
(fish_id, allele_count, allele_codes, allele_nicknames, transgenes, genotype_rollup) AS
WITH jt AS (
  SELECT j.fish_id, ga.transgene_base_code, ga.allele_number,
         COALESCE(NULLIF(j.zygosity,''),'unk') AS zygosity,
         NULLIF(ga.allele_nickname,'') AS allele_nickname
  FROM public.join_fish_transgene_alleles j
  JOIN public.transgene_alleles ga
    ON ga.transgene_base_code=j.transgene_base_code
   AND ga.allele_number=j.allele_number
)
SELECT fish_id,
       COUNT(*)::int AS allele_count,
       COALESCE(NULLIF(string_agg(DISTINCT (transgene_base_code||':'||allele_number), ', '),''),'') AS allele_codes,
       COALESCE(NULLIF(string_agg(DISTINCT COALESCE(allele_nickname,''), ', '),''),'') AS allele_nicknames,
       COALESCE(NULLIF(string_agg(DISTINCT transgene_base_code, ', '),''),'') AS transgenes,
       COALESCE(NULLIF(string_agg(DISTINCT (transgene_base_code||':'||allele_number||
         CASE WHEN zygosity IS NOT NULL THEN ' ('||zygosity||')' ELSE '' END), ', '),''),'') AS genotype_rollup
FROM jt
GROUP BY fish_id;

CREATE OR REPLACE VIEW public.v_fish_overview_id
(fish_code, nickname, birthday, genetic_background, line_building_stage,
 allele_count, allele_codes, allele_nicknames, transgenes, genotype_rollup,
 fusion_rollup, fluor_rollup, tag_rollup, dye_rollup, created_at) AS
SELECT f.fish_code, f.nickname, f.dob,
       COALESCE(f.genetic_background,''), COALESCE(f.line_building_stage,''),
       COALESCE(g.allele_count,0), COALESCE(g.allele_codes,''), COALESCE(g.allele_nicknames,''),
       COALESCE(g.transgenes,''), COALESCE(g.genotype_rollup,''),
       COALESCE(m.fusion_rollup,''), COALESCE(m.fluor_rollup,''), COALESCE(m.tag_rollup,''), COALESCE(m.dye_rollup,''),
       f.created_at
FROM public.fish f
LEFT JOIN public.v_fish_genotype_rollup_by_ids g ON g.fish_id=f.id
LEFT JOIN public.v_fish_marker_rollup_by_ids   m ON m.fish_id=f.id;

-- unified treatments, final sources
CREATE OR REPLACE VIEW public.v_treatments_catalog
(code, kind, label, created_by, created_at, source) AS
SELECT tf.ft_code::text, 'fluorescent'::text, COALESCE(tf.ft_text,'')::text, tf.created_by, tf.created_at, 'treatments_fluorescent'::text
  FROM public.treatments_fluorescent tf
UNION ALL
SELECT tc.ct_code::text, 'chemical'::text, COALESCE(tc.ct_text,'')::text, tc.created_by, tc.created_at, 'treatments_chemical'::text
  FROM public.treatments_chemical tc
UNION ALL
SELECT tp.pt_code::text, 'physical'::text, COALESCE(tp.pt_text,'')::text, tp.created_by, tp.created_at, 'treatments_physical'::text
  FROM public.treatments_physical tp
UNION ALL
SELECT t.treat_code::text, COALESCE(NULLIF(t.kind,''),'other')::text, COALESCE(t.treat_text,'')::text, t.created_by, t.created_at, 'treatments'::text
  FROM public.treatments t;

-- tank views
CREATE OR REPLACE VIEW public.v_tanks AS
SELECT t.id AS tank_uuid, t.tank_code,
       COALESCE(l.code,'') AS location_code,
       COALESCE(t.status,'') AS status,
       t.created_at
FROM public.tanks t
LEFT JOIN public.locations l ON l.id=t.location_id;

CREATE OR REPLACE VIEW public.v_tank_pairs AS
SELECT tp.tank_pair_code, m.tank_code AS tank_code_female, f.tank_code AS tank_code_male, tp.created_at
FROM public.tank_pairs tp
LEFT JOIN public.tanks m ON m.id=tp.mother_tank_id
LEFT JOIN public.tanks f ON f.id=tp.father_tank_id;

COMMENT ON VIEW public.v_fish_overview_id IS 'CANON: single PK-based fish overview';
COMMIT;
