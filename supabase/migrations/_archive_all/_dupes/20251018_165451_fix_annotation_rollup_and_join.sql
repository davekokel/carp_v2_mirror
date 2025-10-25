-- 0) Drop the final view first so we can recreate dependencies in order
do $$
begin
  if exists (
    select 1 from information_schema.views  where table_schema='public' and table_name='v_clutches_overview_final'
  ) then
    execute 'drop view public.v_clutches_overview_final';
  end if;
end$$;

-- 1) Latest-annotation summary per clutch with compact annotation_rollup
create or replace view public.v_clutch_annotations_summary as
with link as (
    select
        cl.id as clutch_id,
        ci.id as selection_id,
        ci.cross_instance_id,
        ci.created_at,
        ci.annotated_at,
        ci.annotated_by,
        coalesce(ci.red_selected, false) as red_selected,
        coalesce(ci.green_selected, false) as green_selected,
        nullif(btrim(ci.red_intensity), '') as red_intensity,
        nullif(btrim(ci.green_intensity), '') as green_intensity,
        nullif(btrim(ci.notes), '') as notes,
        nullif(btrim(ci.label), '') as ci_label
    from public.clutches as cl
    inner join public.cross_instances as x on cl.cross_instance_id = x.id
    inner join public.clutch_instances as ci on x.id = ci.cross_instance_id
),

latest as (
    select distinct on (clutch_id)
        clutch_id,
        selection_id,
        cross_instance_id,
        created_at,
        annotated_at,
        annotated_by,
        red_selected,
        green_selected,
        red_intensity,
        green_intensity,
        notes,
        label
    from link
    order by
        clutch_id asc,
        coalesce(annotated_at, created_at) desc,
        created_at desc,
        selection_id desc
),

annotators as (
    -- Pre-dedupe then ordered string_agg (no DISTINCT needed in the agg)
    select
        s.clutch_id,
        string_agg(s.annotated_by_txt, ', ' order by s.annotated_by_txt) as annotators
    from (
        select distinct
            clutch_id,
            coalesce(annotated_by, '') as annotated_by_txt
        from link
        where annotated_by is not null and btrim(annotated_by) <> ''
    ) as s
    group by s.clutch_id
),

agg as (
    select
        l.clutch_id,
        count(*)::int as annotations_count,
        sum(case when l.red_selected then 1 else 0 end)::int as red_selected_count,
        sum(case when l.green_selected then 1 else 0 end)::int as green_selected_count,
        max(coalesce(l.annotated_at, l.created_at)) as last_annotated_at
    from link as l
    group by l.clutch_id
),

rollup as (
    -- Build one-line rollup from the AS latest row
    select
        lt.clutch_id,
        case
            when lt.red_selected
                then 'red:' || coalesce(lt.red_intensity, 'selected')
            else ''
        end as red_part,
        case
            when lt.green_selected
                then 'green:' || coalesce(lt.green_intensity, 'selected')
            else ''
        end as green_part,
        case
            when lt.notes is not null
                then 'note:' || left(lt.notes, 120)
            else ''
        end as note_part
    from latest as lt
),

rollup_fmt as (
    select
        r.clutch_id,
        (
            case
                when (nullif(r.red_part, '') is not null or nullif(r.green_part, '') is not null)
                    then
                        array_to_string(array[nullif(r.red_part, ''), nullif(r.green_part, '')], ' ; ')
                else ''
            end
            ||
            case
                when nullif(r.note_part, '') is not null
                    then case
                        when (nullif(r.red_part, '') is not null or nullif(r.green_part, '') is not null)
                            then ', ' || r.note_part
                        else r.note_part
                    end
                else ''
            end
        ) as annotation_rollup
    from rollup as r
)

select
    a.clutch_id,
    coalesce(a.annotations_count, 0)::int as annotations_count,
    a.last_annotated_at,
    coalesce(a.red_selected_count, 0)::int as red_selected_count,
    coalesce(a.green_selected_count, 0)::int as green_selected_count,
    coalesce(n.annotators, '') as annotators,
    coalesce(rf.annotation_rollup, '') as annotation_rollup
from agg as a
left join annotators as n on a.clutch_id = n.clutch_id
left join rollup_fmt as rf on a.clutch_id = rf.clutch_id;

-- 2) Recreate the final view to include annotation_rollup (and keep existing fields)
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
    from public.v_fish_overview_all as v
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
    from public.v_fish_overview_all as v
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
    from public.clutches as cl
    inner join public.cross_instances as ci on cl.cross_instance_id = ci.id
    inner join public.crosses as x on ci.cross_id = x.id
    left join public.clutch_plans as cp on cl.planned_cross_id = cp.id
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
    from core as c
    left join mom as m on c.mother_code = m.fish_code
    left join dad as d on c.father_code = d.fish_code
    left join lateral (
        with toks as (
            select
                unnest(string_to_array(nullif(m.canonical, ''), ' ; ')) as can,
                unnest(string_to_array(nullif(m.pretty, ''), ' ; ')) as pre
            union all
            select
                unnest(string_to_array(nullif(d.canonical, ''), ' ; ')) as can,
                unnest(string_to_array(nullif(d.pretty, ''), ' ; ')) as pre
        )

        select
            string_agg(distinct can, ' ; ' order by can) as canonical_union,
            string_agg(distinct pre, ' ; ' order by pre) as pretty_union
        from toks
        where coalesce(can, '') <> '' and coalesce(pre, '') <> ''
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
    coalesce(t.treatments_count, 0)::int as treatments_count,
    coalesce(a.annotations_count, 0)::int as annotations_count,
    a.last_annotated_at,
    j.clutch_birthday,
    j.date_planned,
    j.created_by_plan,
    -- treatments (assumes your v_clutch_treatments_summary already exists)
    j.created_at_plan,
    j.created_by_instance,
    j.created_at_instance,
    -- annotations (new)
    coalesce(j.planned_name, j.clutch_genotype_pretty) as clutch_name,
    coalesce(j.planned_nickname, coalesce(j.planned_name, j.clutch_genotype_pretty)) as clutch_nickname,
    coalesce(j.mom_genotype_raw, j.mother_code) as mom_genotype,
    -- metadata
    coalesce(j.dad_genotype_raw, j.father_code) as dad_genotype,
    public.gen_clutch_strain(j.mother_code, j.father_code) as clutch_strain,
    concat_ws(' × ', nullif(j.mom_strain, ''), nullif(j.dad_strain, '')) as clutch_strain_pretty,
    coalesce(t.treatments_pretty, '') as treatments_pretty,
    coalesce(t.treatments_json, '[]'::jsonb) as treatments_json,
    coalesce(a.annotation_rollup, '') as annotation_rollup
from joined as j
left join public.v_clutch_treatments_summary as t on j.clutch_id = t.clutch_id
left join public.v_clutch_annotations_summary as a on j.clutch_id = a.clutch_id;
