BEGIN;

CREATE OR REPLACE VIEW public.v_fish_overview AS
WITH jt AS (  -- allele rows per fish, nickname-first label
  SELECT
    f.fish_code,
    jfta.transgene_base_code,
    jfta.allele_number,
    ta.allele_name,
    ta.allele_nickname,
    COALESCE(NULLIF(ta.allele_nickname,''), ta.allele_name) AS allele_label
  FROM public.join_fish_transgene_alleles jfta
  JOIN public.fish f ON f.id = jfta.fish_id
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = jfta.transgene_base_code
   AND ta.allele_number       = jfta.allele_number
),
mk AS (  -- markers string
  SELECT
    fish_code,
    string_agg(
      DISTINCT CASE
        WHEN COALESCE(allele_label,'') <> '' THEN transgene_base_code||'('||allele_label||')'
        ELSE transgene_base_code
      END,
      ',' ORDER BY
      CASE
        WHEN COALESCE(allele_label,'') <> '' THEN transgene_base_code||'('||allele_label||')'
        ELSE transgene_base_code
      END
    ) AS markers
  FROM jt
  GROUP BY fish_code
),
gp AS (  -- pretty genotype (nickname-first)
  SELECT
    fish_code,
    string_agg(
      DISTINCT (transgene_base_code||'('||allele_label||')'),
      ', ' ORDER BY (transgene_base_code||'('||allele_label||')')
    ) AS genotype_pretty
  FROM jt
  WHERE COALESCE(allele_label,'') <> ''
  GROUP BY fish_code
),
fu AS (  -- fusion rollups via plasmids → join_plasmid_fusions → fusions
  SELECT
    jt.fish_code,
    COALESCE(string_agg(DISTINCT fl.fluor_code, ','), '')          AS fluors,
    COALESCE(string_agg(DISTINCT NULLIF(tg.tag_code,''), ','), '') AS tags,
    COALESCE(
      string_agg(
        DISTINCT (COALESCE(fl.fluor_code,'')||COALESCE(':'||NULLIF(tg.tag_code,''),'')),
        ',' ORDER BY (COALESCE(fl.fluor_code,'')||COALESCE(':'||NULLIF(tg.tag_code,''),''))
      ),
      ''
    ) AS fusions,
    COUNT(DISTINCT pf.id) AS n_fusions
  FROM jt
  JOIN public.plasmids p                ON p.code = jt.transgene_base_code
  JOIN public.join_plasmid_fusions jpf  ON jpf.plasmid_id = p.id
  JOIN public.fusions pf                ON pf.id = jpf.fusion_id
  LEFT JOIN public.fluors fl            ON fl.id = pf.fluor_id
  LEFT JOIN public.tags   tg            ON tg.id = pf.tag_id
  GROUP BY jt.fish_code
)
SELECT
  CASE
    WHEN f.fish_code ~ '^FSH-[A-Z0-9]{8}$' THEN f.fish_code
    WHEN f.fish_code ~ '^\\d+$'            THEN 'FSH-'||lpad(f.fish_code,8,'0')
    ELSE f.fish_code
  END                               AS fish_code_display,
  f.fish_code                       AS fish_code_raw,
  COALESCE(f.nickname,'')           AS nickname,
  f.birthday                        AS birthday,
  COALESCE(f.genetic_background,'') AS genetic_background,
  COALESCE(f.in_breeding_stage,'')  AS line_building_stage,
  COALESCE(gp.genotype_pretty,'')   AS genotype_pretty,
  COALESCE(mk.markers,'')           AS markers,
  COALESCE(fu.fluors,'')            AS fluors,
  COALESCE(fu.tags,'')              AS tags,
  COALESCE(fu.fusions,'')           AS fusions,
  COALESCE(fu.n_fusions,0)          AS n_fusions,
  ''::text                          AS dyes,
  f.created_at
FROM public.fish f
LEFT JOIN gp ON gp.fish_code = f.fish_code
LEFT JOIN mk ON mk.fish_code = f.fish_code
LEFT JOIN fu ON fu.fish_code = f.fish_code;

COMMIT;
