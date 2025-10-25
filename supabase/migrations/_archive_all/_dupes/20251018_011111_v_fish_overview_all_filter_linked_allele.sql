create or replace view public.v_fish_overview_all as
with clean0 as (
    select
        c.fish_code,
        c.birthday,
        c.allele_number,
        c.created_at,
        coalesce(c.genotype, '') as genotype,
        coalesce(c.genetic_background, '') as genetic_background,
        coalesce(c.transgene_base, '') as transgene_base,
        coalesce(c.allele_name, '') as allele_name,
        coalesce(c.allele_nickname, '') as allele_nickname,
        coalesce(c.transgene_pretty_nickname, '') as transgene_pretty_nickname,
        coalesce(c.transgene_pretty_name, '') as transgene_pretty_name,
        coalesce(c.genotype_rollup_clean, '') as genotype_rollup_clean,
        coalesce(c.created_by, '') as created_by
    from public.v_fish_standard_clean AS c
),

linked as (
    select
        f.fish_code,
        fta.transgene_base_code as transgene_base,
        fta.allele_number
    from public.fish_transgene_alleles AS fta
    inner join public.fish AS f on fta.fish_id = f.id
),

clean as (
    select *
    from (
        select
            c0.*,
            row_number() over (
                partition by c0.fish_code, c0.transgene_base
                order by
                    case when exists (
                        select 1
                        from linked AS l
                        where
                            l.fish_code = c0.fish_code
                            and l.transgene_base = c0.transgene_base
                            and l.allele_number = c0.allele_number
                    ) then 0 else 1 end,
                    (c0.allele_number is null),
                    c0.allele_number asc nulls last,
                    c0.created_at desc nulls last
            ) as rn
        from clean0 AS c0
    ) as s
    where s.rn = 1
),

fish_meta as (
    select
        f.fish_code,
        f.created_at as created_at_fish,
        coalesce(nullif(lv.name, ''), nullif(f.name, ''), '') as name,
        coalesce(nullif(lv.nickname, ''), nullif(f.nickname, ''), '') as nickname,
        coalesce(
            row_to_json(f.*)::jsonb ->> 'line_building_stage',
            row_to_json(f.*)::jsonb ->> 'line_building_stage_print', ''
        ) as line_building_stage,
        coalesce(row_to_json(f.*)::jsonb ->> 'description', '') as description,
        coalesce(row_to_json(f.*)::jsonb ->> 'notes', '') as notes,
        coalesce(f.created_by, '') as created_by_fish
    from public.fish AS f
    left join public.v_fish_label_fields AS lv on f.fish_code = lv.fish_code
),

counts as (
    select
        v.fish_code,
        v.n_live
    from public.v_fish_live_counts AS v
),

zyg as (
    select
        f.fish_code,
        fta.transgene_base_code as transgene_base,
        coalesce(fta.zygosity, '') as zygosity
    from public.fish_transgene_alleles AS fta
    inner join public.fish AS f on fta.fish_id = f.id
)

select
    cl.birthday,
    cl.allele_number,
    coalesce(cl.fish_code, fm.fish_code) as fish_code,
    coalesce(fm.name, '') as name,
    coalesce(fm.nickname, '') as nickname,
    coalesce(cl.genetic_background, '') as genetic_background,
    coalesce(fm.line_building_stage, '') as line_building_stage,
    coalesce(fm.description, '') as description,
    coalesce(fm.notes, '') as notes,
    coalesce(cl.created_by, fm.created_by_fish, '') as created_by,
    coalesce(cl.created_at, fm.created_at_fish) as created_at,
    coalesce(cl.transgene_base, '') as transgene_base,
    coalesce(cl.allele_name, '') as allele_name,
    coalesce(cl.allele_nickname, '') as allele_nickname,
    coalesce(z.zygosity, '') as zygosity,
    coalesce(cl.transgene_pretty_nickname, '') as transgene_pretty_nickname,
    coalesce(cl.transgene_pretty_name, '') as transgene_pretty_name,
    coalesce(cl.genotype, '') as genotype,
    coalesce(cl.genotype_rollup_clean, '') as genotype_rollup_clean,
    coalesce(cl.transgene_base, '') as transgene_base_code,
    coalesce(cnt.n_live, 0) as n_living_tanks
from clean AS cl
full join fish_meta AS fm
    on cl.fish_code = fm.fish_code
left join counts AS cnt
    on cnt.fish_code = coalesce(cl.fish_code, fm.fish_code)
left join zyg AS z
    on
        z.fish_code = coalesce(cl.fish_code, fm.fish_code)
        and cl.transgene_base = z.transgene_base
order by coalesce(cl.fish_code, fm.fish_code);
