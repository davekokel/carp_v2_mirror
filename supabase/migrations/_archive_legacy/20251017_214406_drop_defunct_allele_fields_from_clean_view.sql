-- Drop/recreate views to remove defunct allele_token / allele_label.

drop materialized view if exists public.mv_fish_search;
drop view if exists public.v_fish_search;
drop view if exists public.v_fish_standard_clean;

create view public.v_fish_standard_clean as
with vs as (
    select * from public.v_fish_standard
),

src as (
    select
        vs.fish_code,
        coalesce(vs.genotype, '') as genotype,
        coalesce(vs.genetic_background, '') as genetic_background,
        to_char(coalesce(vs.date_birth::date, null), 'YYYY-MM-DD') as birthday,
        coalesce(
            to_jsonb(vs.vs) ->> 'transgene_base_code',
            to_jsonb(vs.vs) ->> 'transgene',
            to_jsonb(vs.vs) ->> 'transgene_print', ''
        ) as transgene_base,
        coalesce(
            to_jsonb(vs.vs) ->> 'allele_code',
            to_jsonb(vs.vs) ->> 'allele_number', ''
        ) as allele_token_view,
        coalesce(to_jsonb(vs.vs) ->> 'allele_label', '') as allele_label_view
    from vs
),

joined as (
    select
        s.*,
        ta.allele_nickname,
        (ta.allele_number)::text as allele_number_canon,
        ta.allele_name as allele_name_canon
    from src AS s
    left join public.transgene_alleles AS ta
        on
            nullif(s.allele_token_view, '') is not null
            and (ta.allele_number)::text = s.allele_token_view::text
),

fmt as (
    select
        fish_code,
        genotype,
        genetic_background,
        birthday,
        transgene_base,
        -- keep canonical text values
        coalesce(allele_number_canon, nullif(allele_token_view, '')) as allele_number,
        coalesce(
            allele_name_canon,
            case when nullif(allele_token_view, '') is not null then 'gu' || allele_token_view else '' end
        ) as allele_name,
        coalesce(allele_nickname, '') as allele_nickname,
        -- clean rollup: transgene + (allele_number [label-from-view]); background excluded
        trim(
            regexp_replace(
                concat_ws(
                    ' ',
                    case
                        when nullif(transgene_base, '') is not null
                            then
                                transgene_base
                                || case
                                    when nullif(coalesce(allele_number_canon, allele_token_view, ''), '') is not null
                                        then
                                            '('
                                            || coalesce(allele_number_canon, allele_token_view, '')
                                            || case
                                                when nullif(allele_label_view, '') is not null
                                                    then ' ' || allele_label_view
                                                else ''
                                            end
                                            || ')'
                                    else ''
                                end
                    end
                ), '\s+', ' ', 'g'
            )
        ) as genotype_rollup_clean
    from joined
)

select
    fish_code,
    genotype,
    genetic_background,
    birthday,
    transgene_base,
    allele_number,
    allele_name,
    allele_nickname,
    -- pretty strings (built now that allele_name exists)
    genotype_rollup_clean,
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
from fmt;

comment on view public.v_fish_standard_clean is
'Clean fish standard view — (no allele_token/allele_label). Includes allele_number (global text), allele_name, allele_nickname, pretty strings, and a background-free genotype_rollup_clean.';

-- Recreate v_fish_search pointing to clean fields
create view public.v_fish_search as
select
    f.fish_code,
    lower(coalesce(sc.genotype, '') || ' ' || coalesce(sc.genetic_background, '')) as txt,
    coalesce(sc.genotype, '') as genotype,
    coalesce(sc.genetic_background, '') as genetic_background,
    coalesce(l.n_live, 0) as n_live
from public.fish AS f
left join public.v_fish_live_counts AS l on f.fish_code = l.fish_code
left join public.v_fish_standard_clean AS sc on f.fish_code = sc.fish_code;

-- Recreate MV from the AS view, index for concurrent refresh, and refresh
create materialized view public.mv_fish_search as
select
    fish_code,
    txt,
    genotype,
    genetic_background,
    n_live
from public.v_fish_search AS with no data;

create unique index if not exists ux_mv_fish_search_code on public.mv_fish_search (fish_code);

do $$
declare fn_exists boolean;
begin
  select exists(
    select 1 from pg_proc AS p join pg_namespace AS n on n.oid=p.pronamespace
    where n.nspname='public' and p.proname='refresh_mv_fish_search'
  ) into fn_exists;
  if fn_exists then
    perform public.refresh_mv_fish_search();
  end if;
end$$;
