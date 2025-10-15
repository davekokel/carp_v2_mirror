begin;

-- clutch_instances: free the name "id", then promote the uuid name
alter table public.clutch_instances
  rename column id to id_int;

alter table public.clutch_instances
  rename column id_uuid to id;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='clutch_instances_pkey_uuid')
     AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='clutch_instances_pkey')
  THEN
    EXECUTE 'ALTER TABLE public.clutch_instances RENAME CONSTRAINT clutch_instances_pkey_uuid TO clutch_instances_pkey';
  END IF;
END;
$$ LANGUAGE plpgsql;
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
end
$$ LANGUAGE plpgsql;

commit;
