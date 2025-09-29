-- 1) Ensure dictionary rows
insert into public.transgenes (transgene_base_code)
select distinct trim(transgene_base_code)
from raw.wide_fish_upload
where trim(coalesce(transgene_base_code,'')) <> ''
on conflict do nothing;

insert into public.transgene_alleles (transgene_base_code, allele_number)
select distinct
  trim(transgene_base_code),
  (allele_number)::text               -- ← CAST to text
from raw.wide_fish_upload
where trim(coalesce(transgene_base_code,'')) <> ''
  and allele_number is not null
on conflict do nothing;

-- 2) Ensure fish by name
insert into public.fish (name)
select distinct trim(fish_name)
from raw.wide_fish_upload
where trim(coalesce(fish_name,'')) <> ''
on conflict (name) do nothing;

-- 3) Create fish ↔ allele links (use text consistently)
with links as (
  select
    trim(fish_name)             as fish_name,
    trim(transgene_base_code)   as base,
    (allele_number)::text       as num_text,   -- ← CAST to text
    lower(coalesce(trim(zygosity),'unknown')) as z
  from raw.wide_fish_upload
  where trim(coalesce(transgene_base_code,'')) <> ''
    and allele_number is not null
)
insert into public.fish_transgene_alleles
  (fish_id, transgene_base_code, allele_number, zygosity)
select
  f.id,
  l.base,
  l.num_text,                   -- ← text
  l.z
from links l
join public.fish f
  on f.name = l.fish_name
join public.transgene_alleles ta
  on ta.transgene_base_code = l.base
 and ta.allele_number       = l.num_text   -- ← text join
on conflict do nothing;
