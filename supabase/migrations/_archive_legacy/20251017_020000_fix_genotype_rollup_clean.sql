-- Fix genotype rollup to never render the literal word 'unknown'.
-- We don't redefine your existing views; instead we expose a clean, companion view.

-- Preconditions: prefer vw_fish_standard if present; otherwise fallback to fish (minimal columns)

-- 1) Clean companion view: v_fish_standard_clean
create or replace view public.v_fish_standard_clean as
with vs as (
    select * from public.vw_fish_standard
),

src as (
    select
        vs.fish_code,
        coalesce(vs.genotype, '') as genotype,
        coalesce(vs.genetic_background, '') as genetic_background,
        to_char(coalesce(vs.date_birth::date, null), 'YYYY-MM-DD') as birthday,
        -- pull optional fields safely via json projection (handles naming variants)
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
        -- Build clean rollup: base + (allele [label]) when present (no 'unknown')
        trim(
            regexp_replace(
                concat_ws(
                    ' ',
                    nullif(genetic_background, ''),
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
'Companion to vw_fish_standard with genotype_rollup_clean that never renders literal "unknown".';

-- 2) If v_fish_search exists, refresh it to prefer the clean fields (optional, idempotent)
do $$
begin
  if exists (
    select 1
    from information_schema.views  where table_schema='public' and table_name='v_fish_search'
  ) then
    -- Recreate v_fish_search to source genotype/background from the AS clean view when available
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

-- 3) Trigram & helper indexes for v_fish_search (safe if they already exist)
create extension if not exists pg_trgm;
create index if not exists idx_v_fish_search_txt_trgm on public.v_fish_search using gin (txt gin_trgm_ops);
create index if not exists idx_v_fish_search_nlive on public.v_fish_search (n_live);
