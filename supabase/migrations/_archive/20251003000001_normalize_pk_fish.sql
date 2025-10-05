begin;

create extension if not exists pgcrypto;

do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='fish' and column_name='id_uuid'
  )
  and not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='fish' and column_name='id'
  ) then
    alter table public.fish rename column id_uuid to id;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='fish' and column_name='id'
  ) then
    alter table public.fish add column id uuid not null default gen_random_uuid();
    alter table public.fish alter column id drop default;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='fish' and column_name='id_uuid'
  ) then
    alter table public.fish add column id_uuid uuid generated always as (id) stored;
  end if;

  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and tablename='fish' and indexname='uq_fish_id'
  ) then
    create unique index uq_fish_id on public.fish(id);
  end if;

  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and tablename='fish' and indexname='uq_fish_id_uuid_compat'
  ) then
    create unique index uq_fish_id_uuid_compat on public.fish(id_uuid);
  end if;

  if not exists (
    select 1
    from pg_constraint c
    join pg_class t on t.oid=c.conrelid
    join pg_namespace n on n.oid=t.relnamespace
    where c.contype='p' and n.nspname='public' and t.relname='fish'
  ) then
    alter table public.fish add primary key (id);
  end if;
end $$;

commit;
