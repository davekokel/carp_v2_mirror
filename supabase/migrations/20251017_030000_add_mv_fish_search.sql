-- Materialized search view w/ trigram indexes
create extension if not exists pg_trgm;

create materialized view if not exists public.mv_fish_search as
select
    s.fish_code,
    s.txt,
    s.genotype,
    s.genetic_background,
    s.n_live
from public.v_fish_search AS s
with no data;

-- indexes on the MV
create index if not exists idx_mv_fish_search_txt_trgm on public.mv_fish_search using gin (txt gin_trgm_ops);
create index if not exists idx_mv_fish_search_nlive on public.mv_fish_search (n_live);

comment on materialized view public.mv_fish_search is
'Materialized version of v_fish_search for fast token LIKE. Refresh as needed.';

-- Optional helper to refresh
create or replace function public.refresh_mv_fish_search() returns void
language sql as $$
  refresh materialized view concurrently public.mv_fish_search;
$$;
