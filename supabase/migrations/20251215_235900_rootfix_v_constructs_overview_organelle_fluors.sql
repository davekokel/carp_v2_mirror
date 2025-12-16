BEGIN;

CREATE OR REPLACE VIEW public.v_constructs_overview AS
WITH base AS (
  SELECT
    c.id,
    c.construct_code,
    c.construct_kind,
    c.construct_name,
    c.resistance,
    COALESCE(c.plasmid_notes, c.description, ''::text) AS description,
    c.injection_use_plasmid,
    c.injection_use_rna,
    c.injection_use_crispr,
    c.created_at
  FROM public.constructs c
),
fusion_join AS (
  SELECT
    cf.construct_id,
    count(DISTINCT cf.fusion_id) AS n_fusions,

    COALESCE(string_agg(DISTINCT
      CASE
        WHEN fl.id IS NULL THEN NULL::text
        ELSE (
          COALESCE(fl.nickname, fl.display_name, fl.code)
          || COALESCE('-'::text || COALESCE(t.nickname, t.display_name, t.code), ''::text)
          || '('::text || COALESCE(f.tag_pos, ''::text) || ')'::text
        )
      END,
      '||'::text
    ), ''::text) AS fusion_pretty,

    COALESCE(string_agg(DISTINCT
      CASE
        WHEN fl.id IS NULL THEN NULL::text
        ELSE
          COALESCE(fl.nickname, fl.display_name, fl.code)
          || CASE
               WHEN COALESCE(t.localization, ''::text) = ''::text THEN ''::text
               ELSE '-'::text || COALESCE(t.localization, ''::text)
             END
      END,
      '||'::text
    ), ''::text) AS organelle_fluors

  FROM public.construct_fusions cf
  JOIN public.fusions f ON f.id = cf.fusion_id
  LEFT JOIN public.fluors fl ON fl.id = f.fluor_id
  LEFT JOIN public.tags t ON t.id = f.tag_id
  GROUP BY cf.construct_id
)
SELECT
  b.construct_code,
  b.construct_kind,
  b.construct_name,
  b.resistance,
  b.description,
  COALESCE(fj.n_fusions, 0::bigint) AS n_fusions,
  COALESCE(fj.fusion_pretty, ''::text) AS fusion_pretty,
  COALESCE(fj.organelle_fluors, ''::text) AS organelle_fluors,
  b.injection_use_plasmid,
  b.injection_use_rna,
  b.injection_use_crispr,
  b.created_at
FROM base b
LEFT JOIN fusion_join fj ON fj.construct_id = b.id;

COMMIT;
