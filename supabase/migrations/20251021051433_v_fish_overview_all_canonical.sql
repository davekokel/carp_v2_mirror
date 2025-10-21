\set ON_ERROR_STOP on
begin;

create or replace view public.v_fish_overview_all as
with geno as (
  select
    f.id                                  as fish_id,
    string_agg(
      'Tg('||fta.transgene_base_code||')'||coalesce(ta.allele_name,''),
      '; ' order by fta.transgene_base_code, coalesce(ta.allele_name,'')
    ) as genotype_rollup
  from public.fish f
  left join public.fish_transgene_alleles fta on fta.fish_id = f.id
  left join public.transgene_alleles ta
    on ta.transgene_base_code = fta.transgene_base_code
   and ta.allele_number       = fta.allele_number
  group by f.id
),
living as (
  select m.fish_id, count(*)::int as n_living_tanks
  from public.fish_tank_memberships m
  where m.left_at is null
  group by m.fish_id
)
select
  f.id                   as fish_id,
  f.fish_code,
  coalesce(f.name,'')    as fish_name,
  coalesce(f.nickname,'')as fish_nickname,
  coalesce(f.genetic_background,'') as genetic_background,
  f.date_birth           as birthday,
  coalesce(g.genotype_rollup,'')  as genotype_rollup,
  coalesce(l.n_living_tanks,0)    as n_living_tanks,
  f.created_at,
  f.updated_at,
  ''::text               as created_by  -- populate if you track it
from public.fish f
left join geno g   on g.fish_id = f.id
left join living l on l.fish_id = f.id
order by f.created_at desc nulls last;

commit;
