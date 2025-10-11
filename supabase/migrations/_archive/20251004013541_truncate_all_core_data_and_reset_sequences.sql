begin;

-- Disable FK checks temporarily
set session_replication_role = replica;

-- Truncate everything cascade
truncate table
  public.fish,
  public.fish_transgene_alleles,
  public.transgene_alleles,
  public.transgene_allele_registry,
  public.transgene_allele_counters
restart identity cascade;

-- Reset all sequences explicitly
do $$
declare r record;
begin
  for r in
    select c.oid::regclass::text as relname
    from pg_class c
    join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public' and c.relkind='S'
  loop
    execute format('alter sequence %s restart with 1', r.relname);
  end loop;
end$$;

set session_replication_role = DEFAULT;

commit;
