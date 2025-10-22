\set ON_ERROR_STOP on
begin;
create or replace view public.v_clutches_overview_final as
select
  cp.id::uuid                           as clutch_plan_id,
  coalesce(cp.clutch_code, cp.id::text) as clutch_code,
  cp.mom_code, cp.dad_code,
  coalesce(cp.planned_name,'')          as planned_name,
  coalesce(cp.planned_nickname,'')      as planned_nickname,
  ''::text as mom_genotype, ''::text as dad_genotype,
  case when cp.mom_code is not null and cp.dad_code is not null
       then cp.mom_code||' x '||cp.dad_code else '' end as cross_name_pretty,
  coalesce(cp.planned_nickname,'')  as clutch_name,
  ''::text as clutch_genotype_pretty, ''::text as clutch_genotype_canonical,
  ''::text as mom_strain, ''::text as dad_strain, ''::text as clutch_strain_pretty,
  0::int  as treatments_count, ''::text as treatments_pretty,
  null::date as clutch_birthday,
  cp.created_by as created_by_instance, cp.created_at as created_at_instance
from public.clutch_plans cp
order by created_at_instance desc nulls last;
commit;
