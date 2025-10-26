create or replace view public.v_fish_rich as
with
vf as (
  select * from public.v_fish
),
fb as (
  select
    f.id                  as fish_id,
    f.fish_code           as fish_code,
    f.name                as fish_name,
    f.nickname            as fish_nickname,
    f.genetic_background  as genetic_background,
    f.line_building_stage as line_building_stage,
    f.created_at          as fish_created_at,
    f.created_by          as fish_created_by,
    f.date_birth          as date_birth
  from public.fish f
),
live_cte as (
  select
    ftm.fish_id,
    count(*) filter (where ftm.left_at is null)::int as n_living_tanks_derived
  from public.fish_tank_memberships ftm
  group by ftm.fish_id
),
first_tank as (
  select distinct on (ftm.fish_id)
    ftm.fish_id,
    t.tank_code       as first_tank_code,
    t.status          as first_tank_status,
    ftm.joined_at     as first_tank_joined_at
  from public.fish_tank_memberships ftm
  join public.tanks t
    on t.tank_uuid = ftm.container_id
  where ftm.left_at is null
  order by ftm.fish_id, ftm.joined_at asc nulls last
),
alleles as (
  select
    fta.fish_id,
    min(fta.allele_number)::int as allele_number_primary,
    array_agg(fta.allele_number order by fta.allele_number) as allele_numbers,
    array_agg(fta.transgene_base_code || '-' || fta.allele_number
              order by fta.transgene_base_code, fta.allele_number) as allele_codes
  from public.fish_transgene_alleles fta
  group by fta.fish_id
),
base as (
  select
    coalesce(vf.fish_id,  fb.fish_id)  as fish_id,
    coalesce(vf.fish_code,fb.fish_code) as fish_code,
    fb.fish_name,
    fb.fish_nickname,
    fb.genetic_background,
    fb.line_building_stage,
    fb.date_birth,
    coalesce( (to_jsonb(vf)->>'created_at')::timestamp, fb.fish_created_at ) as created_at,
    coalesce(  to_jsonb(vf)->>'created_by',                   fb.fish_created_by ) as created_by,
    to_jsonb(vf)->>'transgene_pretty_name' as transgene_pretty_name,
    to_jsonb(vf)->>'genotype_rollup'       as genotype_rollup,
    to_jsonb(vf)->>'transgene_base_code'   as transgene_base_code,
    (to_jsonb(vf)->>'n_living_tanks')::int as n_living_tanks
  from vf
  full join fb
    on vf.fish_code = fb.fish_code
)
select
  b.fish_id,
  b.fish_code,
  b.fish_name,
  b.fish_nickname,
  b.genetic_background,
  b.line_building_stage,
  a.allele_number_primary as allele_number,
  case
    when a.allele_number_primary is not null and b.transgene_base_code is not null
      then b.transgene_base_code || '-' || a.allele_number_primary
    else null
  end                       as allele_code,
  a.allele_numbers,
  a.allele_codes,
  ft.first_tank_code        as tank_code,
  ft.first_tank_status      as tank_status,
  ft.first_tank_joined_at,
  b.transgene_pretty_name   as transgene,
  b.genotype_rollup,
  coalesce(b.n_living_tanks, l.n_living_tanks_derived, 0) as n_living_tanks,
  b.created_at,
  b.created_by,
  b.date_birth
from base b
left join live_cte   l  on l.fish_id  = b.fish_id
left join first_tank ft on ft.fish_id = b.fish_id
left join alleles    a  on a.fish_id  = b.fish_id;
