begin;
create extension if not exists pgcrypto;

-- 1) add uuid id column
alter table public.transgenes
  add column if not exists id uuid default gen_random_uuid();

-- 2) keep natural key unique (assuming transgene_base_code is the natural key column name);
DO 28762
BEGIN
  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and tablename='transgenes' and indexname='uq_transgenes_transgene_base_code'
  ) then
    execute 'create unique index uq_transgenes_transgene_base_code on public.transgenes(transgene_base_code)';
  end if;
end
$$ LANGUAGE plpgsql;

-- 3) promote id to PK (drop existing PK if any);
DO 28762
BEGIN
declare pk_name text;
begin
  select conname into pk_name
  from pg_constraint
  where conrelid='public.transgenes'::regclass and contype='p';

  if pk_name is not null then
    execute format('alter table public.transgenes drop constraint %I', pk_name);
  end if;

  execute 'alter table public.transgenes add constraint transgenes_pkey primary key (id)';
end;
END;
$$ LANGUAGE plpgsql;

commit;
