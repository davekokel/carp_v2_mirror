begin;

-- clutch_instances: id_uuid -> id, and PK name to standard
alter table public.clutch_instances
  rename column id_uuid to id;

alter table public.clutch_instances
  rename constraint clutch_instances_pkey_uuid to clutch_instances_pkey;

-- bruker_mounts: selection_id_uuid -> selection_id, plus FK/index rename
alter table public.bruker_mounts
  rename column selection_id_uuid to selection_id;

alter table public.bruker_mounts
  rename constraint fk_bm_selection_uuid to fk_bm_selection_id;

do $$
begin
  if exists (
    select 1 from pg_class where relname='ix_bm_selection_id_uuid'
  ) then
    execute 'alter index ix_bm_selection_id_uuid rename to ix_bm_selection_id';
  end if;
end$$;

commit;
