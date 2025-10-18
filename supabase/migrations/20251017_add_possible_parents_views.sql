-- MIGRATION: add possible_parents plumbing (views + function)
-- Safe, idempotent. Requires public.vw_fish_overview to exist.

-- 0) Extensions
create extension if not exists pg_trgm;

-- 1) Live membership counts per fish
create or replace view public.v_fish_live_counts as
select f.fish_code,
       count(*)::int as n_live
from public.fish f
join public.fish_tank_memberships m
  on m.fish_id = f.id and m.left_at is null
join public.containers c
  on c.id = m.container_id
where c.status in ('active','new_tank')
  and c.container_type in ('inventory_tank','holding_tank','nursery_tank')
group by f.fish_code;

comment on view public.v_fish_live_counts is
'Live tank membership per fish_code, filtered to active/new_tank & relevant tank types.';

-- 2) Searchable fish view (genotype + background + n_live)
--    Assumes public.vw_fish_overview exposes genotype & genetic_background by fish_code.
create or replace view public.v_fish_search as
select f.fish_code,
       lower(coalesce(vo.genotype,'') || ' ' || coalesce(vo.genetic_background,'')) as txt,
       coalesce(vo.genotype,'')           as genotype,
       coalesce(vo.genetic_background,'') as genetic_background,
       coalesce(l.n_live,0)               as n_live
from public.fish f
left join public.vw_fish_overview vo on vo.fish_code = f.fish_code
left join public.v_fish_live_counts l on l.fish_code = f.fish_code;

comment on view public.v_fish_search is
'Unified per-fish search text (genotype + background) plus n_live. Use with pg_trgm for token LIKE.';

-- 3) Indexes to make token search fast
create index if not exists idx_v_fish_search_txt_trgm
  on public.v_fish_search using gin (txt gin_trgm_ops);

create index if not exists idx_v_fish_search_nlive
  on public.v_fish_search (n_live);

-- 4) Token-based possible parents function (no schema changes required)
--    Pass your parsed tokens (genotype + strain) from the app.
drop function if exists public.possible_parents_by_tokens(text[], int) cascade;

create function public.possible_parents_by_tokens(tokens text[], min_hits int default 1)
returns table (
  fish_code text,
  hits       text[],
  hits_count int,
  genotype   text,
  genetic_background text,
  n_live     int
)
language sql
stable
as $$
with toks as (
  -- normalize and de-duplicate tokens from the app
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
  from public.v_fish_search s
  left join toks t on true
  where s.n_live > 0
  group by s.fish_code, s.genotype, s.genetic_background, s.n_live
)
select m.fish_code,
       coalesce(m.hits, array[]::text[]) as hits,
       coalesce(cardinality(m.hits), 0)  as hits_count,
       m.genotype,
       m.genetic_background,
       m.n_live
from match m
where coalesce(cardinality(m.hits),0) >= greatest(min_hits, 0)
order by hits_count desc, n_live desc, m.fish_code;
$$;

comment on function public.possible_parents_by_tokens(text[], int) is
'Return fish with live tanks whose genotype/background matches any of the given tokens; ranked by #hits, then n_live.';
