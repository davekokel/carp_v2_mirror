BEGIN;

CREATE OR REPLACE VIEW public.v_fish_genotype_rollup_by_ids AS
WITH jt AS (
  SELECT j.fish_id,
         ga.transgene_base_code,
         ga.allele_number,
         COALESCE(NULLIF(j.zygosity,''),'unk') AS zygosity,
         NULLIF(ga.allele_nickname,'')        AS allele_nickname
  FROM public.join_fish_transgene_alleles j
  JOIN public.transgene_alleles ga
    ON ga.transgene_base_code = j.transgene_base_code
   AND ga.allele_number      = j.allele_number
)
SELECT fish_id,
       COUNT(*)::int AS allele_count,
       COALESCE(NULLIF(string_agg(DISTINCT (transgene_base_code||':'||allele_number),', '),''),'')      AS allele_codes,
       COALESCE(NULLIF(string_agg(DISTINCT COALESCE(allele_nickname,''),', '),''),'')                    AS allele_nicknames,
       COALESCE(NULLIF(string_agg(DISTINCT transgene_base_code,', '),''),'')                             AS transgenes,
       COALESCE(NULLIF(string_agg(DISTINCT
         (transgene_base_code||':'||allele_number)||
         CASE WHEN zygosity IS NOT NULL THEN ' ('||zygosity||')' ELSE '' END
       ,', '),''),'') AS genotype_rollup
FROM jt
GROUP BY fish_id;

CREATE OR REPLACE VIEW public.v_fish_marker_rollup_by_ids AS
WITH j AS (
  SELECT f.id AS fish_id, jft.ft_code
  FROM public.fish f
  LEFT JOIN public.join_fish_fluorescent_treatments jft ON jft.fish_id = f.id
)
SELECT x.fish_id,
       COALESCE((SELECT COUNT(DISTINCT j.ft_code)::int FROM j WHERE j.fish_id=x.fish_id),0) AS marker_count,
       ''::text AS fusion_rollup,
       COALESCE((SELECT string_agg(DISTINCT p.fluor_code,',' ORDER BY p.fluor_code)
                 FROM j LEFT JOIN public.ft_proteins p ON p.ft_code=j.ft_code
                 WHERE j.fish_id=x.fish_id AND p.fluor_code IS NOT NULL),'') AS fluor_rollup,
       COALESCE((SELECT string_agg(DISTINCT p.tag_code,',' ORDER BY p.tag_code)
                 FROM j LEFT JOIN public.ft_proteins p ON p.ft_code=j.ft_code
                 WHERE j.fish_id=x.fish_id AND p.tag_code   IS NOT NULL),'') AS tag_rollup,
       COALESCE((SELECT string_agg(DISTINCT d.dye_code,',' ORDER BY d.dye_code)
                 FROM j LEFT JOIN public.ft_dyes d ON d.ft_code=j.ft_code
                 WHERE j.fish_id=x.fish_id AND d.dye_code   IS NOT NULL),'') AS dye_rollup
FROM (SELECT fish.id AS fish_id FROM public.fish) x;

CREATE OR REPLACE VIEW public.v_fish_unified AS
WITH markers AS (
  SELECT f.fish_code,
         (ta.transgene_base_code||'('||ta.allele_name||')') AS marker_label
  FROM public.join_fish_transgene_alleles jf
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = jf.transgene_base_code
   AND ta.allele_number      = jf.allele_number
  JOIN public.fish f ON f.id = jf.fish_id
  WHERE NULLIF(ta.allele_name,'') IS NOT NULL
), gp AS (
  SELECT m.fish_code,
         string_agg(DISTINCT m.marker_label, ', ' ORDER BY m.marker_label) AS genotype_pretty
  FROM markers m
  GROUP BY m.fish_code
)
SELECT f.fish_code, COALESCE(gp.genotype_pretty,'') AS genotype_pretty
FROM public.fish f
LEFT JOIN gp ON gp.fish_code=f.fish_code;

CREATE OR REPLACE VIEW public.v_fluorescent_marker_rollup AS
WITH m AS (
  SELECT f.fish_code,
         rid.fluor_rollup,
         rid.tag_rollup,
         rid.dye_rollup
  FROM public.fish f
  LEFT JOIN public.v_fish_marker_rollup_by_ids rid ON rid.fish_id=f.id
), mk AS (
  SELECT f.fish_code,
         string_agg(DISTINCT
           CASE
             WHEN ta.allele_name IS NOT NULL AND ta.allele_name<>'' THEN (j.transgene_base_code||'('||ta.allele_name||')')
             ELSE j.transgene_base_code
           END
         ,',' ORDER BY
           CASE
             WHEN ta.allele_name IS NOT NULL AND ta.allele_name<>'' THEN (j.transgene_base_code||'('||ta.allele_name||')')
             ELSE j.transgene_base_code
           END
         ) AS markers
  FROM public.join_fish_transgene_alleles j
  JOIN public.fish f ON f.id=j.fish_id
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code=j.transgene_base_code AND ta.allele_number=j.allele_number
  GROUP BY f.fish_code
)
SELECT f.fish_code,
       COALESCE(mk.markers,'') AS markers,
       COALESCE(m.fluor_rollup,'') AS fluors,
       COALESCE(m.tag_rollup,'')   AS tags,
       COALESCE(m.dye_rollup,'')   AS dyes
FROM public.fish f
LEFT JOIN mk ON mk.fish_code=f.fish_code
LEFT JOIN m  ON m.fish_code =f.fish_code;

CREATE OR REPLACE VIEW public.v_fish_main AS
SELECT
  f.fish_code,
  f.nickname,
  f.dob,
  COALESCE(f.genetic_background,'')  AS genetic_background,
  COALESCE(f.line_building_stage,'') AS line_building_stage,
  jfta.transgene_base_code,
  jfta.allele_number,
  ta.allele_name,
  ta.allele_nickname,
  COALESCE(NULLIF(ta.allele_name,''), jfta.transgene_base_code||'-'||LPAD(jfta.allele_number::text,2,'0')) AS transgene_pretty_nickname,
  jfta.transgene_base_code AS transgene_pretty_name,
  u.genotype_pretty,
  r.fluors,
  r.tags,
  r.dyes
FROM public.fish f
LEFT JOIN public.join_fish_transgene_alleles jfta
  ON jfta.fish_id = f.id
LEFT JOIN public.transgene_alleles ta
  ON ta.transgene_base_code=jfta.transgene_base_code
 AND ta.allele_number     =jfta.allele_number
LEFT JOIN public.v_fish_unified u
  ON u.fish_code=f.fish_code
LEFT JOIN public.v_fluorescent_marker_rollup r
  ON r.fish_code=f.fish_code;

COMMIT;
