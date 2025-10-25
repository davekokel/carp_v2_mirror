-- Remove background from genotype AS rollup in v_fish_standard_clean, keep only genotype elements.
create or replace view public.v_fish_standard_clean as
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
            to_jsonb(vs.vs) ->> 'allelecode',
            to_jsonb(vs.vs) ->> 'allele_number', ''
        ) as allele_token,
        coalesce(to_jsonb(vs.vs) ->> 'allele_label', '') as allele_label
    from vs
),

fmt as (
    select
        fish_code,
        genotype,
        genetic_background,
        birthday,
        transgene_base,
        allele_token,
        allele_label,
        trim(
            regexp_replace(
                concat_ws(
                    ' ',
                    case
                        when nullif(transgene_base, '') is not null
                            then
                                transgene_base
                                || case
                                    when nullif(allele_token, '') is not null and nullif(allele_label, '') is not null
                                        then '(' || allele_token || ' ' || allele_label || ')'
                                    when nullif(allele_token, '') is not null
                                        then '(' || allele_token || ')'
                                    else ''
                                end
                    end
                ), '\s+', ' ', 'g'
            )
        ) as genotype_rollup_clean
    from src
)

select * from fmt;

comment on view public.v_fish_standard_clean is
'Companion to v_fish_standard with genotype_rollup_clean (no background/strain). Only genotype elements.';

-- Recreate v_fish_search to prefer the clean fields (if the view exists).
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

-- Refresh MV if present (non-concurrent if empty; concurrent otherwise).
do $$
declare
  mv_exists boolean;
  mv_populated boolean;
  fn_exists boolean;
begin
  select exists(
    select 1 from pg_class AS c join pg_namespace AS n on n.oid=c.relnamespace
    where n.nspname='public' and c.relname='mv_fish_search' and c.relkind='m'
  ) into mv_exists;

  if mv_exists then
    select c.relispopulated
    from pg_class AS c join pg_namespace AS n on n.oid=c.relnamespace
    where n.nspname='public' and c.relname='mv_fish_search' and c.relkind='m'
    into mv_populated;

    select exists(
      select 1 from pg_proc AS p join pg_namespace AS n on n.oid=p.pronamespace
      where n.nspname='public' and p.proname='refresh_mv_fish_search'
    ) into fn_exists;

    if fn_exists then
      perform public.refresh_mv_fish_search();
    else
      if mv_populated then
        execute 'REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_fish_search';
      else
        execute 'REFRESH MATERIALIZED VIEW public.mv_fish_search';
      end if;
    end if;
  end if;
end$$;
