BEGIN;

DROP VIEW IF EXISTS public.v11_fish_instance_star;

CREATE VIEW public.v11_fish_instance_star AS
WITH fi AS (
    SELECT
      fi.fish_instance_id,
      fi.fish_code,
      fi.line_id,
      fi.birthday,
      fi.fish_notes,
      fi.fish_created_at,
      fi.line_code,
      fi.line_nickname,
      fi.genetic_background,
      fi.line_building_stage,
      fi.line_created_at,
      fi.genotype_pretty,
      fi.fluor_codes,
      fi.tag_codes,
      fi.organelle_fluors,
      fi.fusion_pretty,
      fi.n_fusions
    FROM public.v10_fish_instances_overview_enriched fi
),
fi_raw AS (
    SELECT
      f.id,
      f.line_instance_code
    FROM public.fish_instances_v10 f
),
line_geno AS (
    SELECT
      fl.id AS line_id,
      string_agg(DISTINCT c.base_code, ', ' ORDER BY c.base_code) AS genotype_base_codes,
      string_agg(
        DISTINCT ta.allele_name,
        ', ' ORDER BY c.base_code, ta.allele_number
      ) AS genotype_allele_codes
    FROM public.fish_lines fl
    JOIN public.join_line_alleles jla
      ON jla.line_id = fl.id
    JOIN public.constructs c
      ON c.id = jla.construct_id
    JOIN public.transgene_alleles ta
      ON ta.transgene_base_code = c.base_code
     AND ta.allele_number       = jla.allele_number
    GROUP BY fl.id
),
tank_join AS (
    SELECT
      t.id          AS tank_id,
      t.tank_code,
      t.status      AS tank_status,
      t.created_at  AS tank_created_at,
      t.fish_instance_id
    FROM public.tanks t
)
SELECT
  f.fish_instance_id,
  f.fish_code,
  f.line_id,
  r.line_instance_code,
  f.birthday,
  f.fish_notes,
  f.fish_created_at,
  f.line_code,
  f.line_nickname,
  f.genetic_background,
  f.line_building_stage,
  f.line_created_at,
  fl.fish_group_id,
  fg.group_code,
  fl.group_instance_code,
  f.genotype_pretty,
  f.fluor_codes,
  f.tag_codes,
  f.organelle_fluors,
  tj.tank_id,
  tj.tank_code,
  tj.tank_status,
  tj.tank_created_at,
  lg.genotype_base_codes,
  lg.genotype_allele_codes,
  NULL::text AS treat_codes,
  f.genotype_pretty AS treatments_and_transgenes,
  f.fusion_pretty   AS all_fluor_tag_rollup,
  f.organelle_fluors AS all_organelle_fluor_rollup
FROM fi f
LEFT JOIN fi_raw r
  ON r.id = f.fish_instance_id
LEFT JOIN public.fish_lines fl
  ON fl.id = f.line_id
LEFT JOIN public.fish_groups fg
  ON fg.id = fl.fish_group_id
LEFT JOIN line_geno lg
  ON lg.line_id = f.line_id
LEFT JOIN tank_join tj
  ON tj.fish_instance_id = f.fish_instance_id
ORDER BY f.birthday, f.fish_code;

COMMIT;
