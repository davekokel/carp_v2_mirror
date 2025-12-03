BEGIN;

CREATE OR REPLACE VIEW public.v11_fish_marker_rollups AS
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
       LATERAL regexp_split_to_table(COALESCE(b.genotype_basecodes, ''::text), '\\s*\\|\\|\\s*') AS code(code)
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
    regexp_replace(
      regexp_replace(
        string_agg(
          DISTINCT NULLIF(j.fusion_pretty, ''::text),
          '||'
        ) FILTER (WHERE j.fusion_pretty IS NOT NULL),
        '::\(\)', '',
        'g'
      ),
      '[:]{1,2}',
      '-',
      'g'
    ),
    ''
  ) AS fluor_tag_rollup,
  COALESCE(
    regexp_replace(
      regexp_replace(
        string_agg(
          DISTINCT NULLIF(j.organelle_fluors, ''::text),
          '||'
        ) FILTER (WHERE j.organelle_fluors IS NOT NULL),
        '::\(\)', '',
        'g'
      ),
      '[:]{1,2}',
      '-',
      'g'
    ),
    ''
  ) AS organelle_fluor_rollup
FROM public.fish_instances_v10 fi
LEFT JOIN joined j
  ON j.fish_instance_id = fi.id
GROUP BY fi.id
ORDER BY fi.id;

COMMENT ON VIEW public.v11_fish_marker_rollups IS
'Per-fish_instance marker rollups derived from v_constructs_overview, with cleaned and hyphenated forms:
 fluor_tag_rollup: fluor-tag(pos) with ":" and "::" normalized to "-";
 organelle_fluor_rollup: organelle-fluor with ":" and "::" normalized to "-".';

COMMIT;
