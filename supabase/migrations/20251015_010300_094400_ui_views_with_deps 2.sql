create or replace view public.vw_fish_overview_with_label as
with base as (
    select
        f.fish_code,
        f.name,
        f.nickname,
        f.line_building_stage,
        f.date_birth,
        f.genetic_background,
        f.created_by,
        f.created_at
    from fish AS f
),

allele as (
    select distinct on (f2.fish_code)
        f2.fish_code,
        l.transgene_base_code,
        l.allele_number,
        ta.allele_nickname
    from fish_transgene_alleles AS l
    inner join fish AS f2 on l.fish_id = f2.id
    left join transgene_alleles AS ta
        on l.transgene_base_code = ta.transgene_base_code and l.allele_number = ta.allele_number
    order by f2.fish_code, l.transgene_base_code, l.allele_number
),

batch as (
    select distinct on (f3.fish_code)
        f3.fish_code,
        m.seed_batch_id
    from fish_seed_batches_map AS m
    inner join fish AS f3 on m.fish_id = f3.id
    order by f3.fish_code asc, m.logged_at desc nulls last, m.created_at desc nulls last
)

select
    b.fish_code,
    b.name,
    b.nickname,
    b.line_building_stage,
    b.date_birth,
    b.genetic_background,
    b.created_by,
    b.created_at,
    a.transgene_base_code as transgene_base_code_filled,
    a.allele_number::text as allele_code_filled,
    a.allele_nickname as allele_name_filled,
    batch.seed_batch_id,
    batch.seed_batch_id as batch_label,
    NULL::text as plasmid_injections_text,
    NULL::text as rna_injections_text,
    COALESCE(b.nickname, ''::text) as nickname_print,
    COALESCE(b.genetic_background, ''::text) as genetic_background_print,
    COALESCE(b.line_building_stage, ''::text) as line_building_stage_print,
    COALESCE(TO_CHAR(b.date_birth::timestamp with time zone, 'YYYY-MM-DD'::text), ''::text) as date_birth_print,
    case
        when a.transgene_base_code is NULL then ''::text
        when a.allele_number is not NULL then (a.transgene_base_code || '-'::text) || a.allele_number::text
        when a.allele_nickname is not NULL then (a.transgene_base_code || ' '::text) || a.allele_nickname
        else a.transgene_base_code
    end as genotype_print,
    case
        when b.date_birth is not NULL then CURRENT_DATE - b.date_birth
        else NULL::integer
    end as age_days,
    case
        when b.date_birth is not NULL then (CURRENT_DATE - b.date_birth) / 7
        else NULL::integer
    end as age_weeks,
    COALESCE(b.created_by, ''::text) as created_by_enriched
from base AS b
left join allele AS a on b.fish_code = a.fish_code
left join batch AS using (fish_code)
order by b.fish_code;

create or replace view public.vw_planned_clutches_overview as
with x as (
    select
        cp.id as clutch_plan_id,
        pc.id as planned_cross_id,
        cp.clutch_code,
        cp.planned_name as clutch_name,
        cp.planned_nickname as clutch_nickname,
        pc.cross_date,
        cp.created_by,
        cp.created_at,
        COALESCE(cp.note, pc.note) as note
    from clutch_plans AS cp
    left join planned_crosses AS pc on cp.id = pc.clutch_id
),

tx as (
    select
        t.clutch_id as clutch_plan_id,
        COUNT(*)::integer as n_treatments
    from clutch_plan_treatments AS t
    group by t.clutch_id
)

select
    x.clutch_plan_id,
    x.planned_cross_id,
    x.clutch_code,
    x.clutch_name,
    x.clutch_nickname,
    x.cross_date,
    x.created_by,
    x.created_at,
    x.note,
    COALESCE(tx.n_treatments, 0) as n_treatments
from x  left join tx AS on x.clutch_plan_id = tx.clutch_plan_id
order by (COALESCE(x.cross_date::timestamp with time zone, x.created_at)) desc nulls last;

create or replace view public.v_fish_overview as
select
    f.fish_code,
    f.name,
    f.nickname,
    f.line_building_stage,
    f.date_birth,
    f.genetic_background,
    f.created_at,
    DATE_PART('day'::text, NOW() - f.date_birth::timestamp with time zone)::integer as age_days,
    NULLIF(ARRAY_TO_STRING(ARRAY(
        select (fa2.transgene_base_code || '^'::text) || fa2.allele_number::text
        from fish_transgene_alleles AS fa2
        where fa2.fish_id = f.id
        order by fa2.transgene_base_code, fa2.allele_number
    ), '; '::text), ''::text) as genotype_text
from fish AS f
order by f.created_at desc;

create or replace view public.v_cross_concepts_overview as
select
    cp.clutch_code as conceptual_cross_code,
    cp.clutch_name as name,
    cp.clutch_nickname as nickname,
    hum.mom_tank_label as mom_code,
    hum.dad_tank_label as dad_code,
    hum.mom_tank_label as mom_code_tank,
    hum.dad_tank_label as dad_code_tank,
    cp.created_at
from vw_clutches_concept_overview AS cp
left join vw_clutches_overview_human AS hum on cp.clutch_code = hum.clutch_code;
