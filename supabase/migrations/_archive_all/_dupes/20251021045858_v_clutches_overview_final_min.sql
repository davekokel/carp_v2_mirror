\set ON_ERROR_STOP on
begin;

-- Canonical final view used by the UI (minimal but stable shape).
-- Derives core fields from clutch_plans + cross_instances + clutches.
-- Any enrichments you don't track yet are blank/zero (so UI doesn't crash).

create or replace view public.v_clutches_overview_final as
with base as (
  select
    cp.id::uuid                           as clutch_plan_id,
    coalesce(cp.clutch_code, cp.id::text) as clutch_code,
    cp.mom_code                           as mom_code,
    cp.dad_code                           as dad_code,
    cp.planned_name                       as planned_name,
    cp.planned_nickname                   as planned_nickname,
    cp.created_by                         as plan_created_by,
    cp.created_at                         as plan_created_at
  from public.clutch_plans cp
),
inst as (
  -- latest cross_instance per plan (if table/columns exist)
  select
    ci.id::uuid               as cross_instance_id,
    ci.cross_id::uuid         as cross_id,
    ci.created_by             as created_by_instance,
    ci.created_at             as created_at_instance,
    ci.cross_date             as cross_date,
    ci.tank_pair_id::uuid     as tank_pair_id,
    -- best-effort pretty cross name if present, else mom x dad from plan
    coalesce(ci.cross_name, '') as cross_name_pretty
  from public.cross_instances ci
),
ci_by_plan as (
  -- Map plan -> latest cross_instance if a link exists
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
    -- parents
    b.mom_code,
    b.dad_code,

    -- genotypes (fill later if you add a genotype view; safe blanks for now)
    ''::text as mom_genotype,
    ''::text as dad_genotype,

    -- pretty names (fallbacks)
    coalesce(i.cross_name_pretty,
             case when b.mom_code is not null and b.dad_code is not null
                  then b.mom_code||' x '||b.dad_code else '' end) as cross_name_pretty,

    -- clutch name / genotype summaries
    coalesce(b.planned_nickname, '')          as clutch_name,
    ''::text                                  as clutch_genotype_pretty,
    ''::text                                  as clutch_genotype_canonical,

    -- strains (optional; fill via future join if you track strains)
    ''::text as mom_strain,
    ''::text as dad_strain,
    ''::text as clutch_strain_pretty,

    -- treatments rollup (safe defaults)
    0::int  as treatments_count,
    ''::text as treatments_pretty,

    -- birthday: prefer clutches.date_birth if present; else cross_date + 1 day if available
    coalesce(
      (select c.date_birth from public.clutches c
        where c.planned_cross_id = b.clutch_plan_id
        order by c.created_at desc nulls last limit 1),
      (i.cross_date + interval '1 day')::date
    ) as clutch_birthday,

    -- provenance (prefer instance)
    coalesce(i.created_by_instance, b.plan_created_by)   as created_by_instance,
    coalesce(i.created_at_instance, b.plan_created_at)   as created_at_instance

  from base b
  left join ci_by_plan i on i.clutch_plan_id = b.clutch_plan_id
)

select *
from rows
order by created_at_instance desc nulls last, clutch_birthday desc nulls last;

commit;
