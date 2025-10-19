-- 1) default clutch_name and nickname trigger
create or replace function public.trg_clutches_default_names()
returns trigger
language plpgsql
as $$
begin
  if new.clutch_name is null or btrim(new.clutch_name) = '' then
    new.clutch_name := new.clutch_genotype_pretty;
  end if;
  if new.clutch_nickname is null or btrim(new.clutch_nickname) = '' then
    new.clutch_nickname := new.clutch_name;
  end if;
  return new;
end$$;

drop trigger if exists trg_clutches_default_names on public.clutches;
create trigger trg_clutches_default_names
before insert or update on public.clutches
for each row execute function public.trg_clutches_default_names();

-- 2) view: v_clutches_overview_final
create or replace view public.v_clutches_overview_final as
with mom as (
    select
        v.fish_code,
        string_agg(
            distinct v.transgene_base_code || '-' || v.allele_name, ' ; ' order by v.transgene_base_code, v.allele_name
        ) as canonical,
        string_agg(
            distinct coalesce(v.allele_pretty_name, v.transgene_pretty_name), ' ; ' order by coalesce(v.allele_pretty_name, v.transgene_pretty_name)
        ) as pretty
    from public.v_fish_overview_all AS v
    group by v.fish_code
),

dad as (
    select
        v.fish_code,
        string_agg(
            distinct v.transgene_base_code || '-' || v.allele_name, ' ; ' order by v.transgene_base_code, v.allele_name
        ) as canonical,
        string_agg(
            distinct coalesce(v.allele_pretty_name, v.transgene_pretty_name), ' ; ' order by coalesce(v.allele_pretty_name, v.transgene_pretty_name)
        ) as pretty
    from public.v_fish_overview_all AS v
    group by v.fish_code
),

stats as (
    select
        cp2.id as clutch_plan_id,
        count(distinct c.id) as n_crosses,
        count(distinct cl2.id) as n_instances,
        count(distinct ct.id) as n_containers
    from public.clutch_plans AS cp2
    left join public.crosses AS c on cp2.planned_cross_id = c.planned_cross_id
    left join public.cross_instances AS ci2 on c.id = ci2.cross_id
    left join public.clutches AS cl2 on ci2.id = cl2.cross_instance_id
    left join public.container_clutches AS ct on cl2.id = ct.clutch_id
    group by cp2.id
)

select
    cp.id::uuid as clutch_plan_id,
    cl.id::uuid as clutch_id,
    x.cross_code,
    gen.canonical_union as clutch_genotype_canonical,
    -- cross names
    gen.pretty_union as clutch_genotype_pretty,
    mom.pretty as mom_genotype,
    -- clutch names
    dad.pretty as dad_genotype,
    cl.date_birth as clutch_birthday,
    -- genotypes
    cp.cross_date as date_planned,
    cp.created_by as created_by_plan,
    cp.created_at as created_at_plan,
    cl.created_by as created_by_instance,
    cl.created_at as created_at_instance,
    coalesce(stats.n_instances, 0)::int as n_instances,
    coalesce(stats.n_crosses, 0)::int as n_crosses,
    coalesce(stats.n_containers, 0)::int as n_containers,
    cl.note,
    coalesce(cl.clutch_code, cp.clutch_code) as clutch_code,
    (mom.pretty || ' × ' || dad.pretty) as cross_name_pretty,
    (mom.canonical || ' × ' || dad.canonical) as cross_name,
    coalesce(cl.clutch_name, gen.pretty_union) as clutch_name,
    coalesce(cl.clutch_nickname, coalesce(cl.clutch_name, gen.pretty_union)) as clutch_nickname
from public.clutches AS cl
inner join public.cross_instances AS ci on cl.cross_instance_id = ci.id
inner join public.crosses AS x on ci.cross_id = x.id
left join public.clutch_plans AS cp on cl.planned_cross_id = cp.id
-- mom/dad genotype rollups
left join mom AS on x.mother_code = mom.fish_code
left join dad AS on x.father_code = dad.fish_code
-- clutch genotype (union of parents)
left join lateral (
    select
        string_agg(distinct t.canonical, ' ; ' order by t.canonical) as canonical_union,
        string_agg(distinct t.pretty, ' ; ' order by t.pretty) as pretty_union
    from (
        select
            unnest(string_to_array(mom.canonical, ' ; ')) as canonical,
            unnest(string_to_array(mom.pretty, ' ; ')) as pretty
        union all
        select
            unnest(string_to_array(dad.canonical, ' ; ')),
            unnest(string_to_array(dad.pretty, ' ; '))
    ) as t
) as gen on true
-- stats
left join stats AS on cp.id = stats.clutch_plan_id;
