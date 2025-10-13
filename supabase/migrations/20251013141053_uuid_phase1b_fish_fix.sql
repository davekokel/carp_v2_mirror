begin;
create extension if not exists pgcrypto;

-- add column if missing; set default, but do NOT force-update if generated
alter table public.fish
  add column if not exists id_uuid uuid;

-- ensure default present
alter table public.fish
  alter column id_uuid set default gen_random_uuid();

-- only backfill if column is NOT generated and rows exist
do $$
declare is_gen text; has_rows boolean;
begin
  select is_generated into is_gen
  from information_schema.columns
  where table_schema='public' and table_name='fish' and column_name='id_uuid';

  select exists(select 1 from public.fish limit 1) into has_rows;

  if coalesce(is_gen,'NEVER')='NEVER' and has_rows then
    update public.fish set id_uuid = gen_random_uuid() where id_uuid is null;
  end if;
end$$;

create unique index if not exists uq_fish_id_uuid on public.fish(id_uuid);
commit;
