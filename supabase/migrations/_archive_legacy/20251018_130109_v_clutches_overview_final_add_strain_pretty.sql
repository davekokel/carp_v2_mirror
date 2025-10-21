-- Extend v_clutches_overview_final with mom_strain, dad_strain, and directional clutch_strain_pretty

create or replace view public.v_clutches_overview_final as
with mom as (
    select
        v.fish_code,
        string_agg(
            distinct (v.transgene_base_code || '-' || v.allele_name), ' ; ' order by (v.transgene_base_code || '-' || v.allele_name)
        ) as canonical,
        string_agg(
            distinct coalesce(
                v.transgene_pretty_name, v.transgene_pretty_nickname, v.transgene_base_code || v.allele_name
            ), ' ; '
            order by
                coalesce(v.transgene_pretty_name, v.transgene_pretty_nickname, v.transgene_base_code || v.allele_name)
        ) as pretty,
        max(nullif(btrim(v.genetic_background), '')) as mom_strain
    from public.v_fish_overview_all AS v
    group by v.fish_code
),

dad as (
    select
        v.fish_code,
        string_agg(
            distinct (v.transgene_base_code || '-' || v.allele_name), ' ; ' order by (v.transgene_base_code || '-' || v.allele_name)
        ) as canonical,
        string_agg(
            distinct coalesce(
                v.transgene_pretty_name, v.transgene_pretty_nickname, v.transgene_base_code || v.allele_name
            ), ' ; '
            order by
                coalesce(v.transgene_pretty_name, v.transgene_pretty_nickname, v.transgene_base_code || v.allele_name)
        ) as pretty,
        max(nullif(btrim(v.genetic_background), '')) as dad_strain
    from public.v_fish_overview_all AS v
    group by v.fish_code
),

core as (
    select
        cp.id::uuid as clutch_plan_id,
        cl.id::uuid as clutch_id,
        x.cross_code,
        cl.date_birth as clutch_birthday,
        cp.cross_date as date_planned,
        cp.created_by as created_by_plan,
        cp.created_at as created_at_plan,
        cl.created_by as created_by_instance,
        cl.created_at as created_at_instance,
        x.mother_code,
        x.father_code,
        cp.planned_name,
        cp.planned_nickname,
        cp.planned_strain,
        cl.clutch_strain,
        coalesce(cl.clutch_instance_code, cl.clutch_code, cp.clutch_code, left(cl.id::text, 8)) as clutch_code
    from public.clutches AS cl
    inner join public.cross_instances AS ci on cl.cross_instance_id = ci.id
    inner join public.crosses AS x on ci.cross_id = x.id
    left join public.clutch_plans AS cp on cl.planned_cross_id = cp.id
),

joined as (
    select
        c.*,
        m.pretty as mom_genotype,
        d.pretty as dad_genotype,
        gu.canonical_union as clutch_genotype_canonical,
        gu.pretty_union as clutch_genotype_pretty,
        concat_ws(' × ', nullif(m.pretty, ''), nullif(d.pretty, '')) as cross_name_pretty,
        concat_ws(' × ', nullif(m.canonical, ''), nullif(d.canonical, '')) as cross_name,
        coalesce(m.mom_strain, '(unknown)') as mom_strain,
        coalesce(d.dad_strain, '(unknown)') as dad_strain
    from core AS c
    left join mom AS m on c.mother_code = m.fish_code
    left join dad AS d on c.father_code = d.fish_code
    left join lateral (
        with toks as (
            select
                unnest(string_to_array(nullif(m.canonical, ''), ' ; ')) as can,
                unnest(string_to_array(nullif(m.pretty, ''), ' ; ')) as pre
            union all
            select
                unnest(string_to_array(nullif(d.canonical, ''), ' ; ')),
                unnest(string_to_array(nullif(d.pretty, ''), ' ; '))
        )

        select
            string_agg(distinct can, ' ; ' order by can) as canonical_union,
            string_agg(distinct pre, ' ; ' order by pre) as pretty_union
        from toks  where coalesce(can, '') <> '' and coalesce(pre, '') <> ''
    ) as gu on true
)

select
    clutch_plan_id,
    clutch_id,
    clutch_code,
    cross_code,
    cross_name_pretty,
    cross_name,
    clutch_genotype_canonical,
    clutch_genotype_pretty,
    mom_genotype,
    dad_genotype,
    mom_strain,
    dad_strain,
    clutch_birthday,
    date_planned,
    created_by_plan,
    created_at_plan,
    created_by_instance,
    created_at_instance,
    0::int as n_instances,
    0::int as n_crosses,
    0::int as n_containers, ''::text as note,
    coalesce(planned_name, clutch_genotype_pretty) as clutch_name,
    coalesce(planned_nickname, coalesce(planned_name, clutch_genotype_pretty)) as clutch_nickname,
    coalesce(clutch_strain, planned_strain, public.gen_clutch_strain(mother_code, father_code)) as clutch_strain,
    concat_ws(' × ', nullif(mom_strain, ''), nullif(dad_strain, '')) as clutch_strain_pretty
from joined;
