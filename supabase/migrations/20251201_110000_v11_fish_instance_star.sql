BEGIN;

DROP VIEW IF EXISTS public.v11_fish_instance_star;

CREATE VIEW public.v11_fish_instance_star AS
SELECT
  vie.fish_instance_id,
  vie.fish_code,
  vie.birthday,
  vie.fish_created_at,

  fl.id                AS line_id,
  vie.line_code,
  vie.line_nickname    AS line_nickname,
  vie.genetic_background,
  vie.line_building_stage,

  fg.id                AS fish_group_id,
  fg.group_code,
  fg.genotype_key,
  vfg.basecode_genotype,

  vie.genotype_pretty,
  vie.fluor_codes,
  vie.tag_codes,

  t.id::text           AS tank_id,
  t.tank_code,
  t.status             AS tank_status,
  t.location,
  t.created_at         AS tank_created_at

FROM public.v10_fish_instances_overview_enriched AS vie
JOIN public.fish_lines fl
  ON fl.id = vie.line_id
JOIN public.fish_groups fg
  ON fg.id = fl.fish_group_id
LEFT JOIN public.v10_fish_groups_overview vfg
  ON vfg.fish_group_id = fg.id::text
LEFT JOIN public.tanks t
  ON t.fish_instance_id = vie.fish_instance_id;

COMMIT;
