create or replace view public.v_fish_rich as
with alleles as (
  select
    fta.fish_uuid,
    ta.transgene_base_code,
    ta.allele_number,
    ('gu' || ta.allele_number::text) as allele_name,
    ta.allele_nickname,
    ('Tg('||ta.transgene_base_code||')'||coalesce(ta.allele_nickname, 'gu'||ta.allele_number::text)) as transgene_pretty_nickname,
    ('Tg('||ta.transgene_base_code||')'||'gu'||ta.allele_number::text) as transgene_pretty_name
  from public.fish_transgene_alleles fta
  join public.transgene_alleles ta
    on ta.transgene_base_code = fta.transgene_base_code
   and ta.allele_number       = fta.allele_number
),
allele_rollups as (
  select
    fish_uuid,
    array_agg(allele_number   order by transgene_pretty_name)                 as allele_numbers,
    array_agg(allele_name     order by transgene_pretty_name)                 as allele_names,
    array_agg(allele_nickname order by transgene_pretty_name)                 as allele_nicknames,
    string_agg(transgene_pretty_nickname, '; ' order by transgene_pretty_nickname) as genotype_rollup_by_nickname,
    string_agg(transgene_pretty_name,     '; ' order by transgene_pretty_name)     as genotype_rollup_by_name
  from alleles
  group by fish_uuid
),
first_allele as (
  select distinct on (fish_uuid)
    fish_uuid,
    transgene_base_code,
    allele_number,
    allele_name,
    allele_nickname,
    transgene_pretty_nickname,
    transgene_pretty_name
  from alleles
  order by fish_uuid, transgene_pretty_name
)
select
  f.fish_uuid,
  f.fish_code,
  NULL::text as fish_name,
  NULL::text as fish_nickname,
  f.genetic_background,
  f.line_building_stage,
  f.date_birth,
  coalesce(cnt.current_tanks, 0)::int as n_active_tanks,
  coalesce(fa.allele_nickname, '')          as allele_nickname,
  fa.allele_number,
  coalesce(fa.allele_name, '')              as allele_name,
  coalesce(fa.transgene_pretty_nickname,'') as transgene_pretty_nickname,
  coalesce(fa.transgene_pretty_name,'')     as transgene_pretty_name,
  coalesce(ar.allele_numbers,   ARRAY[]::int[])   as allele_numbers,
  coalesce(ar.allele_names,     ARRAY[]::text[])  as allele_names,
  coalesce(ar.allele_nicknames, ARRAY[]::text[])  as allele_nicknames,
  coalesce(ar.genotype_rollup_by_nickname, '')    as genotype_rollup_by_nickname,
  coalesce(ar.genotype_rollup_by_name, '')        as genotype_rollup_by_name,
  f.created_at,
  f.updated_at
from public.fish f
left join public.v_fish_current_tank_counts cnt
  on cnt.fish_uuid = f.fish_uuid
left join first_allele fa
  on fa.fish_uuid = f.fish_uuid
left join allele_rollups ar
  on ar.fish_uuid = f.fish_uuid;
