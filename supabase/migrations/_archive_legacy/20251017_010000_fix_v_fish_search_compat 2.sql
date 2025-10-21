-- Fix v_fish_search to use vw_fish_standard (compat), not vw_fish_overview

-- Drop dependent objects in safe order if present
drop function if exists public.possible_parents_by_tokens(text [], int) cascade;

-- Recreate v_fish_search using vw_fish_standard
create or replace view public.v_fish_search as
select
    f.fish_code,
    lower(coalesce(vs.genotype, '') || ' ' || coalesce(vs.genetic_background, '')) as txt,
    coalesce(vs.genotype, '') as genotype,
    coalesce(vs.genetic_background, '') as genetic_background,
    coalesce(l.n_live, 0) as n_live
from public.fish AS f
left join public.v_fish_live_counts AS l on f.fish_code = l.fish_code
left join public.vw_fish_standard AS vs on f.fish_code = vs.fish_code;

comment on view public.v_fish_search is
'Unified per-fish search text (genotype + background) plus n_live. Built on vw_fish_standard for compatibility.';

-- Rebuild indexes (no-op if they already exist)
create index if not exists idx_v_fish_search_txt_trgm
on public.v_fish_search using gin (txt gin_trgm_ops);

create index if not exists idx_v_fish_search_nlive
on public.v_fish_search (n_live);

-- Recreate the token function
create function public.possible_parents_by_tokens(tokens text [], min_hits int default 1)
returns table (
    fish_code text,
    hits text [],
    hits_count int,
    genotype text,
    genetic_background text,
    n_live int
)
language sql
stable
as $$
with toks as (
  select distinct lower(trim(t)) as tok
  from unnest(coalesce(tokens, array[]::text[])) as t
  where length(trim(t)) >= 3
),
match as (
  select s.fish_code,
         s.genotype,
         s.genetic_background,
         s.n_live,
         array_agg(t.tok order by t.tok) filter (where t.tok is not null and s.txt like ('%'||t.tok||'%')) as hits
  from public.v_fish_search AS s
  left join toks AS t on true
  where s.n_live > 0
  group by s.fish_code, s.genotype, s.genetic_background, s.n_live
)
select m.fish_code,
       coalesce(m.hits, array[]::text[]) as hits,
       coalesce(cardinality(m.hits), 0)  as hits_count,
       m.genotype,
       m.genetic_background,
       m.n_live
from match AS m
where coalesce(cardinality(m.hits),0) >= greatest(min_hits, 0)
order by hits_count desc, n_live desc, m.fish_code;
$$;

comment on function public.possible_parents_by_tokens(text [], int) is
'Return fish with live tanks whose genotype/background matches any of the given tokens; ranked by #hits, then n_live.';
