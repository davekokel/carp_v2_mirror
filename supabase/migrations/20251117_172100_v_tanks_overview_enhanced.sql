BEGIN;

DROP VIEW IF EXISTS public.v_tanks_overview;

CREATE VIEW public.v_tanks_overview AS
WITH resident AS (
  SELECT
    tm.tank_id,
    tm.fish_id,
    tm.started_at,
    tm.ended_at,
    tm.role,
    row_number() OVER (PARTITION BY tm.tank_id ORDER BY tm.started_at) AS rn
  FROM public.tank_memberships tm
  WHERE tm.role = 'resident'
    AND tm.ended_at IS NULL
)
SELECT
  t.id                                        AS id,
  t.tank_code,
  f.fish_code,
  t.status,
  COALESCE(
    CAST(date_part('day', now() - r.started_at) AS integer),
    0
  )                                           AS since_days,
  t.created_at                                AS created,

  -- tank details
  t.location,
  t.volume_l,
  t.notes                                     AS tank_notes,

  -- membership details
  r.fish_id,
  r.started_at,
  r.ended_at,
  r.role,

  -- fish/genotype/treatment summary from v_fish_overview_pretty
  vf.genotype_pretty,
  vf.genotype_alleles_pretty,
  vf.genotype_alleles_priority_pretty,
  vf.genotype_base_codes,
  vf.genotype_fluors,
  vf.treatment_base_codes,
  vf.treatment_rna_codes,
  vf.treatment_fluors,
  vf.all_base_codes,
  vf.all_fluors

FROM public.tanks t
LEFT JOIN resident r
  ON r.tank_id = t.id
  AND r.rn = 1
LEFT JOIN public.fish_instance f
  ON f.id = r.fish_id
LEFT JOIN public.v_fish_overview_pretty vf
  ON vf.fish_id = f.id;

COMMIT;

