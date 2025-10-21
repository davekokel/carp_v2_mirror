\set ON_ERROR_STOP on
begin;

create or replace view public.v_clutches_overview_final as
with base as (
  select
    cp.id::uuid                           as clutch_plan_id,
    coalesce(cp.clutch_code, cp.id::text) as clutch_code,
    cp.mom_code                           as mom_code,
    cp.dad_code                           as dad_code,
    coalesce(cp.planned_name,'')          as planned_name,
    coalesce(cp.planned_nickname,'')      as planned_nickname,
    cp.created_by                         as plan_created_by,
    cp.created_at                         as plan_created_at
  from public.clutch_plans cp
),
mom as (
  select
    f.fish_code,
    string_agg('Tg('||fta.transgene_base_code||')'||coalesce(ta.allele_name,''), '; ' 
               order by fta.transgene_base_code, coalesce(ta.allele_name,'')) as mom_genotype
  from public.fish f
  join public.fish_transgene_alleles fta on fta.fish_id = f.id
  join public.transgene_alleles ta
    on ta.transgene_base_code = fta.transgene_base_code
   and ta.allele_number       = fta.allele_number
  group by f.fish_code
),
dad as (
  select
    f.fish_code,
    string_agg('Tg('||fta.transgene_base_code||')'||coalesce(ta.allele_name,''), '; ' 
               order by fta.transgene_base_code, coalesce(ta.allele_name,'')) as dad_genotype
  from public.fish f
  join public.fish_transgene_alleles fta on fta.fish_id = f.id
  join public.transgene_alleles ta
    on ta.transgene_base_code = fta.transgene_base_code
   and ta.allele_number       = fta.allele_number
  group by f.fish_code
),
inst as (
  -- latest cross_instance rows
  select
    ci.id::uuid               as cross_instance_id,
    ci.cross_id::uuid         as cross_id,
    ci.created_by             as created_by_instance,
    ci.created_at             as created_at_instance,
    ci.cross_date             as cross_date,
    ci.tank_pair_id::uuid     as tank_pair_id,
    coalesce(ci.cross_name,'') as cross_name_pretty
  from public.cross_instances ci
),
ci_by_plan as (
  -- plan → latest cross_instance via clutches link
  select
    c.planned_cross_id::uuid  as clutch_plan_id,
    i.*
  from public.clutches c
  join inst i on i.cross_instance_id = c.cross_instance_id
),
rows as (
  select
    b.clutch_plan_id,
    b.clutch_code,
    b.mom_code,
    coalesce(m.mom_genotype,'') as mom_genotype,
    b.dad_code,
    coalesce(d.dad_genotype,'') as dad_genotype,

    coalesce(i.cross_name_pretty,
             case when b.mom_code is not null and b.dad_code is not null
                  then b.mom_code||' x '||b.dad_code else '' end) as cross_name_pretty,

    coalesce(b.planned_nickname,'')  as clutch_name,
    ''::text                         as clutch_genotype_pretty,
    ''::text                         as clutch_genotype_canonical,
    ''::text as mom_strain,
    ''::text as dad_strain,
    ''::text as clutch_strain_pretty,
    0::int  as treatments_count,
    ''::text as treatments_pretty,

    coalesce(
      (select c.date_birth from public.clutches c
        where c.planned_cross_id = b.clutch_plan_id
        order by c.created_at desc nulls last limit 1),
      (i.cross_date + interval '1 day')::date
    ) as clutch_birthday,

    coalesce(i.created_by_instance, b.plan_created_by)   as created_by_instance,
    coalesce(i.created_at_instance, b.plan_created_at)   as created_at_instance

  from base b
  left join ci_by_plan i on i.clutch_plan_id = b.clutch_plan_id
  left join mom m on m.fish_code = b.mom_code
  left join dad d on d.fish_code = b.dad_code
)

select *
from rows
order by created_at_instance desc nulls last, clutch_birthday desc nulls last;

commit;
