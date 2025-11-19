BEGIN;

DROP VIEW IF EXISTS public.v_tanks_overview;

CREATE VIEW public.v_tanks_overview AS
SELECT
  t.id                                       AS id,
  t.tank_code                                AS tank_code,
  f.fish_code                                AS fish_code,
  t.status                                   AS status,
  COALESCE(date_part('day', now() - t.created_at)::integer, 0) AS since_days,
  t.created_at                               AS created,
  t.location                                 AS location,
  t.volume_l                                 AS volume_l,
  t.notes                                    AS tank_notes,
  t.fish_id                                  AS fish_id,
  t.created_at                               AS started_at,
  NULL::timestamp with time zone             AS ended_at,
  'resident'::text                           AS role,
  vf.genotype_pretty                         AS genotype_pretty,
  vf.genotype_alleles_pretty                 AS genotype_alleles_pretty,
  vf.genotype_alleles_priority_pretty        AS genotype_alleles_priority_pretty,
  vf.genotype_base_codes                     AS genotype_base_codes,
  vf.genotype_fluors                         AS genotype_fluors,
  vf.treatment_base_codes                    AS treatment_base_codes,
  vf.treatment_rna_codes                     AS treatment_rna_codes,
  vf.treatment_fluors                        AS treatment_fluors,
  vf.all_base_codes                          AS all_base_codes,
  vf.all_fluors                              AS all_fluors
FROM public.tanks t
LEFT JOIN public.fish_instance f
       ON f.id = t.fish_id
LEFT JOIN public.v_fish_overview_pretty vf
       ON vf.fish_id = f.id;

COMMIT;
