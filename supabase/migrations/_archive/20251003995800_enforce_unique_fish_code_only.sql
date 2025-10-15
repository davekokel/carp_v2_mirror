begin;

-- Drop ANY unique constraint on public.fish that starts with UNIQUE (name...
do $$
declare r record;
begin
  for r in
    select c.conname
    from pg_constraint c
    join pg_class t on t.oid = c.conrelid
    join pg_namespace n on n.oid = t.relnamespace
    where n.nspname='public'
      and t.relname='fish'
      and c.contype='u'
      and pg_get_constraintdef(c.oid) ilike 'UNIQUE (name%'
  loop
    execute format('alter table public.fish drop constraint %I', r.conname);
  end loop;
end$$;

-- Ensure fish_code is the single unique identity
create unique index if not exists uq_fish_code on public.fish(fish_code);

-- Optional non-unique index on name (only if the column exists);
DO $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='fish' and column_name='name'
  ) then
    create index if not exists ix_fish_name on public.fish(name);
  end if;
end$$;

commit;
