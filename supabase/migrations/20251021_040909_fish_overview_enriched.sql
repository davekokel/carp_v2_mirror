create or replace view public.v_fish_overview_enriched as
select
  f.id                               as fish_id,
  f.fish_code                        as fish_code,
  f.name                             as fish_name,
  f.nickname                         as fish_nickname,
  f.genetic_background               as genetic_background,

  fta.transgene_base_code            as transgene_base_code,
  fta.allele_number                  as allele_number,
  ta.allele_name                     as allele_name,
  ta.allele_nickname                 as allele_nickname,
  coalesce(ta.allele_nickname, ta.allele_name) as transgene_pretty_nickname,

  vt.tank_code                       as tank_code,
  vt.status                          as tank_status,

  f.line_building_stage              as stage,
  f.date_birth                       as date_birth,
  f.created_at                       as created_at,
  f.created_by                       as created_by
from public.fish f
left join public.fish_transgene_alleles fta
  on fta.fish_id = f.id
left join public.transgene_alleles ta
  on ta.transgene_base_code = fta.transgene_base_code
 and ta.allele_number       = fta.allele_number
left join public.v_tanks_for_fish vt
  on vt.fish_id = f.id;
