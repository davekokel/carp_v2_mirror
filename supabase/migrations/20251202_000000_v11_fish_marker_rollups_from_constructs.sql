BEGIN;

CREATE OR REPLACE VIEW public.v11_fish_marker_rollups AS
WITH base AS (
  SELECT
    fi.id AS fish_instance_id,
    g.genotype_basecodes
  FROM public.fish_instances_v10 fi
  LEFT JOIN public.genotypes_v11 g
    ON g.id = fi.genotype_v11_id
),
expanded AS (
  SELECT
    b.fish_instance_id,
    split_part(trim(code), ':', 1) AS construct_base_code
  FROM base b,
       LATERAL regexp_split_to_table(COALESCE(b.genotype_basecodes, ''), '\\s*\\|\\|\\s*') AS code
  WHERE trim(code) <> ''
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
  COALESCE(count(DISTINCT j.construct_code), 0) AS n_constructs,
  COALESCE(count(DISTINCT j.fusion_pretty), 0) AS n_fluors,
  COALESCE(
    string_agg(DISTINCT NULLIF(j.fusion_pretty, ''), '||')
      FILTER (WHERE j.fusion_pretty IS NOT NULL),
    ''
  ) AS fluor_tag_rollup,
  COALESCE(
    string_agg(DISTINCT NULLIF(j.organelle_fluors, ''), '||')
      FILTER (WHERE j.organelle_fluors IS NOT NULL),
    ''
  ) AS organelle_fluor_rollup
FROM public.fish_instances_v10 fi
LEFT JOIN joined j
  ON j.fish_instance_id = fi.id
GROUP BY fi.id
ORDER BY fi.id;

COMMIT;
