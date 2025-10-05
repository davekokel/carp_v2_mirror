-- One row per fish; includes batch/seed, primary allele, and aggregated lists
drop view if exists public.v_fish_overview_canonical cascade;

create view public.v_fish_overview_canonical as
with links as (
  select
    fta.fish_id,
    fta.transgene_base_code,
    fta.allele_number,
    fta.zygosity,
    fta.created_at,
    (fta.transgene_base_code || '-' || fta.allele_number)::text as allele_code,
    row_number() over (partition by fta.fish_id order by fta.created_at desc nulls last, fta.transgene_base_code, fta.allele_number) as rn
  from public.fish_transgene_alleles fta
),
agg as (
  select
    f.id_uuid,
    array_remove(array_agg(distinct l.transgene_base_code), null) as transgene_base_codes,
    array_remove(array_agg(distinct l.allele_code), null)         as allele_codes,
    array_remove(array_agg(distinct l.zygosity), null)             as zygosities,
    max(l.transgene_base_code) filter (where l.rn = 1)             as primary_transgene_base_code,
    max(l.allele_code)          filter (where l.rn = 1)             as primary_allele_code,
    max(l.zygosity)             filter (where l.rn = 1)             as primary_zygosity
  from public.fish f
  left join links l on l.fish_id = f.id_uuid
  group by f.id_uuid
),
lists as (
  select
    a.id_uuid,
    case when a.transgene_base_codes is null then null else array_to_string(a.transgene_base_codes, ', ') end as transgene_base_codes_list,
    case when a.allele_codes         is null then null else array_to_string(a.allele_codes,         ', ') end as allele_codes_list,
    case when a.zygosities           is null then null else array_to_string(a.zygosities,           ', ') end as zygosities_list
  from agg a
),
batch as (
  select distinct on (m.fish_id)
    m.fish_id,
    m.batch_label,
    m.seed_batch_id
  from public.fish_seed_batches_map m
  order by m.fish_id, m.logged_at desc nulls last, m.created_at desc nulls last
)
select
  f.id_uuid,
  f.fish_code,
  f.name,
  f.nickname,
  f.created_at,
  f.created_by,
  f.date_birth,
  b.batch_label,
  b.seed_batch_id,
  coalesce(b.batch_label, b.seed_batch_id) as batch_display,
  a.primary_transgene_base_code,
  a.primary_allele_code,
  a.primary_zygosity,
  a.transgene_base_codes,
  a.allele_codes,
  a.zygosities,
  l.transgene_base_codes_list,
  l.allele_codes_list,
  l.zygosities_list
from public.fish f
left join agg  a on a.id_uuid = f.id_uuid
left join lists l on l.id_uuid = f.id_uuid
left join batch b on b.fish_id = f.id_uuid
order by f.created_at desc nulls last, f.fish_code;
