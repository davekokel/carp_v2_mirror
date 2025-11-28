BEGIN;

DROP VIEW IF EXISTS public.v11_tank_star;

CREATE VIEW public.v11_tank_star AS
WITH fis AS (
  SELECT
    fish_instance_id,
    fish_code,
    line_id,
    birthday,
    line_building_stage,
    all_organelle_fluor_rollup
  FROM public.v11_fish_instance_star
)
SELECT
  t.id::text                              AS tank_id,
  t.tank_code                             AS tank_code_raw,
  CASE
    WHEN t.tank_code LIKE 'TANK-FSH-%'
      THEN 'TANK-' || substring(t.tank_code FROM '^TANK-FSH-(.*)$')
    ELSE t.tank_code
  END                                     AS tank_code,
  COALESCE(fi.fish_code, fis.fish_code)   AS fish_code,
  COALESCE(la.allele_canonical_rollup,'') AS allele_canonical,
  COALESCE(fis.all_organelle_fluor_rollup,'') AS organelle_fluor,
  COALESCE(fl.line_building_stage, fis.line_building_stage,'') AS line_building_stage,
  fis.birthday                            AS dob
FROM public.tanks t
LEFT JOIN public.fish_instances_v10 fi ON fi.id = t.fish_instance_id
LEFT JOIN fis ON fis.fish_instance_id = t.fish_instance_id
LEFT JOIN public.fish_lines fl ON fl.id = fis.line_id
LEFT JOIN public.v11_line_allele_rollups la ON la.line_id = fis.line_id;

COMMIT;
