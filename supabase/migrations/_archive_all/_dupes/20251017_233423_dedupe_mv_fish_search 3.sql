-- Recreate mv_fish_search so each fish_code appears once.
-- Keep the row with the highest n_live (ties broken by fish_code/genotype/txt).

drop materialized view if exists public.mv_fish_search;

create materialized view public.mv_fish_search as
select distinct on (fish_code)
    fish_code,
    txt,
    genotype,
    genetic_background,
    n_live
from public.v_fish_search  order by fish_code asc, n_live desc, genotype asc nulls last, txt asc nulls last;

-- Now a UNIQUE index on fish_code is valid
create unique index if not exists ux_mv_fish_search_code on public.mv_fish_search (fish_code);
