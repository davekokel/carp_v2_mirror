begin;

-- clutch_instances: id_uuid -> id, and PK name to standard
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='id_uuid'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='id'
  ) THEN
    EXECUTE 'ALTER TABLE public.clutch_instances RENAME COLUMN id_uuid TO id';
  END IF;
END;
$$ LANGUAGE plpgsql;
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='clutch_instances_pkey_uuid'
  ) AND NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='clutch_instances_pkey'
  ) THEN
    EXECUTE 'ALTER TABLE public.clutch_instances RENAME CONSTRAINT clutch_instances_pkey_uuid TO clutch_instances_pkey';
  END IF;
END;
$$ LANGUAGE plpgsql;
-- bruker_mounts: selection_id_uuid -> selection_id, plus FK/index rename
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='bruker_mounts' AND column_name='selection_id_uuid'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='bruker_mounts' AND column_name='selection_id'
  ) THEN
    EXECUTE 'ALTER TABLE public.bruker_mounts RENAME COLUMN selection_id_uuid TO selection_id';
  END IF;
END;
$$ LANGUAGE plpgsql;
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='fk_bm_selection_uuid'
  ) AND NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname='fk_bm_selection_id'
  ) THEN
    EXECUTE 'ALTER TABLE public.bruker_mounts RENAME CONSTRAINT fk_bm_selection_uuid TO fk_bm_selection_id';
  END IF;
END;
$$ LANGUAGE plpgsql;
DO $$
BEGIN
  if exists (
    select 1 from pg_class where relname='ix_bm_selection_id_uuid'
  ) then
    execute 'alter index ix_bm_selection_id_uuid rename to ix_bm_selection_id';
  end if;
end
$$ LANGUAGE plpgsql;

commit;
