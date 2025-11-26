BEGIN;

-- Drop dependent views so we can change column layout safely
DROP VIEW IF EXISTS public.v10_fish_instances_overview;
DROP VIEW IF EXISTS public.v10_fish_lines_overview;

-- v10_fish_lines_overview:
--   One row per fish line, with fluor/tag rollups.
--   genotype_pretty is a placeholder for now (NULL).
CREATE VIEW public.v10_fish_lines_overview AS
SELECT
  fl.id                  AS line_id,
  fl.line_code,
  fl.nickname,
  fl.genetic_background,
  fl.line_building_stage,
  fl.created_at,
  NULL::text             AS genotype_pretty,
  vlf.fluor_codes,
  vlf.tag_codes
FROM public.fish_lines fl
LEFT JOIN public.v10_line_fluors vlf
  ON vlf.line_id = fl.id;

-- v10_fish_instances_overview:
--   One row per fish_instance_v10, joined to its line and line-level rollups.
CREATE VIEW public.v10_fish_instances_overview AS
SELECT
  fi.id          AS fish_instance_id,
  fi.fish_code,
  fi.line_id,
  fi.birthday,
  fi.notes       AS fish_notes,
  fi.created_at  AS fish_created_at,
  fl.line_code,
  fl.nickname    AS line_nickname,
  fl.genetic_background,
  fl.line_building_stage,
  fl.created_at  AS line_created_at,
  v10.genotype_pretty,
  v10.fluor_codes,
  v10.tag_codes
FROM public.fish_instances_v10 fi
JOIN public.fish_lines fl
  ON fl.id = fi.line_id
LEFT JOIN public.v10_fish_lines_overview v10
  ON v10.line_id = fl.id;

COMMIT;
