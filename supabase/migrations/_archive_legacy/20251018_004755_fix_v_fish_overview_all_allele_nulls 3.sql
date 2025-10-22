create or replace view public.v_fish_overview_all as
with clean as (
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

fish_meta as (
    select
        f.fish_code,
        f.created_at as created_at_fish,
        coalesce(lv.name, f.name, '') as name,
        coalesce(lv.nickname, f.nickname, '') as nickname,
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
        v_fish_live_counts.fish_code,
        v_fish_live_counts.n_live
    from public.v_fish_live_counts
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
full join fish_meta AS fm on cl.fish_code = fm.fish_code
left join counts AS cnt on cnt.fish_code = coalesce(cl.fish_code, fm.fish_code)
left join zyg AS z on z.fish_code = coalesce(cl.fish_code, fm.fish_code) and cl.transgene_base = z.transgene_base
order by coalesce(cl.fish_code, fm.fish_code);
