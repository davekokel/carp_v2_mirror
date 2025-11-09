BEGIN;

-- Build-only, no renames. Drop if present, then create in dependency order.

DROP VIEW IF EXISTS public.v_fish_main CASCADE;
DROP VIEW IF EXISTS public.v_fish_unified CASCADE;
DROP VIEW IF EXISTS public.v_fluorescent_marker_rollup_by_base CASCADE;
DROP VIEW IF EXISTS public.v_fluorescent_marker_rollup CASCADE;

-- Per-base (fish_code, ft_code) rollup using FT catalog (ft_proteins)
CREATE VIEW public.v_fluorescent_marker_rollup_by_base AS
WITH base AS (
  SELECT f.fish_code, jft.ft_code, ftp.fluor_code, ftp.tag_code
  FROM public.join_fish_fluorescent_treatments jft
  JOIN public.fish f          ON f.id = jft.fish_id
  JOIN public.ft_proteins ftp ON ftp.ft_code = jft.ft_code
),
canon AS (
  SELECT
    b.fish_code,
    b.ft_code,
    COALESCE(fl.fluor_code, upper(b.fluor_code)) AS fluor_code,
    COALESCE(tg.tag_code, b.tag_code)            AS tag_code
  FROM base b
  LEFT JOIN public.fluors fl
    ON lower(fl.fluor_code)=lower(b.fluor_code)
    OR lower(COALESCE(fl.fluor_name,''))=lower(b.fluor_code)
  LEFT JOIN public.tags tg
    ON lower(tg.tag_code)=lower(COALESCE(b.tag_code,''))
    OR lower(COALESCE(tg.tag_name,''))=lower(COALESCE(b.tag_code,''))
),
agg AS (
  SELECT
    fish_code,
    ft_code,
    COALESCE(string_agg(DISTINCT fluor_code, ',' ORDER BY fluor_code),'') AS fluors,
    COALESCE(string_agg(DISTINCT COALESCE(tag_code,''), ',' ORDER BY COALESCE(tag_code,'')),'') AS tags
  FROM canon
  GROUP BY fish_code, ft_code
)
SELECT * FROM agg;

-- Fish-level (all FTs on a fish) rollup using FT catalog
CREATE VIEW public.v_fluorescent_marker_rollup AS
WITH base AS (
  SELECT f.fish_code, jft.ft_code, ftp.fluor_code, ftp.tag_code
  FROM public.join_fish_fluorescent_treatments jft
  JOIN public.fish f          ON f.id = jft.fish_id
  JOIN public.ft_proteins ftp ON ftp.ft_code = jft.ft_code
),
canon AS (
  SELECT
    b.fish_code,
    COALESCE(fl.fluor_code, upper(b.fluor_code)) AS fluor_code,
    COALESCE(tg.tag_code, b.tag_code)            AS tag_code
  FROM base b
  LEFT JOIN public.fluors fl
    ON lower(fl.fluor_code)=lower(b.fluor_code)
    OR lower(COALESCE(fl.fluor_name,''))=lower(b.fluor_code)
  LEFT JOIN public.tags tg
    ON lower(tg.tag_code)=lower(COALESCE(b.tag_code,''))
    OR lower(COALESCE(tg.tag_name,''))=lower(COALESCE(b.tag_code,''))
),
agg AS (
  SELECT
    fish_code,
    COALESCE(string_agg(DISTINCT fluor_code, ',' ORDER BY fluor_code),'') AS fluors,
    COALESCE(string_agg(DISTINCT COALESCE(tag_code,''), ',' ORDER BY COALESCE(tag_code,'')),'') AS tags
  FROM canon
  GROUP BY fish_code
)
SELECT f.fish_code,
       COALESCE(a.fluors,'') AS fluors,
       COALESCE(a.tags,'')   AS tags,
       ''::text              AS dyes
FROM public.fish f
LEFT JOIN agg a ON a.fish_code=f.fish_code;

-- Genotype pretty (unchanged): fish_code → marker label from transgene_alleles
CREATE VIEW public.v_fish_unified AS
WITH markers AS (
  SELECT f.fish_code,
         (ta.transgene_base_code||'('||ta.allele_name||')') AS marker_label
  FROM public.join_fish_transgene_alleles jf
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code=jf.transgene_base_code
   AND ta.allele_number      =jf.allele_number
  JOIN public.fish f ON f.id = jf.fish_id
  WHERE NULLIF(ta.allele_name,'') IS NOT NULL
),
gp AS (
  SELECT m.fish_code,
         string_agg(DISTINCT m.marker_label, ', ' ORDER BY m.marker_label) AS genotype_pretty
  FROM markers m
  GROUP BY m.fish_code
)
SELECT f.fish_code, COALESCE(gp.genotype_pretty,'') AS genotype_pretty
FROM public.fish f
LEFT JOIN gp ON gp.fish_code=f.fish_code;

-- Canonical v_fish_main with base-scoped and fish-level markers
CREATE VIEW public.v_fish_main AS
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
  r.fluors         AS fluors,       -- fish-level
  r.tags           AS tags,         -- fish-level
  rb.fluors        AS base_fluors,  -- base-scoped
  rb.tags          AS base_tags,    -- base-scoped
  ''::text         AS dyes
FROM public.fish f
LEFT JOIN public.join_fish_transgene_alleles jfta
  ON jfta.fish_id = f.id
LEFT JOIN public.transgene_alleles ta
  ON ta.transgene_base_code = jfta.transgene_base_code
 AND ta.allele_number      = jfta.allele_number
LEFT JOIN public.v_fish_unified u
  ON u.fish_code = f.fish_code
LEFT JOIN public.v_fluorescent_marker_rollup r
  ON r.fish_code = f.fish_code
LEFT JOIN public.v_fluorescent_marker_rollup_by_base rb
  ON rb.fish_code = f.fish_code
 AND rb.ft_code   = jfta.transgene_base_code;

COMMIT;
