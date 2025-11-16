-- 2025-11-15: Redefine v_fish_overview with canonical transgene fields.
-- Fields preserved:
--   fish_code_display, fish_code_raw, nickname, birthday,
--   genetic_background, line_building_stage, genotype_pretty,
--   markers, fluors, tags, fusions, n_fusions, dyes, created_at.
-- New explicit fields:
--   transgene_canonical = Tg(base)allele_name    (allele_name = 'gu' || allele_number)
--   transgene_nickname  = Tg(base)allele_nickname
-- No fallbacks: if allele_name or allele_nickname are NULL/empty, that allele is omitted.

BEGIN;

CREATE OR REPLACE VIEW public.v_fish_overview AS
WITH jt AS (
  SELECT
    f1.fish_code,
    jfta.transgene_base_code,
    jfta.allele_number,
    ta.allele_name,
    ta.allele_nickname,
    COALESCE(NULLIF(ta.allele_nickname, ''::text), ta.allele_name) AS allele_label
  FROM public.join_fish_transgene_alleles jfta
  JOIN public.fish f1
    ON f1.id = jfta.fish_id
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = jfta.transgene_base_code
   AND ta.allele_number       = jfta.allele_number
),
mk AS (
  -- markers: keep existing behavior (uses allele_label)
  SELECT
    jt.fish_code,
    string_agg(
      DISTINCT
        CASE
          WHEN COALESCE(jt.allele_label, ''::text) <> ''::text
            THEN ((jt.transgene_base_code || '('::text) || jt.allele_label) || ')'::text
          ELSE jt.transgene_base_code
        END,
      ','::text
      ORDER BY
        CASE
          WHEN COALESCE(jt.allele_label, ''::text) <> ''::text
            THEN ((jt.transgene_base_code || '('::text) || jt.allele_label) || ')'::text
          ELSE jt.transgene_base_code
        END
    ) AS markers
  FROM jt
  GROUP BY jt.fish_code
),
tg AS (
  -- canonical + nickname transgene labels with no fallback
  SELECT
    x.fish_code,

    -- canonical transgene label: Tg(base)allele_name
    string_agg(
      DISTINCT x.canonical_label,
      ', '::text
      ORDER BY x.canonical_label
    ) AS transgene_canonical,

    -- nickname label: Tg(base)allele_nickname (no fallback)
    string_agg(
      DISTINCT x.nickname_label,
      ', '::text
      ORDER BY x.nickname_label
    ) AS transgene_nickname

  FROM (
    SELECT
      jt.fish_code,
      CASE
        WHEN jt.allele_name IS NOT NULL AND btrim(jt.allele_name) <> ''::text
          THEN 'Tg(' || jt.transgene_base_code || ')' || jt.allele_name
        ELSE NULL
      END AS canonical_label,
      CASE
        WHEN jt.allele_nickname IS NOT NULL AND btrim(jt.allele_nickname) <> ''::text
          THEN 'Tg(' || jt.transgene_base_code || ')' || jt.allele_nickname
        ELSE NULL
      END AS nickname_label
    FROM jt
  ) AS x
  GROUP BY x.fish_code
),
fu AS (
  -- fusions / fluors / tags: unchanged from original
  SELECT
    jt.fish_code,
    COALESCE(string_agg(DISTINCT fl.fluor_code, ','::text), ''::text) AS fluors,
    COALESCE(
      string_agg(DISTINCT NULLIF(tg.tag_code, ''::text), ','::text),
      ''::text
    ) AS tags,
    COALESCE(
      string_agg(
        DISTINCT COALESCE(fl.fluor_code, ''::text)
                 || COALESCE(':'::text || NULLIF(tg.tag_code, ''::text), ''::text),
        ','::text
        ORDER BY
          (COALESCE(fl.fluor_code, ''::text)
           || COALESCE(':'::text || NULLIF(tg.tag_code, ''::text), ''::text))
      ),
      ''::text
    ) AS fusions,
    COUNT(DISTINCT pf.id) AS n_fusions
  FROM jt
  JOIN public.plasmids p
    ON p.code = jt.transgene_base_code
  JOIN public.join_plasmid_fusions jpf
    ON jpf.plasmid_id = p.id
  JOIN public.fusions pf
    ON pf.id = jpf.fusion_id
  LEFT JOIN public.fluors fl
    ON fl.id = pf.fluor_id
  LEFT JOIN public.tags tg
    ON tg.id = pf.tag_id
  GROUP BY jt.fish_code
)
SELECT
  CASE
    WHEN f.fish_code ~ '^FSH-[A-Z0-9]{8}$'::text
      THEN f.fish_code
    WHEN f.fish_code ~ '^\d+$'::text
      THEN 'FSH-'::text || lpad(f.fish_code, 8, '0'::text)
    ELSE
      f.fish_code
  END                                   AS fish_code_display,
  f.fish_code                           AS fish_code_raw,
  COALESCE(f.nickname, ''::text)        AS nickname,
  f.birthday,
  COALESCE(f.genetic_background, ''::text) AS genetic_background,
  COALESCE(f.in_breeding_stage, ''::text)  AS line_building_stage,

  -- genotype_pretty is now canonical Tg(base)allele_name
  COALESCE(tg.transgene_canonical, ''::text) AS genotype_pretty,

  COALESCE(mk.markers, ''::text)        AS markers,
  COALESCE(fu.fluors, ''::text)         AS fluors,
  COALESCE(fu.tags, ''::text)           AS tags,
  COALESCE(fu.fusions, ''::text)        AS fusions,
  COALESCE(fu.n_fusions, 0::bigint)     AS n_fusions,
  ''::text                              AS dyes,
  f.created_at,

  -- explicit canonical + nickname fields
  COALESCE(tg.transgene_canonical, ''::text) AS transgene_canonical,
  COALESCE(tg.transgene_nickname, ''::text)  AS transgene_nickname

FROM public.fish f
LEFT JOIN tg ON tg.fish_code = f.fish_code
LEFT JOIN mk ON mk.fish_code = f.fish_code
LEFT JOIN fu ON fu.fish_code = f.fish_code;

COMMIT;
