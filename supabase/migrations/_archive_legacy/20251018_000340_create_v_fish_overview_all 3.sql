-- v_fish_overview_all: single canonical row per fish_code with CSV meta + clean genetics + counts
-- Idempotent: CREATE OR REPLACE VIEW

create or replace view public.v_fish_overview_all as
with
-- Clean genetics / displayed base / rollups / audit (from v_fish_standard_clean)
clean as (
    select
        c.fish_code,
        c.birthday,
        c.created_at,
        coalesce(c.genotype, '') as genotype,
        coalesce(c.genetic_background, '') as genetic_background,      -- displayed base
        coalesce(c.transgene_base, '') as transgene_base,
        coalesce(c.allele_number, 0) as allele_number,
        coalesce(c.allele_name, '') as allele_name,
        coalesce(c.allele_nickname, '') as allele_nickname,
        coalesce(c.transgene_pretty_nickname, '') as transgene_pretty_nickname,
        coalesce(c.transgene_pretty_name, '') as transgene_pretty_name,
        coalesce(c.genotype_rollup_clean, '') as genotype_rollup_clean,
        coalesce(c.created_by, '') as created_by
    from public.v_fish_standard_clean AS c
),

-- CSV/meta fields from fish; safe against legacy *_print columns via JSONB
fish_meta as (
    select
        f.fish_code,
        f.created_at as created_at_fish,
        coalesce(lv.name, f.name, '') as name,
        coalesce(lv.nickname, f.nickname, '') as nickname,
        coalesce(
            (row_to_json(f)::jsonb ->> 'line_building_stage'),
            (row_to_json(f)::jsonb ->> 'line_building_stage_print'), ''
        ) as line_building_stage,
        coalesce((row_to_json(f)::jsonb ->> 'description'), '') as description,
        coalesce((row_to_json(f)::jsonb ->> 'notes'), '') as notes,
        coalesce(f.created_by, '') as created_by_fish
    from public.fish AS f
    left join public.v_fish_label_fields AS lv on f.fish_code = lv.fish_code
),

-- Live counts (optional view; if missing, join will AS NULL → coalesce 0 later)
counts as (
    select
        fish_code,
        n_live
    from public.v_fish_live_counts
),

-- Zygosity per (fish_code, displayed base)
zyg as (
    select
        f.fish_code,
        fta.transgene_base_code as transgene_base,
        coalesce(fta.zygosity, '') as zygosity
    from public.fish_transgene_alleles AS fta
    inner join public.fish AS f on fta.fish_id = f.id
)

select
    -- identity
    cl.birthday,

    -- CSV identity/meta
    coalesce(cl.fish_code, fm.fish_code) as fish_code,
    coalesce(fm.name, '') as name,
    coalesce(fm.nickname, '') as nickname,
    coalesce(cl.genetic_background, '') as genetic_background,
    coalesce(fm.line_building_stage, '') as line_building_stage,
    coalesce(fm.description, '') as description,
    coalesce(fm.notes, '') as notes,

    -- created_by/created_at (prefer clean’s values, else fish table)
    coalesce(cl.created_by, fm.created_by_fish, '') as created_by,
    coalesce(cl.created_at, fm.created_at_fish) as created_at,

    -- linkage/clean genetics
    coalesce(cl.transgene_base, '') as transgene_base,
    coalesce(cl.allele_number, 0) as allele_number,
    coalesce(cl.allele_name, '') as allele_name,
    coalesce(cl.allele_nickname, '') as allele_nickname,
    coalesce(z.zygosity, '') as zygosity,
    coalesce(cl.transgene_pretty_nickname, '') as transgene_pretty_nickname,
    coalesce(cl.transgene_pretty_name, '') as transgene_pretty_name,
    coalesce(cl.genotype, '') as genotype,
    coalesce(cl.genotype_rollup_clean, '') as genotype_rollup_clean,

    -- alias for CSV convenience
    coalesce(cl.transgene_base, '') as transgene_base_code,

    -- counts
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

comment on view public.v_fish_overview_all is
'One row per fish_code with CSV meta (name/nickname/stage/description/notes/birthday/created_by), clean genetics/pretty/rollup, transgene_base/allele fields, zygosity for displayed base, and n_living_tanks.';
