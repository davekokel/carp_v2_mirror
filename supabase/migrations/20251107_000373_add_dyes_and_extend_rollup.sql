begin;

create table if not exists public.dyes (
  id uuid primary key default gen_random_uuid(),
  dye_code text unique,
  dye_name text not null,
  created_at timestamptz default now()
);

alter table public.fusions
  add column if not exists dye_id uuid references public.dyes(id);

create or replace view public.v_fluorescent_marker_rollup as
with base as (
  select f.fish_code, ta.transgene_base_code, ta.allele_number, p.id as plasmid_id
  from public.fish f
  join public.join_fish_transgene_alleles jf on jf.fish_id=f.id
  join public.transgene_alleles ta on ta.transgene_base_code=jf.transgene_base_code and ta.allele_number=jf.allele_number
  join public.plasmids p on p.code=ta.transgene_base_code
),
fus as (
  select distinct b.fish_code, b.transgene_base_code, b.allele_number, fu.fluor_id, fu.tag_id, fu.dye_id
  from base b
  left join public.join_plasmid_fusions jpf on jpf.plasmid_id=b.plasmid_id
  left join public.fusions fu on fu.id=jpf.fusion_id
)
select
  b.fish_code,
  string_agg(distinct (b.transgene_base_code || b.allele_number::text), ',' order by (b.transgene_base_code || b.allele_number::text)) as markers,
  coalesce(string_agg(distinct fl.fluor_name, ',' order by fl.fluor_name), '') as fluors,
  coalesce(string_agg(distinct tg.tag_name,   ',' order by tg.tag_name),   '') as tags,
  coalesce(string_agg(distinct dy.dye_name,   ',' order by dy.dye_name),   '') as dyes
from base b
left join fus x on x.fish_code=b.fish_code and x.transgene_base_code=b.transgene_base_code and x.allele_number=b.allele_number
left join public.fluors fl on fl.id=x.fluor_id
left join public.tags   tg on tg.id=x.tag_id
left join public.dyes   dy on dy.id=x.dye_id
group by b.fish_code;

commit;
