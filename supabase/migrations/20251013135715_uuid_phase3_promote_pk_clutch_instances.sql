begin;

-- ensure id_uuid is NOT NULL
alter table public.clutch_instances
  alter column id_uuid set not null;

-- drop the current primary key (name-agnostic)
do $$
declare pk_name text;
begin
  select conname
    into pk_name
  from pg_constraint
  where conrelid = 'public.clutch_instances'::regclass
    and contype  = 'p';

  if pk_name is not null then
    execute format('alter table public.clutch_instances drop constraint %I', pk_name);
  end if;
end$$;

-- make id_uuid the PK
alter table public.clutch_instances
  add constraint clutch_instances_pkey_uuid primary key (id_uuid);

-- keep legacy int id around (optional uniqueness if you want)
-- create unique index if not exists uq_clutch_instances_id on public.clutch_instances(id);

commit;
