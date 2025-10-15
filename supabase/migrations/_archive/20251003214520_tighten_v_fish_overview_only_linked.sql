-- supabase/migrations/20251003214520_tighten_v_fish_overview_only_linked.sql
begin;

drop view if exists public.v_fish_overview cascade;

create view public.v_fish_overview as
select
  f.id,
  f.fish_code,
  f.name,
  (
    select array_to_string(array_agg(x.base), ', ')
    from (
      select distinct t.transgene_base_code as base
      from public.fish_transgene_alleles t
      where t.fish_id = f.id
      order by 1
    ) x
  ) as transgene_base_code_filled,
  (
    select array_to_string(array_agg(x.an), ', ')
    from (
      select distinct (t.allele_number::text) as an
      from public.fish_transgene_alleles t
      where t.fish_id = f.id
      order by 1
    ) x
  ) as allele_code_filled,
  null::text as allele_name_filled,
  f.created_at,
  f.created_by
from public.fish f
where exists (
  select 1 from public.fish_transgene_alleles t where t.fish_id = f.id
)
order by f.created_at desc;

commit;
