-- 1) Latest-annotation summary per clutch, with a compact annotation_rollup string
create or replace view public.v_clutch_annotations_summary as
with link as (
    -- Link selection rows to clutch_id
    select
        cl.id as clutch_id,
        ci.id as selection_id,
        ci.cross_instance_id,
        ci.created_at,
        ci.annotated_at,
        ci.annotated_by,
        ci.red_selected,
        ci.green_selected,
        ci.red_intensity,
        ci.green_intensity,
        ci.notes,
        ci.label
    from public.clutches AS cl
    inner join public.cross_instances AS x on cl.cross_instance_id = x.id
    inner join public.clutch_instances AS ci on x.id = ci.cross_instance_id
),

latest as (
    -- Latest row per clutch by annotated_at (fallback created_at)
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
    from link  order by
        clutch_id asc,
        coalesce(annotated_at, created_at) desc,
        created_at desc,
        selection_id desc
),

agg as (
    -- Counts/rollups over all rows per clutch
    select
        l.clutch_id,
        count(*)::int as annotations_count,
        sum(case when coalesce(l.red_selected, false) then 1 else 0 end)::int as red_selected_count,
        sum(case when coalesce(l.green_selected, false) then 1 else 0 end)::int as green_selected_count,
        max(coalesce(l.annotated_at, l.created_at)) as last_annotated_at,
        string_agg(
            distinct coalesce(nullif(btrim(l.annotated_by), ''), null), ', ' order by coalesce(l.annotated_by, '')
        ) as annotators,
        -- compact phenotype counts for the whole clutch history
        case
            when
                sum(case when coalesce(l.red_selected, false) then 1 else 0 end) > 0
                and sum(case when coalesce(l.green_selected, false) then 1 else 0 end) > 0
                then
                    'red:' || sum(case when coalesce(l.red_selected, false) then 1 else 0 end)::text
                    || ' ; green:' || sum(case when coalesce(l.green_selected, false) then 1 else 0 end)::text
            when sum(case when coalesce(l.red_selected, false) then 1 else 0 end) > 0
                then 'red:' || sum(case when coalesce(l.red_selected, false) then 1 else 0 end)::text
            when sum(case when coalesce(l.green_selected, false) then 1 else 0 end) > 0
                then 'green:' || sum(case when coalesce(l.green_selected, false) then 1 else 0 end)::text
            else ''
        end as phenotype_rollup
    from link AS l
    group by l.clutch_id
),

rollup as (
    -- Build the single-line annotation_rollup from the AS latest row only
    select
        lt.clutch_id,
        -- parts for latest row
        case
            when coalesce(lt.red_selected, false)
                then 'red:' || coalesce(nullif(btrim(lt.red_intensity), ''), 'selected')
            else ''
        end as red_part,
        case
            when coalesce(lt.green_selected, false)
                then 'green:' || coalesce(nullif(btrim(lt.green_intensity), ''), 'selected')
            else ''
        end as green_part,
        case
            when nullif(btrim(coalesce(lt.notes, '')), '') is not null
                then 'note:' || left(lt.notes, 120)
            else ''
        end as note_part
    from latest AS lt
),

rollup_fmt as (
    select
        r.clutch_id,
        -- join red/green with ' ; ', then append ", note:…" if present
        (
            case
                when (nullif(r.red_part, '') is not null or nullif(r.green_part, '') is not null)
                    then
                        array_to_string(array[
                            nullif(r.red_part, ''),
                            nullif(r.green_part, '')
                        ], ' ; ')
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
    from rollup AS r
)

select
    a.clutch_id,
    coalesce(a.annotations_count, 0)::int as annotations_count,
    a.last_annotated_at,
    coalesce(a.red_selected_count, 0)::int as red_selected_count,
    coalesce(a.green_selected_count, 0)::int as green_selected_count,
    coalesce(a.annotators, '') as annotators,
    coalesce(a.phenotype_rollup, '') as annotation_phenotype,
    coalesce(rf.annotation_rollup, '') as annotation_rollup,
    -- optional: the latest label if you want it
    (
        select l.label from latest AS l
        where l.clutch_id = a.clutch_id limit 1
    ) as last_annotation_label
from agg AS a
left join rollup_fmt AS rf on a.clutch_id = rf.clutch_id;

-- 2) Recreate final clutch overview with annotation summary joined
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
    coalesce(t.treatments_count, 0)::int as treatments_count,
    coalesce(a.annotations_count, 0)::int as annotations_count,
    a.last_annotated_at,
    j.clutch_birthday,
    j.date_planned,
    j.created_by_plan,
    -- treatments
    j.created_at_plan,
    j.created_by_instance,
    j.created_at_instance,
    -- annotations summary (incl. the single-line rollup you asked for)
    coalesce(j.planned_name, j.clutch_genotype_pretty) as clutch_name,
    coalesce(j.planned_nickname, coalesce(j.planned_name, j.clutch_genotype_pretty)) as clutch_nickname,
    coalesce(j.mom_genotype_raw, j.mother_code) as mom_genotype,
    -- existing metadata
    coalesce(j.dad_genotype_raw, j.father_code) as dad_genotype,
    public.gen_clutch_strain(j.mother_code, j.father_code) as clutch_strain,
    concat_ws(' × ', nullif(j.mom_strain, ''), nullif(j.dad_strain, '')) as clutch_strain_pretty,
    coalesce(t.treatments_pretty, '') as treatments_pretty,
    coalesce(t.treatments_json, '[]'::jsonb) as treatments_json,
    coalesce(a.annotation_rollup, '') as annotation_rollup
from joined AS j
left join public.v_clutch_treatments_summary AS t on j.clutch_id = t.clutch_id
left join public.v_clutch_annotations_summary AS a on j.clutch_id = a.clutch_id;
