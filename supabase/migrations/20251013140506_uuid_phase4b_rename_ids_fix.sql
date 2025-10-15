begin;

-- clutch_instances: free the name "id", then promote the uuid name
alter table public.clutch_instances
  rename column id to id_int;

alter table public.clutch_instances
  rename column id_uuid to id;

alter table public.clutch_instances
  rename constraint clutch_instances_pkey_uuid to clutch_instances_pkey;

-- bruker_mounts: standardize FK column/constraint/index names
alter table public.bruker_mounts
  rename column selection_id_uuid to selection_id;

alter table public.bruker_mounts
  rename constraint fk_bm_selection_uuid to fk_bm_selection_id;

DO $$
BEGIN
  if exists (select 1 from pg_class where relname='ix_bm_selection_id_uuid') then
    execute 'alter index ix_bm_selection_id_uuid rename to ix_bm_selection_id';
  end if;
end$$;

commit;
