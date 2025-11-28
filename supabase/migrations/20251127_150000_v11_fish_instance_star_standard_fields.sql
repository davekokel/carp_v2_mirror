BEGIN;

CREATE OR REPLACE VIEW public.v11_fish_instance_star AS
WITH enriched AS (
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
raw_fi AS (
    SELECT
      f.id,
      f.line_instance_code
    FROM public.fish_instances_v10 f
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
  e.fish_instance_id,
  e.fish_code,
  e.line_id,
  r.line_instance_code,
  e.birthday,
  e.fish_notes,
  e.fish_created_at,
  e.line_code,
  e.line_nickname,
  e.genetic_background,
  e.line_building_stage,
  e.line_created_at,
  fl.fish_group_id,
  fg.group_code,
  fl.group_instance_code,
  e.genotype_pretty,
  e.fluor_codes,
  e.tag_codes,
  e.organelle_fluors,
  tj.tank_id,
  tj.tank_code,
  tj.tank_status,
  tj.tank_created_at,
  NULL::text         AS treatment_code,
  fg.group_code      AS genotype_basecode_code,
  fl.line_code       AS genotype_transgene_allele_code,
  e.genotype_pretty  AS treatments_and_transgenes,
  e.fusion_pretty    AS all_fluor_tag_rollup,
  e.organelle_fluors AS all_organelle_fluor_rollup
FROM enriched e
LEFT JOIN raw_fi r
  ON r.id = e.fish_instance_id
LEFT JOIN public.fish_lines fl
  ON fl.id = e.line_id
LEFT JOIN public.fish_groups fg
  ON fg.id = fl.fish_group_id
LEFT JOIN tank_join tj
  ON tj.fish_instance_id = e.fish_instance_id
ORDER BY e.birthday, e.fish_code;

COMMIT;
