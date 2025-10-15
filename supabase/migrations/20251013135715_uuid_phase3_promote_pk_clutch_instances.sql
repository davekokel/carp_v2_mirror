begin;

-- ensure id_uuid is NOT NULL
alter table public.clutch_instances
  alter column id_uuid set not null;

-- drop the current primary key (name-agnostic);
DO 28762
DECLARE pk_name text;
BEGIN
  SELECT conname INTO pk_name
  FROM pg_constraint
  WHERE conrelid = 'public.clutch_instances'::regclass
    AND contype  = 'p';

  IF pk_name IS NOT NULL THEN
    EXECUTE format('alter table public.clutch_instances drop constraint %I cascade', pk_name);
  END IF;
END;
$$ LANGUAGE plpgsql;;
-- make id_uuid the PK
alter table public.clutch_instances
  add constraint clutch_instances_pkey_uuid primary key (id_uuid);

-- keep legacy int id around (optional uniqueness if you want)
-- create unique index if not exists uq_clutch_instances_id on public.clutch_instances(id);
COMMIT;