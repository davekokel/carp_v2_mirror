begin;

create or replace view public.v_fish_overview_human as
with
open_memberships as (
    select
        m.fish_id,
        c.id as container_id,
        c.tank_code,
        c.label,
        c.status,
        c.created_at
    from public.fish_tank_memberships AS m
    inner join public.containers AS c on m.container_id = c.id
    where
        coalesce(
            nullif(to_jsonb(m) ->> 'left_at', '')::timestamptz,
            nullif(to_jsonb(m) ->> 'ended_at', '')::timestamptz
        ) is null
        and (c.status in ('active', 'new_tank') or c.status is null)
),

alleles as (
    select
        fta.fish_id,
        fta.transgene_base_code as base_code,
        fta.allele_number,
        fta.zygosity,
        -- transgene name without assuming a specific column name
        coalesce(ta.allele_nickname, fta.allele_number::text) as allele_nickname,
        coalesce(
            nullif(to_jsonb(tg) ->> 'transgene_name', ''),
            nullif(to_jsonb(tg) ->> 'name', ''),
            nullif(to_jsonb(tg) ->> 'label', ''),
            fta.transgene_base_code
        ) as transgene_name
    from public.fish_transgene_alleles AS fta
    left join public.transgene_alleles AS ta
        on
            fta.transgene_base_code = ta.transgene_base_code
            and fta.allele_number = ta.allele_number
    left join public.transgenes AS tg
        on fta.transgene_base_code = tg.transgene_base_code
),

genotype as (
    select
        a.fish_id,
        string_agg(
            trim(
                both ' ' from
                a.transgene_name || '(' || a.allele_number::text
                || coalesce(' ' || a.zygosity, '') || ')'
            ), ' + ' order by a.transgene_name, a.allele_number
        ) as genotype_rollup,
        min(a.transgene_name) as transgene_primary,
        min(a.allele_number) as allele_number_primary,
        min(a.transgene_name || '(' || a.allele_number::text || ')') as allele_code_primary
    from alleles AS a
    group by a.fish_id
),

current_tank as (
    select distinct on (o.fish_id)
        o.fish_id,
        o.tank_code,
        o.label as tank_label,
        o.status as tank_status,
        o.created_at as tank_created_at
    from open_memberships AS o
    order by o.fish_id asc, o.created_at desc nulls last
)

select
    f.id as fish_id,
    f.fish_code,
    f.name as fish_name,
    f.nickname as fish_nickname,
    f.genetic_background,
    g.allele_number_primary as allele_number,
    g.allele_code_primary as allele_code,
    g.transgene_primary as transgene,
    g.genotype_rollup,
    ct.tank_code,
    ct.tank_label,
    ct.tank_status,
    f.stage,
    f.date_birth,
    f.created_at,
    f.created_by
from public.fish AS f
left join genotype AS g on f.id = g.fish_id
left join current_tank AS ct on f.id = ct.fish_id
order by f.created_at desc nulls last;

commit;
