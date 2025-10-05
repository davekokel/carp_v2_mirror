begin;

-- 1) Drop historical/experimental fish overview views except the canonical two
do $$
declare r record;
begin
  for r in
    select n.nspname, c.relname
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where c.relkind = 'v'
      and n.nspname = 'public'
      and c.relname ~* '^(vw?_)?fish_overview(_.*)?$'
      and c.relname not in ('v_fish_overview','vw_fish_overview_with_label')
  loop
    execute format('drop view if exists %I.%I cascade', r.nspname, r.relname);
  end loop;
end$$;

-- 2) Canonical base view: one row per fish WITH genotype (≥1 link)
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

-- 3) Canonical label view: decorator over base (no looseness)
drop view if exists public.vw_fish_overview_with_label cascade;

create view public.vw_fish_overview_with_label as
select
  v.id,
  v.fish_code,
  v.name,
  v.transgene_base_code_filled,
  v.allele_code_filled,
  v.allele_name_filled,
  v.created_at,
  v.created_by,
  fsb.seed_batch_id as batch_label,
  coalesce(nullif(btrim(v.created_by),''), nullif(btrim(f.created_by),'')) as created_by_enriched
from public.v_fish_overview v
left join public.fish f  on f.id = v.id
left join public.fish_seed_batches fsb on fsb.fish_id = v.id
order by v.created_at desc;

commit;
