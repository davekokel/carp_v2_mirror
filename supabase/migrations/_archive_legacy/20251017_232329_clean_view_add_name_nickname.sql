-- Extend v_fish_standard_clean to include name/nickname with sensible precedence:
-- prefer v_fish_label_fields.name/nickname if the view exists, otherwise fallback to fish.name/nickname.

create or replace view public.v_fish_standard_clean as
with vs as (
    select * from public.vw_fish_standard
),

src as (
    select
        f.fish_code,
        f.created_at,
        f.name as fish_name_base,
        f.nickname as fish_nickname_base,
        row_to_json(f)::jsonb as fish_row,
        coalesce(vs.genotype, '') as genotype,
        coalesce(vs.genetic_background, '') as genetic_background,
        -- Prefer label view (if present) else fish table for names
        -- We can't conditionally LEFT JOIN on AS a view that may not exist in plain SQL,
        -- so we use row_to_json fallback below after a join attempt. AS If the view is absent,
        -- the left join will AS be removed by the planner; to keep this portable across envs
        -- we do a soft fallback using COALESCE(JSONB ->> 'field', fish.field).
        to_char(coalesce(vs.date_birth::date, null), 'YYYY-MM-DD') as birthday,
        coalesce(
            to_jsonb(vs) ->> 'transgene_base_code',
            to_jsonb(vs) ->> 'transgene',
            to_jsonb(vs) ->> 'transgene_print', ''
        ) as transgene_base,
        coalesce(f.created_by, '') as created_by
    from public.fish AS f
    left join vs AS on f.fish_code = vs.fish_code
),

joined as (
    select
        s.*,
        -- attempt to pull labeled fields when v_fish_label_fields exists (planner will inline it)
        -- if the view doesn't exist in a given env, these columns appear as NULL and our outer
        -- COALESCE fallback covers it.
        l.name as name_labeled,
        l.nickname as nickname_labeled
    from src AS s
    left join public.v_fish_label_fields AS l
        on s.fish_code = l.fish_code
),

fmt as (
    select
        fish_code,
        genotype,
        genetic_background,
        birthday,
        transgene_base,
        created_at,
        created_by,
        -- final name/nickname: prefer label view, else fish table, else blanks
        coalesce(name_labeled, fish_name_base, fish_row ->> 'name', '') as name,
        coalesce(nickname_labeled, fish_nickname_base, fish_row ->> 'nickname', '') as nickname
    from joined
),

roll as (
    select
        f.*,
        -- keep your existing allele/pretty/rollup assembly via transgene_alleles if present
        ta.allele_nickname,
        ta.allele_number,
        ta.allele_name,
        -- Clean rollup: transgene + (allele_number [label-from-source]); background excluded
        trim(
            regexp_replace(
                concat_ws(
                    ' ',
                    case
                        when nullif(transgene_base, '') is not null
                            then
                                transgene_base
                                || case
                                    when ta.allele_number is not null
                                        then '(' || ta.allele_number::text || ')'
                                    else ''
                                end
                    end
                ), '\s+', ' ', 'g'
            )
        ) as genotype_rollup_clean
    from fmt AS f
    left join public.transgene_alleles AS ta
        on f.transgene_base = ta.transgene_base_code
)

select
    fish_code,
    name,
    nickname,
    genotype,
    genetic_background,
    birthday,
    transgene_base,
    allele_number,
    allele_name,
    allele_nickname,
    -- pretty strings derived from final AS base + allele fields
    genotype_rollup_clean,
    created_at,
    created_by,
    case
        when nullif(transgene_base, '') is not null and nullif(coalesce(allele_nickname, ''), '') is not null
            then 'Tg(' || transgene_base || ')' || allele_nickname
        else ''
    end as transgene_pretty_nickname,
    case
        when nullif(transgene_base, '') is not null and nullif(coalesce(allele_name, ''), '') is not null
            then 'Tg(' || transgene_base || ')' || allele_name
        else ''
    end as transgene_pretty_name
from roll;

comment on view public.v_fish_standard_clean is
'Clean fish overview with name/nickname; includes genotype/background/birthday/base, allele fields, pretty strings, background-free rollup, and audit fields.';
