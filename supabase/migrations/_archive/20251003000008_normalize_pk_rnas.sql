begin;

create extension if not exists pgcrypto;
DO 28762
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='rnas' and column_name='id_uuid'
  )
  and not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='rnas' and column_name='id'
  ) then
    alter table public.rnas rename column id_uuid to id;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='rnas' and column_name='id'
  ) then
    alter table public.rnas add column id uuid not null default gen_random_uuid();
    alter table public.rnas alter column id drop default;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='rnas' and column_name='id_uuid'
  ) then
    alter table public.rnas add column id_uuid uuid generated always as (id) stored;
  end if;

  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and tablename='rnas' and indexname='uq_rnas_id'
  ) then
    create unique index uq_rnas_id on public.rnas(id);
  end if;

  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and tablename='rnas' and indexname='uq_rnas_id_uuid_compat'
  ) then
    create unique index uq_rnas_id_uuid_compat on public.rnas(id_uuid);
  end if;

  if not exists (
    select 1
    from pg_constraint c
    join pg_class t on t.oid=c.conrelid
    join pg_namespace n on n.oid=t.relnamespace
    where c.contype='p' and n.nspname='public' and t.relname='rnas'
  ) then
    alter table public.rnas add primary key (id);
  end if;
end $$;

commit;
