BEGIN;

CREATE OR REPLACE VIEW public.v11_fish_instance_star AS
WITH fi AS (
  SELECT
    i.id                  AS fish_instance_id,
    i.fish_code           AS fish_code,
    i.line_id             AS line_id,
    i.line_instance_code  AS line_instance_code,
    i.birthday            AS birthday,
    i.notes               AS fish_notes,
    i.created_at          AS fish_created_at
  FROM public.fish_instances_v10 i
),
lines AS (
  SELECT
    fl.id                 AS line_id,
    fl.line_code          AS line_code,
    fl.nickname           AS line_nickname,
    fl.genetic_background AS genetic_background,
    fl.line_building_stage AS line_building_stage,
    fl.created_at         AS line_created_at,
    fl.fish_group_id      AS fish_group_id,
    fl.group_instance_code AS group_instance_code
  FROM public.fish_lines fl
),
groups AS (
  SELECT
    fg.id         AS fish_group_id,
    fg.group_code AS group_code
  FROM public.fish_groups fg
),
tank_info AS (
  SELECT
    t.fish_instance_id,
    t.id          AS tank_id,
    t.tank_code   AS tank_code,
    t.status      AS tank_status,
    t.created_at  AS tank_created_at
  FROM public.tanks t
),
alleles AS (
  SELECT
    la.line_id,
    la.allele_canonical_rollup AS genotype_basecode_code,
    la.allele_label_rollup     AS genotype_transgene_allele_code,
    -- for now, use allele_label_rollup as "pretty" genotype
    la.allele_label_rollup     AS genotype_pretty
  FROM public.v11_line_allele_rollups la
)
SELECT
  fi.fish_instance_id,
  fi.fish_code,
  fi.line_id,
  fi.line_instance_code,
  fi.birthday,
  fi.fish_notes,
  fi.fish_created_at,
  lines.line_code,
  lines.line_nickname,
  lines.genetic_background,
  lines.line_building_stage,
  lines.line_created_at,
  lines.fish_group_id,
  groups.group_code,
  lines.group_instance_code,
  alleles.genotype_pretty,
  NULL::text AS fluor_codes,
  NULL::text AS tag_codes,
  NULL::text AS organelle_fluors,
  tank_info.tank_id,
  tank_info.tank_code,
  tank_info.tank_status,
  tank_info.tank_created_at,
  NULL::text AS treatment_code,
  alleles.genotype_basecode_code,
  alleles.genotype_transgene_allele_code,
  NULL::text AS treatments_and_transgenes,
  NULL::text AS all_fluor_tag_rollup,
  NULL::text AS all_organelle_fluor_rollup
FROM fi
LEFT JOIN lines   ON lines.line_id = fi.line_id
LEFT JOIN groups  ON groups.fish_group_id = lines.fish_group_id
LEFT JOIN alleles ON alleles.line_id = fi.line_id
LEFT JOIN tank_info ON tank_info.fish_instance_id = fi.fish_instance_id;

COMMIT;
