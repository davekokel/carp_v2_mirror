BEGIN;

-- v_tanks_overview: one row per tank, enriched with resident fish + genotype/treatment summary
DROP VIEW IF EXISTS public.v_tanks_overview;
CREATE OR REPLACE VIEW public.v_tanks_overview AS
WITH resident AS (
  SELECT
    tm.tank_id,
    tm.fish_id,
    tm.started_at,
    row_number() OVER (PARTITION BY tm.tank_id ORDER BY tm.started_at) AS rn
  FROM public.tank_memberships tm
  WHERE tm.role = 'resident'
    AND tm.ended_at IS NULL
)
SELECT
  t.id                                      AS tank_id,
  t.tank_code,
  t.location,
  t.status,
  t.volume_l,
  t.notes                                   AS tank_notes,
  t.created_at                              AS tank_created_at,

  r.fish_id,
  f.fish_code,
  f.birthday,
  f.genetic_background,
  f.line_building_stage,
  f.nickname,
  f.notes                                   AS fish_notes,

  vf.genotype_pretty,
  vf.genotype_alleles_pretty,
  vf.genotype_alleles_priority_pretty,
  vf.genotype_base_codes,
  vf.genotype_fluors,
  vf.treatment_base_codes,
  vf.treatment_rna_codes,
  vf.treatment_fluors,
  vf.all_base_codes,
  vf.all_fluors,

  COALESCE(
    CAST(date_part('day', now() - r.started_at) AS integer),
    0
  )                                         AS since_days
FROM public.tanks t
LEFT JOIN resident r
  ON r.tank_id = t.id
  AND r.rn = 1
LEFT JOIN public.fish_instance f
  ON f.id = r.fish_id
LEFT JOIN public.v_fish_overview_pretty vf
  ON vf.fish_id = f.id;

COMMIT;
