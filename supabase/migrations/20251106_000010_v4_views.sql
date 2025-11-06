BEGIN;
CREATE OR REPLACE VIEW public.v_fluors_lu AS SELECT fluor_code AS code, COALESCE(fluor_name,fluor_code) AS label FROM public.fluors;
CREATE OR REPLACE VIEW public.v_tags_lu AS SELECT tag_code AS code, COALESCE(tag_name,tag_code) AS label FROM public.tags;
CREATE OR REPLACE VIEW public.v_dyes_lu AS SELECT dye_code AS code, COALESCE(dye_name,dye_code) AS label FROM public.dyes;
CREATE OR REPLACE VIEW public.v_fluorescent_treatment_markers AS
SELECT pm.ft_code,'protein'::text AS marker_kind,pm.fluor_code,pm.tag_code,vf.label AS fluor_label,vt.label AS tag_label,NULL::text AS dye_code,NULL::text AS dye_label,pm.created_at AS created_at
FROM public.ft_proteins pm
LEFT JOIN public.v_fluors_lu vf ON vf.code=pm.fluor_code
LEFT JOIN public.v_tags_lu   vt ON vt.code=pm.tag_code
UNION ALL
SELECT d.ft_code,'dye'::text,NULL::text,NULL::text,NULL::text,NULL::text,d.dye_code,vd.label,d.created_at
FROM public.ft_dyes d
LEFT JOIN public.v_dyes_lu vd ON vd.code=d.dye_code;
CREATE OR REPLACE VIEW public.v_fish_marker_rollup_by_ids (fish_id,marker_count,fusion_rollup,fluor_rollup,tag_rollup,dye_rollup) AS
WITH links AS (
  SELECT j.fish_id,m.fluor_label,m.tag_label,m.dye_label,
         CASE WHEN COALESCE(m.fluor_label,'')<>'' AND COALESCE(m.tag_label,'')<>'' THEN m.fluor_label||'::'||m.tag_label
              WHEN COALESCE(m.fluor_label,'')<>'' THEN m.fluor_label
              WHEN COALESCE(m.dye_label,'')<>''   THEN m.dye_label
              ELSE '' END AS fusion_label
  FROM public.join_fish_fluorescent_treatments j
  JOIN public.v_fluorescent_treatment_markers m ON m.ft_code=j.ft_code
)
SELECT fish_id,
       COUNT(*)::int,
       COALESCE(NULLIF(string_agg(DISTINCT fusion_label, ', '),''),''),
       COALESCE(NULLIF(string_agg(DISTINCT COALESCE(fluor_label,''), ', '),''),''),
       COALESCE(NULLIF(string_agg(DISTINCT COALESCE(tag_label,''),   ', '),''),''),
       COALESCE(NULLIF(string_agg(DISTINCT COALESCE(dye_label,''),   ', '),''),'')
FROM links
GROUP BY fish_id;
CREATE OR REPLACE VIEW public.v_fish_genotype_rollup_by_ids (fish_id,allele_count,allele_codes,allele_nicknames,transgenes,genotype_rollup) AS
WITH jt AS (
  SELECT j.fish_id,ga.transgene_base_code,ga.allele_number,COALESCE(NULLIF(j.zygosity,''),'unk') AS zygosity,NULLIF(ga.allele_nickname,'') AS allele_nickname
  FROM public.join_fish_transgene_alleles j
  JOIN public.transgene_alleles ga ON ga.transgene_base_code=j.transgene_base_code AND ga.allele_number=j.allele_number
)
SELECT fish_id,
       COUNT(*)::int,
       COALESCE(NULLIF(string_agg(DISTINCT (transgene_base_code||':'||allele_number), ', '),''),''),
       COALESCE(NULLIF(string_agg(DISTINCT COALESCE(allele_nickname,''), ', '),''),''),
       COALESCE(NULLIF(string_agg(DISTINCT transgene_base_code, ', '),''),''),
       COALESCE(NULLIF(string_agg(DISTINCT (transgene_base_code||':'||allele_number||CASE WHEN zygosity IS NOT NULL THEN ' ('||zygosity||')' ELSE '' END), ', '),''),'')
FROM jt
GROUP BY fish_id;
CREATE OR REPLACE VIEW public.v_fish_overview_id
(fish_code,nickname,birthday,genetic_background,line_building_stage,allele_count,allele_codes,allele_nicknames,transgenes,genotype_rollup,fusion_rollup,fluor_rollup,tag_rollup,dye_rollup,created_at) AS
SELECT f.fish_code,f.nickname,f.dob,COALESCE(f.genetic_background,''),COALESCE(f.line_building_stage,''),COALESCE(g.allele_count,0),COALESCE(g.allele_codes,''),COALESCE(g.allele_nicknames,''),COALESCE(g.transgenes,''),COALESCE(g.genotype_rollup,''),COALESCE(m.fusion_rollup,''),COALESCE(m.fluor_rollup,''),COALESCE(m.tag_rollup,''),COALESCE(m.dye_rollup,''),f.created_at
FROM public.fish f
LEFT JOIN public.v_fish_genotype_rollup_by_ids g ON g.fish_id=f.id
LEFT JOIN public.v_fish_marker_rollup_by_ids   m ON m.fish_id=f.id;
COMMIT;
