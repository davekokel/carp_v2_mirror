begin;

-- clutch_instances PK: rename only if the old name exists
do $$
declare pkname text;
begin
  select conname
    into pkname
  from pg_constraint
  where conrelid='public.clutch_instances'::regclass
    and contype='p';

  -- if current PK name is the temporary one, rename it
  if pkname = 'clutch_instances_pkey_uuid' then
    execute 'alter table public.clutch_instances rename constraint clutch_instances_pkey_uuid to clutch_instances_pkey';
  end if;
end$$;

-- bruker_mounts FK: rename only if the old name exists
DO $$
BEGIN
  if exists (
    select 1 from pg_constraint
    where conrelid='public.bruker_mounts'::regclass
      and conname='fk_bm_selection_uuid'
  ) then
    execute 'alter table public.bruker_mounts rename constraint fk_bm_selection_uuid to fk_bm_selection_id';
  end if;
end$$;

-- index rename: only if the old name exists
DO $$
BEGIN
  if exists (select 1 from pg_class where relname='ix_bm_selection_id_uuid') then
    execute 'alter index ix_bm_selection_id_uuid rename to ix_bm_selection_id';
  end if;
end$$;

commit;
