begin;

-- 0) make sure the UUID column is non-null
alter table public.clutch_instances
  alter column id_uuid set not null;

-- 1) drop the legacy FK from bruker_mounts → clutch_instances(id)
-- (name from error: bruker_mounts_selection_id_fkey; drop if exists to be safe)
alter table public.bruker_mounts
  drop constraint if exists bruker_mounts_selection_id_fkey;

-- 2) drop the current PK on clutch_instances (on int id)
-- (name is clutch_instances_pkey as per error)
alter table public.clutch_instances
  drop constraint if exists clutch_instances_pkey;

-- 3) add the new PK on id_uuid
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conrelid='public.clutch_instances'::regclass AND contype='p'
  ) THEN
    ALTER TABLE public.clutch_instances ADD CONSTRAINT clutch_instances_pkey_uuid PRIMARY KEY (id_uuid);
  END IF;
END;
$$ LANGUAGE plpgsql;

-- 4) add the new FK from bruker_mounts(selection_id_uuid) → clutch_instances(id_uuid)
alter table public.bruker_mounts
  add constraint fk_bm_selection_uuid
  foreign key (selection_id_uuid)
  references public.clutch_instances(id_uuid)
  on delete restrict;

commit;
