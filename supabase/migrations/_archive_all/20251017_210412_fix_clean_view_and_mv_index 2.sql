-- 1) Recreate v_fish_standard_clean without ta.allele_label (not in your schema)
--    Prefer canonical allele_number/allele_name/allele_nickname from transgene_alleles. AS create or replace view public.v_fish_standard_clean as
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
        ) as allele_token,
        coalesce(to_jsonb(vs.vs) ->> 'allele_label', '') as allele_label_view
    from vs
),

joined as (
    select
        s.*,
        ta.allele_nickname,
        ta.allele_number as allele_number_canon,
        ta.allele_name as allele_name_canon
    from src AS s
    left join public.transgene_alleles AS ta
        on
            nullif(s.transgene_base, '') is not null
            and nullif(s.allele_token, '') is not null
            and s.transgene_base = ta.transgene_base_code
            and ta.allele_number::text = s.allele_token::text
),

fmt as (
    select
        fish_code,
        genotype,
        genetic_background,
        birthday,
        transgene_base,
        nullif(allele_token, '') as allele_token,
        coalesce(allele_number_canon, nullif(allele_token, '')) as allele_number,
        /* no canonical allele_label column in your schema; keep label from the AS view if present */
        coalesce(nullif(allele_label_view, ''), '') as allele_label,
        coalesce(
            allele_name_canon,
            case when nullif(allele_token, '') is not null then 'gu' || allele_token else '' end
        ) as allele_name,
        coalesce(allele_nickname, '') as allele_nickname,

        /* clean genotype rollup: transgene + (allele_number [label]); background excluded */
        trim(
            regexp_replace(
                concat_ws(
                    ' ',
                    case
                        when nullif(transgene_base, '') is not null
                            then
                                transgene_base
                                || case
                                    when nullif(coalesce(allele_number_canon, allele_token, ''), '') is not null
                                        then
                                            '('
                                            || coalesce(allele_number_canon, allele_token, '')
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
        ) as genotype_rollup_clean,

        /* pretty strings, as requested */
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
    from joined
)

select
    fish_code,
    genotype,
    genetic_background,
    birthday,
    transgene_base,
    allele_token,
    allele_number,
    allele_label,
    allele_nickname,
    allele_name,
    transgene_pretty_nickname,
    transgene_pretty_name,
    genotype_rollup_clean
from fmt;

comment on view public.v_fish_standard_clean is
'Clean fish standard view — enriched allele_number/allele_name/nickname; pretty strings; rollup excludes background.';

-- 2) Ensure mv_fish_search supports CONCURRENT refresh: add a unique index on fish_code if MV exists.
do $$
declare mv_exists boolean;
begin
  select exists(
    select 1 from pg_class AS c join pg_namespace AS n on n.oid=c.relnamespace
    where n.nspname='public' and c.relname='mv_fish_search' and c.relkind='m'
  ) into mv_exists;

  if mv_exists then
    -- create a unique index (required by CONCURRENTLY)
    execute 'create unique index if not exists ux_mv_fish_search_code on public.mv_fish_search (fish_code)';
  end if;
end$$;

-- 3) Recreate v_fish_search to keep pointing at clean fields (idempotent)
do $$
begin
  if exists (
    select 1 from information_schema.views  where table_schema='public' and table_name='v_fish_search'
  ) then
    execute $vfs$
      create or replace view public.v_fish_search as
      select f.fish_code,
             lower(coalesce(sc.genotype, '') || ' ' || coalesce(sc.genetic_background, '')) as txt,
             coalesce(sc.genotype, '')           as genotype,
             coalesce(sc.genetic_background, '') as genetic_background,
             coalesce(l.n_live,0)               as n_live
      from public.fish AS f
      left join public.v_fish_live_counts AS l on l.fish_code = f.fish_code
      left join public.v_fish_standard_clean AS sc on sc.fish_code = f.fish_code;
    $vfs$;
  end if;
end$$;

-- 4) Refresh MV via helper if present (will now use CONCURRENTLY thanks to unique index)
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
