begin;
create extension if not exists pgcrypto;

-- 1) Ensure transgenes has a UUID id column
alter table public.transgenes
  add column if not exists id uuid default gen_random_uuid();

-- 2) Keep natural key unique (adjust column name if different)
DO $$
BEGIN
  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and tablename='transgenes' and indexname='uq_transgenes_transgene_base_code'
  ) then
    execute 'create unique index uq_transgenes_transgene_base_code on public.transgenes(transgene_base_code)';
  end if;
end$$;

-- 3) Drop legacy FK in transgene_alleles that depends on current PK
alter table public.transgene_alleles
  drop constraint if exists fk_transgene_alleles_base;

-- 4) Drop current PK on transgenes (whatever its name is), then set PK(id)
do $$
declare pk_name text;
begin
  select conname into pk_name
  from pg_constraint
  where conrelid='public.transgenes'::regclass and contype='p';
  if pk_name is not null then
    execute format('alter table public.transgenes drop constraint %I', pk_name);
  end if;
  execute 'alter table public.transgenes add constraint transgenes_pkey primary key (id)';
end$$;

-- 5) Introduce UUID FK lane on transgene_alleles
alter table public.transgene_alleles
  add column if not exists transgene_id uuid;

create index if not exists ix_ta_transgene_id on public.transgene_alleles(transgene_id);

alter table public.transgene_alleles
  add constraint fk_ta_transgene_id
  foreign key (transgene_id) references public.transgenes(id)
  on delete restrict;

commit;
