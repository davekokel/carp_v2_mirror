begin;

-- Tank-centric clutches overview:
--   clutch_instances → cross_instances → tank_pairs → v_tanks → v_fish
-- Columns include parent backgrounds/rollups, #living tanks, treatments count, and provenance.
create or replace view public.v_clutches as
with tp as (
  select
    tp.id                                  as tank_pair_id,
    vtm.fish_code                          as mom_fish_code,
    vtf.fish_code                          as dad_fish_code,
    vtm.tank_code                          as mom_tank_code,
    vtf.tank_code                          as dad_tank_code
  from public.tank_pairs tp
  left join public.v_tanks vtm on vtm.tank_id = tp.mother_tank_id
  left join public.v_tanks vtf on vtf.tank_id = tp.father_tank_id
),
parents as (
  select
    t.tank_pair_id,
    t.mom_fish_code,
    t.dad_fish_code,
    t.mom_tank_code,
    t.dad_tank_code,
    vf_m.genetic_background                as mom_background,
    vf_m.genotype                          as mom_genotype_rollup,
    vf_m.date_birth                        as mom_birth,
    vf_d.genetic_background                as dad_background,
    vf_d.genotype                          as dad_genotype_rollup,
    vf_d.date_birth                        as dad_birth
  from tp t
  left join public.v_fish vf_m on vf_m.fish_code = t.mom_fish_code
  left join public.v_fish vf_d on vf_d.fish_code = t.dad_fish_code
),
living as (
  -- # living tanks per fish (active + new_tank)
  select
    v.fish_code,
    count(*) filter (where v.status in ('active','new_tank'))::int as n_living_tanks
  from public.v_tanks v
  where coalesce(v.fish_code,'') <> ''
  group by v.fish_code
),
ci_tx as (
  -- treatments count per clutch_instance (if the table exists in your DB)
  select
    cit.clutch_instance_id::uuid as clutch_instance_id,
    count(*)::int                 as n_treatments
  from public.clutch_instance_treatments cit
  group by cit.clutch_instance_id
)
select
  -- identities
  ci.id::uuid                                        as clutch_instance_id,
  ci.cross_instance_id::uuid                         as cross_instance_id,
  coalesce(ci.clutch_instance_code, ci.id::text)     as clutch_code,

  -- planned placeholders (legacy concept fields; kept for shape)
  null::text                                         as name,          -- Planned name
  null::text                                         as nickname,      -- Planned nickname

  -- parents (codes/tanks)
  p.mom_fish_code                                    as mom_code,
  p.dad_fish_code                                    as dad_code,
  p.mom_tank_code                                    as mom_tank_code,
  p.dad_tank_code                                    as dad_tank_code,

  -- parents (background/rollup/birth)
  p.mom_background,
  p.mom_genotype_rollup,
  p.mom_birth,
  p.dad_background,
  p.dad_genotype_rollup,
  p.dad_birth,

  -- parents (# living tanks)
  coalesce(lm.n_living_tanks, 0)                     as mom_n_living_tanks,
  coalesce(ld.n_living_tanks, 0)                     as dad_n_living_tanks,

  -- treatments
  coalesce(tx.n_treatments, 0)                       as n_treatments,

  -- provenance + dates
  ci.date_birth                                      as clutch_birthday,
  x.cross_date                                       as cross_date,
  coalesce(ci.created_by, x.created_by)              as created_by,
  coalesce(ci.created_at, x.created_at)              as created_at,

  -- run code
  coalesce(nullif(x.cross_run_code,''), x.id::text)  as cross_run_code

from public.clutch_instances ci
left join public.cross_instances x on x.id = ci.cross_instance_id
left join parents p                 on p.tank_pair_id = x.tank_pair_id
left join living  lm                on lm.fish_code   = p.mom_fish_code
left join living  ld                on ld.fish_code   = p.dad_fish_code
left join ci_tx   tx                on tx.clutch_instance_id = ci.id;

comment on view public.v_clutches is
'Tank-centric clutch overview: identities, planned placeholders, parent backgrounds/rollups, #living tanks, treatments count, and provenance.';

commit;
