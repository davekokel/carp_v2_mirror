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
from v_clutches_concept_overview AS cp
left join v_clutches_overview_human AS hum on cp.clutch_code = hum.clutch_code;
