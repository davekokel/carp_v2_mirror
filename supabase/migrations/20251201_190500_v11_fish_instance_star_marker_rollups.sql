BEGIN;

CREATE OR REPLACE VIEW public.v11_fish_instance_star AS
WITH fi_base AS (
    SELECT
      fi.id              AS fish_instance_id,
      fi.fish_code       AS fish_code,
      fi.line_id         AS line_id,
      fi.line_instance_code,
      fi.birthday,
      fi.notes           AS fish_notes,
      fi.created_at      AS fish_created_at,

      fl.line_code,
      fl.nickname        AS line_nickname,
      fl.genetic_background,
      fl.line_building_stage,
      fl.created_at      AS line_created_at,
      fl.fish_group_id,
      fg.group_code,
      fl.group_instance_code,

      lar.allele_label_rollup     AS genotype_pretty,
      lar.allele_canonical_rollup AS genotype_basecode_code,

      t.id               AS tank_id,
      t.tank_code,
      t.status           AS tank_status,
      t.created_at       AS tank_created_at

    FROM public.fish_instances_v10 fi
    JOIN public.fish_lines fl
      ON fl.id = fi.line_id
    LEFT JOIN public.fish_groups fg
      ON fg.id = fl.fish_group_id
    LEFT JOIN public.v11_line_allele_rollups lar
      ON lar.line_id = fl.id
    LEFT JOIN public.tanks t
      ON t.fish_instance_id = fi.id
),

line_markers AS (
    SELECT
      lf.line_id,
      lf.fluor_codes,
      lf.tag_codes
    FROM public.v10_line_fluors lf
),

group_markers AS (
    SELECT
      fg.fish_group_id::uuid AS fish_group_id,
      fg.fluor_tag            AS all_fluor_tag_rollup,
      fg.organelle_fluor      AS all_organelle_fluor_rollup
    FROM public.v10_fish_groups_overview fg
)

SELECT
  b.fish_instance_id,
  b.fish_code,
  b.line_id,
  b.line_instance_code,
  b.birthday,
  b.fish_notes,
  b.fish_created_at,
  b.line_code,
  b.line_nickname,
  b.genetic_background,
  b.line_building_stage,
  b.line_created_at,
  b.fish_group_id,
  b.group_code,
  b.group_instance_code,

  -- pretty genotype from allele labels
  b.genotype_pretty,

  -- raw fluor/tag codes by line
  lm.fluor_codes,
  lm.tag_codes,

  -- organelle-fluor rollup from fish-group view
  gm.all_organelle_fluor_rollup AS organelle_fluors,

  -- tank info
  b.tank_id,
  b.tank_code,
  b.tank_status,
  b.tank_created_at,

  -- we don't have per-fish treatment yet
  NULL::text AS treatment_code,

  -- canonical genotype codes
  b.genotype_basecode_code      AS genotype_basecode_code,
  NULL::text                    AS genotype_transgene_allele_code,

  -- treatments_and_transgenes: basecode genotype for now
  b.genotype_basecode_code      AS treatments_and_transgenes,

  -- rollups from fish-group view
  gm.all_fluor_tag_rollup,
  gm.all_organelle_fluor_rollup

FROM fi_base b
LEFT JOIN line_markers  lm ON lm.line_id         = b.line_id
LEFT JOIN group_markers gm ON gm.fish_group_id   = b.fish_group_id
ORDER BY b.fish_code;

COMMIT;
