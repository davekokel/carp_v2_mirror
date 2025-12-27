CREATE OR REPLACE VIEW public.v11_genotype_label_star AS
WITH g AS (
  SELECT
    gv.id AS genotype_v11_id,
    gv.genotype_code,
    gv.genotype_pretty,
    gv.genotype_basecodes
  FROM public.genotypes_v11 gv
),
tokens_raw AS (
  SELECT
    g_1.genotype_v11_id,
    lower(btrim(tok.tok)) AS tok
  FROM g g_1
  CROSS JOIN LATERAL regexp_split_to_table(COALESCE(g_1.genotype_basecodes, ''), '[,;|[:space:]]+') tok(tok)
  WHERE NULLIF(btrim(tok.tok), '') IS NOT NULL
),
tokens_norm AS (
  SELECT
    tr.genotype_v11_id,
    CASE
      WHEN regexp_match(
        regexp_replace(regexp_replace(tr.tok, '[:].*$', ''), '[^a-z0-9\-]+', '', 'g'),
        '^([a-z]+)-?0*([0-9]+)$'
      ) IS NOT NULL
      THEN format(
        '%s-%s',
        (regexp_match(regexp_replace(regexp_replace(tr.tok, '[:].*$', ''), '[^a-z0-9\-]+', '', 'g'), '^([a-z]+)-?0*([0-9]+)$'))[1],
        ((regexp_match(regexp_replace(regexp_replace(tr.tok, '[:].*$', ''), '[^a-z0-9\-]+', '', 'g'), '^([a-z]+)-?0*([0-9]+)$'))[2])::integer
      )
      ELSE regexp_replace(regexp_replace(tr.tok, '[:].*$', ''), '[^a-z0-9\-]+', '', 'g')
    END AS base_code_norm
  FROM tokens_raw tr
),
tokens_sort AS (
  SELECT
    tn.genotype_v11_id,
    tn.base_code_norm,
    CASE WHEN tn.base_code_norm ~ '^[a-z]+-[0-9]+$' THEN 0 ELSE 1 END AS sort_kind,
    COALESCE((regexp_match(tn.base_code_norm, '^([a-z]+)-([0-9]+)$'))[1], tn.base_code_norm) AS sort_prefix,
    COALESCE(NULLIF((regexp_match(tn.base_code_norm, '^([a-z]+)-([0-9]+)$'))[2], '')::integer, 0) AS sort_num
  FROM tokens_norm tn
  WHERE NULLIF(btrim(tn.base_code_norm), '') IS NOT NULL
),
tokens_sort_distinct AS (
  SELECT DISTINCT
    ts.genotype_v11_id,
    ts.base_code_norm,
    ts.sort_kind,
    ts.sort_prefix,
    ts.sort_num
  FROM tokens_sort ts
),
g_constructs AS (
  SELECT DISTINCT
    ts.genotype_v11_id,
    ts.base_code_norm,
    ts.sort_kind,
    ts.sort_prefix,
    ts.sort_num,
    c.id AS construct_id
  FROM tokens_sort_distinct ts
  JOIN public.constructs c
    ON lower(c.base_code) = ts.base_code_norm
),
fusion_bits AS (
  SELECT
    gc.genotype_v11_id,
    gc.base_code_norm,
    gc.sort_kind,
    gc.sort_prefix,
    gc.sort_num,
    COALESCE(fl.nickname, fl.display_name, fl.code) AS fluor_label,
    COALESCE(tg.nickname, tg.display_name, tg.code) AS tag_label,
    tg.localization,
    f.tag_pos,
    CASE
      WHEN tg.id IS NULL THEN COALESCE(fl.nickname, fl.display_name, fl.code)
      ELSE format('%s-%s(%s)', COALESCE(fl.nickname, fl.display_name, fl.code), COALESCE(tg.nickname, tg.display_name, tg.code), f.tag_pos)
    END AS fluor_tag_label,
    CASE
      WHEN tg.localization IS NULL OR tg.localization = '' THEN COALESCE(fl.nickname, fl.display_name, fl.code)
      ELSE format('%s-%s', COALESCE(fl.nickname, fl.display_name, fl.code), tg.localization)
    END AS organelle_fluor_label
  FROM g_constructs gc
  JOIN public.construct_fusions cf ON cf.construct_id = gc.construct_id
  JOIN public.fusions f ON f.id = cf.fusion_id
  JOIN public.fluors fl ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg ON tg.id = f.tag_id
),
fluor_tag_rollup AS (
  SELECT
    fb.genotype_v11_id,
    string_agg(DISTINCT fb.fluor_tag_label, '; ' ORDER BY fb.fluor_tag_label) AS all_fluor_tag_rollup
  FROM fusion_bits fb
  GROUP BY fb.genotype_v11_id
),
organelle_fluor_rollup AS (
  SELECT
    fb.genotype_v11_id,
    string_agg(DISTINCT fb.organelle_fluor_label, '; ' ORDER BY fb.organelle_fluor_label) AS all_organelle_fluor_rollup
  FROM fusion_bits fb
  GROUP BY fb.genotype_v11_id
),
fluor_tag_parts_group AS (
  SELECT DISTINCT
    fb.genotype_v11_id,
    fb.fluor_tag_label,
    fb.base_code_norm,
    fb.sort_kind,
    fb.sort_prefix,
    fb.sort_num
  FROM fusion_bits fb
),
fluor_tag_parts_rollup AS (
  SELECT
    g2.genotype_v11_id,
    string_agg(format('%s(%s)', g2.fluor_tag_label, g2.basecodes), '; ' ORDER BY g2.fluor_tag_label) AS fluor_tag_parts
  FROM (
    SELECT
      ft_1.genotype_v11_id,
      ft_1.fluor_tag_label,
      string_agg(ft_1.base_code_norm, ',' ORDER BY ft_1.sort_kind, ft_1.sort_prefix, ft_1.sort_num, ft_1.base_code_norm) AS basecodes
    FROM fluor_tag_parts_group ft_1
    GROUP BY ft_1.genotype_v11_id, ft_1.fluor_tag_label
  ) g2
  GROUP BY g2.genotype_v11_id
),
organelle_parts_group AS (
  SELECT DISTINCT
    fb.genotype_v11_id,
    fb.organelle_fluor_label,
    fb.base_code_norm,
    fb.sort_kind,
    fb.sort_prefix,
    fb.sort_num
  FROM fusion_bits fb
),
organelle_parts_rollup AS (
  SELECT
    g2.genotype_v11_id,
    string_agg(format('%s(%s)', g2.organelle_fluor_label, g2.basecodes), '; ' ORDER BY g2.organelle_fluor_label) AS fluor_organelle_parts
  FROM (
    SELECT
      og.genotype_v11_id,
      og.organelle_fluor_label,
      string_agg(og.base_code_norm, ',' ORDER BY og.sort_kind, og.sort_prefix, og.sort_num, og.base_code_norm) AS basecodes
    FROM organelle_parts_group og
    GROUP BY og.genotype_v11_id, og.organelle_fluor_label
  ) g2
  GROUP BY g2.genotype_v11_id
),
no_tg AS (
  SELECT g.genotype_v11_id
  FROM g
  WHERE g.genotype_code = 'G-NO-TG'
     OR lower(btrim(COALESCE(g.genotype_basecodes, ''))) IN ('no_tg','no-tg','no_transgene','no-transgene','notg')
),
tg_entries AS (
  SELECT DISTINCT ON (gc.genotype_v11_id, gc.base_code_norm)
    gc.genotype_v11_id,
    gc.base_code_norm,
    gc.sort_kind,
    gc.sort_prefix,
    gc.sort_num,
    CASE
      WHEN NULLIF(btrim(COALESCE(ta.allele_name, ta.allele_nickname, ta.nickname, ta.display_name)), '') IS NULL THEN NULL
      WHEN ta.allele_number IS NULL THEN NULLIF(btrim(COALESCE(ta.allele_name, ta.allele_nickname, ta.nickname, ta.display_name)), '')
      ELSE format(
        '%s-%s',
        NULLIF(btrim(COALESCE(ta.allele_name, ta.allele_nickname, ta.nickname, ta.display_name)), ''),
        ta.allele_number
      )
    END AS allele_label,
    ta.allele_number
  FROM g_constructs gc
  LEFT JOIN public.transgene_alleles ta
    ON lower(ta.transgene_base_code) = gc.base_code_norm
  WHERE gc.genotype_v11_id NOT IN (SELECT genotype_v11_id FROM no_tg)
  ORDER BY
    gc.genotype_v11_id,
    gc.base_code_norm,
    ta.allele_number NULLS LAST
),
tg_labels AS (
  SELECT
    te.genotype_v11_id,
    te.base_code_norm,
    te.sort_kind,
    te.sort_prefix,
    te.sort_num,
    CASE
      WHEN te.allele_label IS NULL THEN format('tg(%s)', te.base_code_norm)
      ELSE format('tg(%s)%s', te.base_code_norm, te.allele_label)
    END AS tg_label
  FROM tg_entries te
),
tg_labels_distinct AS (
  SELECT DISTINCT
    tl.genotype_v11_id,
    tl.base_code_norm,
    tl.sort_kind,
    tl.sort_prefix,
    tl.sort_num,
    tl.tg_label
  FROM tg_labels tl
),
tg_label_canon AS (
  SELECT
    g.genotype_v11_id,
    CASE
      WHEN g.genotype_v11_id IN (SELECT genotype_v11_id FROM no_tg)
        THEN 'no transgene'
      ELSE (
        SELECT NULLIF(string_agg(x.tg_label, '; '), '')
        FROM (
          SELECT tld.tg_label
          FROM tg_labels_distinct tld
          WHERE tld.genotype_v11_id = g.genotype_v11_id
          ORDER BY
            tld.sort_kind,
            tld.sort_prefix,
            tld.sort_num,
            tld.base_code_norm,
            tld.tg_label
        ) x
      )
    END AS tg_style_canon
  FROM g
)
SELECT
  g.genotype_v11_id,
  g.genotype_code,
  g.genotype_pretty,
  g.genotype_basecodes,
  NULLIF(btrim(ft.all_fluor_tag_rollup), '') AS fluor_tag_style,
  NULLIF(btrim(ofr.all_organelle_fluor_rollup), '') AS fluor_organelle_style,
  tlc.tg_style_canon,
  NULLIF(btrim(ftp.fluor_tag_parts), '') AS fluor_tag_parts,
  NULLIF(btrim(ofp.fluor_organelle_parts), '') AS fluor_organelle_parts
FROM g
LEFT JOIN fluor_tag_rollup ft ON ft.genotype_v11_id = g.genotype_v11_id
LEFT JOIN organelle_fluor_rollup ofr ON ofr.genotype_v11_id = g.genotype_v11_id
LEFT JOIN tg_label_canon tlc ON tlc.genotype_v11_id = g.genotype_v11_id
LEFT JOIN fluor_tag_parts_rollup ftp ON ftp.genotype_v11_id = g.genotype_v11_id
LEFT JOIN organelle_parts_rollup ofp ON ofp.genotype_v11_id = g.genotype_v11_id;
