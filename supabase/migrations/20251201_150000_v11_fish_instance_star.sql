BEGIN;

-- Drop dependent views in correct order
DROP VIEW IF EXISTS public.v11_clutch_star;
DROP VIEW IF EXISTS public.v11_imaging_roi_star;
DROP VIEW IF EXISTS public.v11_fish_instance_star;

-- Recreate v11_fish_instance_star using v10 enrichment
CREATE VIEW public.v11_fish_instance_star AS
SELECT
  fi.id::uuid                  AS fish_instance_id,
  fi.fish_code,
  fi.line_id::uuid             AS line_id,
  fi.line_instance_code,
  fi.birthday,
  fi.notes                     AS fish_notes,
  fi.created_at                AS fish_created_at,
  fl.line_code,
  fl.nickname                  AS line_nickname,
  fl.genetic_background,
  fl.line_building_stage,
  fl.created_at                AS line_created_at,
  fl.fish_group_id             AS fish_group_id,
  fg.group_code,
  fl.group_instance_code,
  fov.genotype_pretty,
  fov.fluor_codes,
  fov.tag_codes,
  fov.organelle_fluors,
  t.id::uuid                   AS tank_id,
  t.tank_code,
  t.status                     AS tank_status,
  t.created_at                 AS tank_created_at
FROM public.fish_instances_v10 fi
JOIN public.fish_lines fl
  ON fl.id = fi.line_id
LEFT JOIN public.fish_groups fg
  ON fg.id = fl.fish_group_id
LEFT JOIN public.v10_fish_instances_overview_enriched fov
  ON fov.fish_instance_id = fi.id
LEFT JOIN public.tanks t
  ON t.fish_instance_id = fi.id;

COMMIT;
