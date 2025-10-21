\set ON_ERROR_STOP on
begin;

-- v_fish_overview_all
-- One row per (fish × allele × tank)
-- Pulls alleles from fish_transgene_alleles + transgene_alleles
-- Pulls tanks from v_tanks
-- Adds a deterministic per-fish genotype_rollup

with geno_roll as (
  select
    f.id as fish_id,
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
alleles as (
  select
    fta.fish_id,
    fta.transgene_base_code,
    fta.allele_number,
    ta.allele_name,
    ta.allele_nickname,
    ('Tg('||fta.transgene_base_code||')'||coalesce(ta.allele_name,''))::text as transgene_pretty
  from public.fish_transgene_alleles fta
  left join public.transgene_alleles ta
    on ta.transgene_base_code = fta.transgene_base_code
   and ta.allele_number       = fta.allele_number
),
tanks as (
  select
    vt.fish_id,
    vt.tank_code::text as tankcode,
    vt.status::text    as tank_status,
    vt.tank_created_at
  from public.v_tanks vt
)

create or replace view public.v_fish_overview_all as
select
  f.fish_code                        as fish_code,
  coalesce(f.name,'')                as fish_name,
  coalesce(f.nickname,'')            as fish_nickname,
  coalesce(f.genetic_background,'')  as genetic_background,
  coalesce(f.line_building_stage,'') as line_building_stage,

  a.transgene_base_code              as transgene_base_code,
  a.allele_number                    as allele_number,
  a.allele_name                      as allele_name,
  a.allele_nickname                  as allele_nickname,
  coalesce(a.transgene_pretty,'')    as transgene_pretty,

  coalesce(g.genotype_rollup,'')     as genotype_rollup,

  t.tankcode                         as tankcode,
  t.tank_status                      as tank_status,

  f.date_birth                       as birth_date,
  f.created_at                       as created_time,
  coalesce(f.created_by,'')          as created_by

from public.fish f
left join geno_roll g on g.fish_id = f.id
left join alleles  a on a.fish_id  = f.id
left join tanks    t on t.fish_id  = f.id
order by f.created_at desc nulls last,
         f.fish_code,
         a.transgene_base_code nulls last,
         a.allele_number       nulls last,
         t.tank_created_at     desc nulls last;

commit;
