begin;

-- Drop any fish overview-like views; we'll recreate the two canonicals next
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
  loop
    execute format('drop view if exists %I.%I cascade', r.nspname, r.relname);
  end loop;
end$$;

-- Canonical base view: one row per fish WITH ≥1 genotype link (baseline-safe)
create view public.v_fish_overview as
select
    f.id,
    f.fish_code,
    f.name,
    (
        select array_to_string(array_agg(x.base), ', ')
        from (
            select distinct t.transgene_base_code as base
            from public.fish_transgene_alleles as t
            where t.fish_id = f.id
            order by 1
        ) as x
    ) as transgene_base_code_filled,
    (
        select array_to_string(array_agg(x.an), ', ')
        from (
            select distinct t.allele_number::text as an
            from public.fish_transgene_alleles as t
            where t.fish_id = f.id
            order by 1
        ) as x
    ) as allele_code_filled,
    null::text as allele_name_filled,
    f.created_at,
    f.created_by
from public.fish as f
where
    exists (
        select 1 from public.fish_transgene_alleles as t
        where t.fish_id = f.id
    )
order by f.created_at desc;

-- Canonical label view: decorator over base (no relaxed semantics)
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
    coalesce(nullif(btrim(v.created_by), ''), nullif(btrim(f.created_by), '')) as created_by_enriched
from public.v_fish_overview as v
left join public.fish as f on v.id = f.id
left join public.fish_seed_batches as fsb on v.id = fsb.fish_id
order by v.created_at desc;

commit;
