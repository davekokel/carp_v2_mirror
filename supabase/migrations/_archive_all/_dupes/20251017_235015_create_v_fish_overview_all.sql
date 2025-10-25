-- v_fish_overview_all: single source of truth for UI tables
-- One row per fish_code with CSV meta + clean genetics + counts + zygosity (for displayed base)

create or replace view public.v_fish_overview_all as
with
-- 1) Clean genetics / displayed base, rollups, audit
clean as (
    select
        c.fish_code,
        c.genotype,
        c.genetic_background,
        c.birthday,
        c.transgene_base,           -- displayed base
        c.allele_number,
        c.allele_name,
        c.allele_nickname,
        c.transgene_pretty_nickname,
        c.transgene_pretty_name,
        c.genotype_rollup_clean,
        c.created_at,
        c.created_by
    from public.v_fish_standard_clean AS c
),

-- 2) Fish meta (CSV) with safe fallbacks
fish_meta as (
    select
        f.fish_code,
        /* prefer label view if present; fallback to fish */
        f.created_at as created_at_fish,
        coalesce(lv.name, f.name, '') as name,
        /* robust pull for optional columns across schemas */
        coalesce(lv.nickname, f.nickname, '') as nickname,
        coalesce(
            (row_to_json(f)::jsonb ->> 'line_building_stage'),
            (row_to_json(f)::jsonb ->> 'line_building_stage_print'), ''
        ) as line_building_stage,
        coalesce((row_to_json(f)::jsonb ->> 'description'), '') as description,
        coalesce((row_to_json(f)::jsonb ->> 'notes'), '') as notes,
        coalesce(f.created_by, '') as created_by_fish
    from public.fish AS f
    left join public.v_fish_label_fields AS lv
        on f.fish_code = lv.fish_code
),

-- 3) Live counts (optional view)
counts as (
    select
        fish_code,
        coalesce(n_live, 0) as n_live
    from public.v_fish_live_counts
),

-- 4) Zygosity for the displayed base (one per fish_code + base)
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
    fm.name,

    -- meta (CSV)
    fm.nickname,
    fm.line_building_stage,
    fm.description,
    fm.notes,
    cl.birthday,
    cl.transgene_base,
    cl.allele_number,

    -- audit (prefer clean; fallback to fish table)
    cl.allele_name,
    cl.allele_nickname,

    -- linkage/clean genetics
    z.zygosity,
    cl.transgene_pretty_nickname,
    cl.transgene_pretty_name,
    cl.genotype,
    cl.genotype_rollup_clean,
    cl.transgene_base as transgene_base_code,
    coalesce(cl.fish_code, fm.fish_code) as fish_code,
    coalesce(cl.genetic_background, '') as genetic_background,
    coalesce(cl.created_by, fm.created_by_fish) as created_by,

    -- alias for CSV header convenience
    coalesce(cl.created_at, fm.created_at_fish) as created_at,

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
'One row per fish_code: CSV meta (name/nickname/stage/description/notes/birthday/created_by), clean genetics/pretty/rollup, transgene_base/allele fields, zygosity for displayed base, n_living_tanks.';
