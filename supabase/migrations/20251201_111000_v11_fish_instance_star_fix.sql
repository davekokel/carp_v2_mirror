BEGIN;

DROP VIEW IF EXISTS public.v11_fish_instance_star;

CREATE VIEW public.v11_fish_instance_star AS
SELECT
  fi.id                    AS fish_instance_id,
  fi.fish_code,            -- FSH-xxxx
  fi.line_instance_code,   -- LINE-xxxx-NNN
  fi.birthday,
  fi.created_at            AS fish_created_at,

  fl.id                    AS line_id,
  fl.line_code,
  fl.nickname              AS line_nickname,
  fl.genetic_background,
  fl.line_building_stage,

  fg.id                    AS fish_group_id,
  fg.group_code,
  fg.genotype_key,
  vfg.basecode_genotype,

  vie.genotype_pretty,
  vie.fluor_codes,
  vie.tag_codes,
  vie.n_fusions,
  vie.fusion_pretty,
  vie.organelle_fluors,

  t.id::text               AS tank_id,
  t.tank_code,
  t.status                 AS tank_status,
  t.location,
  t.created_at             AS tank_created_at

FROM public.fish_instances_v10 fi
JOIN public.fish_lines fl
  ON fl.id = fi.line_id
JOIN public.fish_groups fg
  ON fg.id = fl.fish_group_id
LEFT JOIN public.v10_fish_groups_overview vfg
  ON vfg.fish_group_id = fg.id::text
LEFT JOIN public.v10_fish_instances_overview_enriched vie
  ON vie.fish_instance_id = fi.id
LEFT JOIN public.tanks t
  ON t.fish_instance_id = fi.id;

COMMIT;
