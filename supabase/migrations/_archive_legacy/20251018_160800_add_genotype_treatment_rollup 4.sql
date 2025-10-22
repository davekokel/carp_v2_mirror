drop view if exists public.v_clutches_overview_final;

create view public.v_clutches_overview_final as
with mom as (
    select
        v.fish_code,
        string_agg(
            distinct (v.transgene_base_code || '-' || v.allele_name), ' ; '
            order by (v.transgene_base_code || '-' || v.allele_name)
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
            distinct (v.transgene_base_code || '-' || v.allele_name), ' ; '
            order by (v.transgene_base_code || '-' || v.allele_name)
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
        coalesce(cl.clutch_instance_code, cl.clutch_code, cp.clutch_code, left(cl.id::text, 8)) as clutch_code
    from public.clutches AS cl
    inner join public.cross_instances AS ci on cl.cross_instance_id = ci.id
    inner join public.crosses AS x on ci.cross_id = x.id
    left join public.clutch_plans AS cp on cl.planned_cross_id = cp.id
),

joined as (
    select
        c.*,
        gu.canonical_union as clutch_genotype_canonical,
        gu.pretty_union as clutch_genotype_pretty,
        concat_ws(' × ', nullif(m.pretty, ''), nullif(d.pretty, '')) as cross_name_pretty,
        concat_ws(' × ', nullif(m.canonical, ''), nullif(d.canonical, '')) as cross_name,
        nullif(m.pretty, '') as mom_genotype_raw,
        nullif(d.pretty, '') as dad_genotype_raw,
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
    j.clutch_plan_id,
    j.clutch_id,
    j.clutch_code,
    j.cross_code,
    j.cross_name_pretty,
    j.cross_name,
    j.clutch_genotype_canonical,
    j.clutch_genotype_pretty,
    j.mom_strain,
    j.dad_strain,
    s.treatments_count,
    s.treatments_pretty,
    s.treatments_json,
    j.clutch_birthday,
    j.date_planned,
    j.created_by_plan,
    j.created_at_plan,
    j.created_by_instance,
    -- NEW rollup: treatments_pretty > clutch_genotype_pretty (or just genotype if no treatments)
    j.created_at_instance,
    coalesce(j.planned_name, j.clutch_genotype_pretty) as clutch_name,
    coalesce(j.planned_nickname, coalesce(j.planned_name, j.clutch_genotype_pretty)) as clutch_nickname,
    coalesce(j.mom_genotype_raw, j.mother_code) as mom_genotype,
    coalesce(j.dad_genotype_raw, j.father_code) as dad_genotype,
    public.gen_clutch_strain(j.mother_code, j.father_code) as clutch_strain,
    concat_ws(' × ', nullif(j.mom_strain, ''), nullif(j.dad_strain, '')) as clutch_strain_pretty,
    case
        when
            coalesce(s.treatments_pretty, '') <> ''
            then s.treatments_pretty || ' > ' || coalesce(j.clutch_genotype_pretty, '')
        else coalesce(j.clutch_genotype_pretty, '')
    end as genotype_treatment_rollup
from joined AS j
left join public.v_clutch_treatments_summary AS s on j.clutch_id = s.clutch_id;
