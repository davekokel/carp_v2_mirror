BEGIN;

CREATE OR REPLACE VIEW public.v_treated_clutches_overview AS
WITH base AS (
  SELECT
    ci.id                   AS clutch_instance_id,
    ci.clutch_instance_code AS clutch_code,
    ''::text                AS clutch_genotype,
    cr.id                   AS cross_id,
    COALESCE(cr.cross_run_code, cr.id::text) AS cross_code,
    cr.tank_pair_id
  FROM public.clutch_instances ci
  LEFT JOIN public.crosses cr ON cr.id = ci.cross_instance_id
),
tx_raw AS (
  SELECT
    tc.treated_clutch_code,
    tc.created_at          AS group_created_at,
    b.clutch_instance_id,
    b.clutch_code,
    b.clutch_genotype,
    b.cross_code,
    b.tank_pair_id,
    NULLIF(t.treat_code,'') AS code,
    NULLIF(COALESCE(t.treat_text, t.treat_code), ''::text) AS name
  FROM public.treated_clutches tc
  JOIN base b ON b.clutch_instance_id = tc.clutch_instance_id
  LEFT JOIN public.join_clutch_treatments jct ON jct.treated_clutch_id = tc.id
  LEFT JOIN public.treatments t              ON t.id = jct.treatment_id
),
tx_distinct AS (
  SELECT DISTINCT
    tx_raw.treated_clutch_code,
    tx_raw.group_created_at,
    tx_raw.clutch_instance_id,
    tx_raw.clutch_code,
    tx_raw.clutch_genotype,
    tx_raw.cross_code,
    tx_raw.tank_pair_id,
    tx_raw.code,
    tx_raw.name
  FROM tx_raw
),
grp AS (
  SELECT
    td.treated_clutch_code,
    min(td.group_created_at)              AS group_created_at,
    min(td.clutch_instance_id::text)      AS clutch_instance_id,
    min(td.clutch_code)                   AS clutch_code,
    min(td.clutch_genotype)               AS clutch_genotype,
    min(td.cross_code)                    AS cross_code,
    min(td.tank_pair_id::text)            AS tank_pair_id_text,
    count(td.code)                        AS treatments_count_group,
    COALESCE(string_agg(td.code, '+' ORDER BY td.code), '') AS treatments_codes_group,
    COALESCE(string_agg(td.name, ' + ' ORDER BY td.name), '') AS treatments_names_group
  FROM tx_distinct td
  GROUP BY td.treated_clutch_code
),
tm AS (
  SELECT
    v_tanks_overview.id::uuid AS tank_id,
    v_tanks_overview.tank_code,
    v_tanks_overview.fish_code
  FROM public.v_tanks_overview
),
fish_rollup AS (
  SELECT
    v_fish_overview.fish_code_raw AS fish_code,
    max(v_fish_overview.genotype_pretty) AS genotype,
    max(v_fish_overview.fusions)         AS fusions
  FROM public.v_fish_overview
  GROUP BY v_fish_overview.fish_code_raw
)
SELECT
  g.treated_clutch_code,
  g.group_created_at,
  g.clutch_instance_id,
  g.clutch_code,
  g.clutch_genotype,
  g.cross_code,
  g.treatments_count_group,
  g.treatments_codes_group,
  g.treatments_names_group,
  tm_m.fish_code AS mom_fish_code,
  tm_d.fish_code AS dad_fish_code,
  gm.genotype    AS mom_genotype,
  gd.genotype    AS dad_genotype,
  gm.fusions     AS mom_fusions,
  gd.fusions     AS dad_fusions
FROM grp g
LEFT JOIN public.tank_pairs tp ON tp.id = g.tank_pair_id_text::uuid
LEFT JOIN tm tm_m ON tm_m.tank_id = tp.mother_tank_id
LEFT JOIN tm tm_d ON tm_d.tank_id = tp.father_tank_id
LEFT JOIN fish_rollup gm ON gm.fish_code = tm_m.fish_code
LEFT JOIN fish_rollup gd ON gd.fish_code = tm_d.fish_code
ORDER BY g.clutch_code, g.group_created_at;

COMMIT;
