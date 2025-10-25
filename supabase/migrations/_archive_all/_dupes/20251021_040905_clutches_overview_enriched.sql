begin;

-- v_clutches_overview: enriched view for planning/overview
-- Columns:
--   clutch_code, name, nickname,
--   mom_code, mom_background, mom_genotype_rollup, mom_n_living_tanks, mom_birth,
--   dad_code, dad_background, dad_genotype_rollup, dad_n_living_tanks, dad_birth,
--   n_treatments, created_by, created_at
--
-- Sources:
--   clutch_plans                               → clutch identity, mom/dad, planned name/nickname, creator, timestamps
--   clutch_plan_treatments (count per clutch)  → n_treatments
--   fish                                       → mom/dad genetic background + birth date (reliable core table)
--   v_fish_genotype_rollup (if present)        → mom/dad genotype rollup (left join; coalesce to '')
--
-- NOTE: We join to fish (not v_fish_overview_all) for background/birth to avoid fragile columns.
--       If a rollup view is absent for an env, fields coalesce to '' and the view still materializes.

create or replace view public.v_clutches_overview as
with tx_counts as (
  select clutch_id, count(*)::int as n_treatments
  from public.clutch_plan_treatments
  group by clutch_id
),
mom_core as (
  select
    f.fish_code                              as mom_code,
    f.genetic_background                     as mom_background,
    f.date_birth                             as mom_birth
  from public.fish f
),
dad_core as (
  select
    f.fish_code                              as dad_code,
    f.genetic_background                     as dad_background,
    f.date_birth                             as dad_birth
  from public.fish f
),
mom_roll as (
  select
    r.fish_code                              as mom_code,
    r.genotype                               as mom_genotype_rollup
  from public.v_fish_genotype_rollup r
),
dad_roll as (
  select
    r.fish_code                              as dad_code,
    r.genotype                               as dad_genotype_rollup
  from public.v_fish_genotype_rollup r
)
select
  coalesce(p.clutch_code, p.id::text)        as clutch_code,
  coalesce(p.planned_name,'')                as name,
  coalesce(p.planned_nickname,'')            as nickname,

  p.mom_code                                 as mom_code,
  coalesce(mo.mom_background,'')             as mom_background,
  coalesce(mr.mom_genotype_rollup,'')        as mom_genotype_rollup,
  0::int                                     as mom_n_living_tanks,  -- can be wired later if you track this
  mo.mom_birth                               as mom_birth,

  p.dad_code                                 as dad_code,
  coalesce(do.dad_background,'')             as dad_background,
  coalesce(dr.dad_genotype_rollup,'')        as dad_genotype_rollup,
  0::int                                     as dad_n_living_tanks,  -- can be wired later if you track this
  do.dad_birth                               as dad_birth,

  coalesce(t.n_treatments,0)                 as n_treatments,
  p.created_by                               as created_by,
  p.created_at                               as created_at
from public.clutch_plans p
left join tx_counts t on t.clutch_id = p.id
left join mom_core  mo on mo.mom_code = p.mom_code
left join dad_core  do on do.dad_code = p.dad_code
left join mom_roll  mr on mr.mom_code = p.mom_code
left join dad_roll  dr on dr.dad_code = p.dad_code
order by p.created_at desc;

commit;
