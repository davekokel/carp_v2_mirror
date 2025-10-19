-- Extend v_fish_standard_clean with name/nickname (prefer label view; fallback to fish).

create or replace view public.v_fish_standard_clean as
with vs as (
    select * from public.vw_fish_standard
),

src as (
    select
        f.fish_code,
        vs.date_birth::date as birthday,
        f.created_at,
        coalesce(vs.genotype, '') as genotype,
        coalesce(vs.genetic_background, '') as genetic_background,
        coalesce(
            to_jsonb(vs) ->> 'transgene_base_code',
            to_jsonb(vs) ->> 'transgene',
            to_jsonb(vs) ->> 'transgene_print', ''
        ) as transgene_base,
        coalesce(f.created_by, '') as created_by,
        coalesce(f.name, '') as fish_name_base,
        coalesce(f.nickname, '') as fish_nickname_base
    from public.fish AS f
    left join vs AS on f.fish_code = vs.fish_code
),

joined as (
    select
        s.*,
        -- Try label view; if it doesn't exist in this env, columns resolve null and we fallback
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
        coalesce(name_labeled, fish_name_base) as name,
        coalesce(nickname_labeled, fish_nickname_base) as nickname
    from joined
),

roll as (
    select
        f.*,
        ta.allele_nickname,
        ta.allele_number,
        ta.allele_name,
        trim(regexp_replace(
            concat_ws(
                ' ',
                case
                    when nullif(transgene_base, '') is not null then
                        transgene_base
                        || case when ta.allele_number is not null then '(' || ta.allele_number::text || ')' else '' end
                end
            ), '\s+', ' ', 'g'
        )) as genotype_rollup_clean
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
'Clean fish overview with name/nickname; includes genotype/background/birthday/transgene_base, allele fields, pretty strings, background-free rollup, and audit fields.';
