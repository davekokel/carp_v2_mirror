BEGIN;

DROP VIEW IF EXISTS public.v11_fish_marker_rollups_nice;
DROP VIEW IF EXISTS public.v11_fish_marker_rollups;
DROP VIEW IF EXISTS public.v_constructs_overview;

CREATE VIEW public.v_constructs_overview AS
WITH base AS (
  SELECT
    c.id,
    c.construct_code,
    c.construct_kind,
    c.construct_name,
    c.resistance,
    COALESCE(c.plasmid_notes, c.description, '') AS description,
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
    COALESCE(
      string_agg(
        DISTINCT CASE
          WHEN fl.fluor_code IS NULL THEN NULL
          ELSE fl.fluor_code
               || COALESCE('-' || t.tag_code, '')
               || '(' || COALESCE(f.tag_pos, '') || ')'
        END,
        '||'
      ),
      ''
    ) AS fusion_pretty,
    COALESCE(
      string_agg(
        DISTINCT CASE
          WHEN fl.fluor_code IS NULL THEN NULL
          ELSE COALESCE(t.localization, '')
               || CASE
                    WHEN COALESCE(t.localization, '') = '' THEN ''
                    ELSE '-'
                  END
               || fl.fluor_code
        END,
        '||'
      ),
      ''
    ) AS organelle_fluors
  FROM public.construct_fusions cf
  JOIN public.fusions f
    ON f.id = cf.fusion_id
  LEFT JOIN public.fluors fl
    ON fl.id = f.fluor_id
  LEFT JOIN public.tags t
    ON t.id = f.tag_id
  GROUP BY cf.construct_id
)
SELECT
  b.construct_code,
  b.construct_kind,
  b.construct_name,
  b.resistance,
  b.description,
  COALESCE(fj.n_fusions, 0)::bigint AS n_fusions,
  COALESCE(fj.fusion_pretty, '')    AS fusion_pretty,
  COALESCE(fj.organelle_fluors, '') AS organelle_fluors,
  b.injection_use_plasmid,
  b.injection_use_rna,
  b.injection_use_crispr,
  b.created_at
FROM base b
LEFT JOIN fusion_join fj
  ON fj.construct_id = b.id;

COMMENT ON VIEW public.v_constructs_overview IS
'Construct overview with fusion_pretty as fluor-tag(pos), organelle_fluors as localization-fluor, and injection_use_* flags passed through from constructs.';

CREATE VIEW public.v11_fish_marker_rollups AS
WITH base AS (
  SELECT
    fi1.id AS fish_instance_id,
    g.genotype_basecodes
  FROM public.fish_instances_v10 fi1
  LEFT JOIN public.genotypes_v11 g
    ON g.id = fi1.genotype_v11_id
),
expanded AS (
  SELECT
    b.fish_instance_id,
    split_part(trim(both from code.code), ':'::text, 1) AS construct_base_code
  FROM base b,
  LATERAL regexp_split_to_table(
    COALESCE(b.genotype_basecodes, ''::text),
    '\\s*\\|\\|\\s*'::text
  ) code(code)
  WHERE trim(both from code.code) <> ''::text
),
joined AS (
  SELECT
    e.fish_instance_id,
    c.construct_code,
    v.fusion_pretty,
    v.organelle_fluors
  FROM expanded e
  JOIN public.constructs c
    ON c.base_code = e.construct_base_code
    OR c.construct_code = e.construct_base_code
  JOIN public.v_constructs_overview v
    ON v.construct_code = c.construct_code
)
SELECT
  fi.id AS fish_instance_id,
  COALESCE(count(DISTINCT j.construct_code), 0::bigint) AS n_constructs,
  COALESCE(count(DISTINCT j.fusion_pretty), 0::bigint)  AS n_fluors,
  COALESCE(
    string_agg(
      DISTINCT NULLIF(j.fusion_pretty, ''),
      '||'
    ) FILTER (WHERE j.fusion_pretty IS NOT NULL),
    ''
  ) AS fluor_tag_rollup,
  COALESCE(
    string_agg(
      DISTINCT NULLIF(j.organelle_fluors, ''),
      '||'
    ) FILTER (WHERE j.organelle_fluors IS NOT NULL),
    ''
  ) AS organelle_fluor_rollup
FROM public.fish_instances_v10 fi
LEFT JOIN joined j
  ON j.fish_instance_id = fi.id
GROUP BY fi.id
ORDER BY fi.id;

COMMENT ON VIEW public.v11_fish_marker_rollups IS
'Per-fish_instance_v10 marker rollups derived from v_constructs_overview (n_constructs, n_fluors, fluor_tag_rollup, organelle_fluor_rollup).';

CREATE VIEW public.v11_fish_marker_rollups_nice AS
SELECT
  m.fish_instance_id,
  m.n_constructs,
  m.n_fluors,
  m.fluor_tag_rollup,
  m.organelle_fluor_rollup
FROM public.v11_fish_marker_rollups m;

COMMENT ON VIEW public.v11_fish_marker_rollups_nice IS
'Simplified passthrough of v11_fish_marker_rollups; pretty-splitting happens in the UI.';

COMMIT;
