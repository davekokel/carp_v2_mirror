BEGIN;

CREATE OR REPLACE VIEW public.v_constructs_overview AS

-- plasmid constructs
SELECT
  p.id              AS construct_id,
  p.code            AS code,
  p.construct_type  AS construct_type,
  p.nickname        AS nickname,
  p.name            AS name,
  string_agg(DISTINCT fl.fluor_code, ',' ORDER BY fl.fluor_code) AS fluors,
  string_agg(DISTINCT tg.tag_code,   ',' ORDER BY tg.tag_code)   AS tag_codes,
  string_agg(
    DISTINCT (fl.fluor_code || ':' || tg.tag_code || ':' || fu.tag_pos),
    ',' ORDER BY (fl.fluor_code || ':' || tg.tag_code || ':' || fu.tag_pos)
  ) AS fusions,
  COUNT(DISTINCT fu.id) AS n_fusions,
  p.created_at          AS created_at
FROM public.plasmids p
LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
LEFT JOIN public.fusions fu              ON fu.id          = jpf.fusion_id
LEFT JOIN public.fluors fl              ON fl.id          = fu.fluor_id
LEFT JOIN public.tags tg                ON tg.id          = fu.tag_id
GROUP BY p.id

UNION ALL

-- RNA constructs
SELECT
  r.id              AS construct_id,
  r.rna_base_code   AS code,
  'RNA'::text       AS construct_type,
  NULL::text        AS nickname,
  r.name            AS name,
  string_agg(DISTINCT fl.fluor_code, ',' ORDER BY fl.fluor_code) AS fluors,
  string_agg(DISTINCT tg.tag_code,   ',' ORDER BY tg.tag_code)   AS tag_codes,
  string_agg(
    DISTINCT (fl.fluor_code || ':' || tg.tag_code || ':' || fu.tag_pos),
    ',' ORDER BY (fl.fluor_code || ':' || tg.tag_code || ':' || fu.tag_pos)
  ) AS fusions,
  COUNT(DISTINCT fu.id) AS n_fusions,
  r.created_at          AS created_at
FROM public.rnas r
LEFT JOIN public.join_rna_fusions jrf ON jrf.rna_id = r.id
LEFT JOIN public.fusions fu          ON fu.id       = jrf.fusion_id
LEFT JOIN public.fluors fl          ON fl.id       = fu.fluor_id
LEFT JOIN public.tags tg            ON tg.id       = fu.tag_id
GROUP BY r.id

UNION ALL

-- CRISPR constructs
SELECT
  c.id             AS construct_id,
  c.crispr_code    AS code,
  'CRISPR'::text   AS construct_type,
  NULL::text       AS nickname,
  c.target_locus   AS name,
  NULL::text       AS fluors,
  NULL::text       AS tag_codes,
  NULL::text       AS fusions,
  0::bigint        AS n_fusions,
  c.created_at     AS created_at
FROM public.crisprs c;

COMMIT;
