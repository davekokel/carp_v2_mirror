begin;

-- 1) Roll up Tg(base)guN per fish (one row per fish_code)
create or replace view public.v_fish_genotype_rollup as
with a as (
  select
    f.fish_code,
    'Tg(' || fta.transgene_base_code || ')' || coalesce(ta.allele_name,'') as transgene_pretty
  from public.fish f
  left join public.fish_transgene_alleles fta on fta.fish_id = f.id
  left join public.transgene_alleles ta
         on ta.transgene_base_code = fta.transgene_base_code
        and ta.allele_number       = fta.allele_number
)
select
  fish_code,
  coalesce(string_agg(transgene_pretty, '; ' order by transgene_pretty), '') as genotype
from a
group by fish_code;

-- 2) Enriched clutch overview (only the fields you care about)
create or replace view public.v_clutches_overview as
with tx_counts as (
  select clutch_id, count(*)::int as n_treatments
  from public.clutch_plan_treatments
  group by clutch_id
),
mom_core as (
  select f.fish_code as mom_code, f.genetic_background as mom_background, f.date_birth as mom_birth
  from public.fish f
),
dad_core as (
  select f.fish_code as dad_code, f.genetic_background as dad_background, f.date_birth as dad_birth
  from public.fish f
),
mom_roll as (
  select fish_code as mom_code, genotype as mom_genotype_rollup
  from public.v_fish_genotype_rollup
),
dad_roll as (
  select fish_code as dad_code, genotype as dad_genotype_rollup
  from public.v_fish_genotype_rollup
)
select
  coalesce(p.clutch_code, p.id::text)  as clutch_code,
  coalesce(p.planned_name,'')          as name,
  coalesce(p.planned_nickname,'')      as nickname,

  p.mom_code                           as mom_code,
  coalesce(mo.mom_background,'')       as mom_background,
  coalesce(mr.mom_genotype_rollup,'')  as mom_genotype_rollup,
  0::int                               as mom_n_living_tanks,
  mo.mom_birth                         as mom_birth,

  p.dad_code                           as dad_code,
  coalesce(dcore.dad_background,'')    as dad_background,
  coalesce(dr.dad_genotype_rollup,'')  as dad_genotype_rollup,
  0::int                               as dad_n_living_tanks,
  dcore.dad_birth                      as dad_birth,

  coalesce(t.n_treatments,0)           as n_treatments,
  p.created_by                         as created_by,
  p.created_at                         as created_at
from public.clutch_plans p
left join tx_counts t   on t.clutch_id   = p.id
left join mom_core  mo  on mo.mom_code   = p.mom_code
left join dad_core  dcore on dcore.dad_code = p.dad_code
left join mom_roll  mr  on mr.mom_code   = p.mom_code
left join dad_roll  dr  on dr.dad_code   = p.dad_code
order by p.created_at desc;

commit;
