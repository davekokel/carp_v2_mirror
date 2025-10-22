-- Ensure code column exists
alter table public.clutch_instances
  add column if not exists clutch_instance_code text;

-- Ensure uniqueness only on this column (drop any existing uniques on it)
DO $$
DECLARE c text;
BEGIN
  FOR c IN
    SELECT conname
    FROM   pg_constraint
    WHERE  conrelid='public.clutch_instances'::regclass
       AND contype='u'
       AND (
         SELECT array_agg(a.attname::text ORDER BY a.attnum)
         FROM   unnest(conkey) AS colnum
         JOIN   pg_attribute a ON a.attrelid='public.clutch_instances'::regclass AND a.attnum=colnum
       ) = ARRAY['clutch_instance_code']::text[]
  LOOP
    EXECUTE format('alter table public.clutch_instances drop constraint %I', c);
  END LOOP;
END$$;

alter table public.clutch_instances
  add constraint uq_clutch_instance_code unique (clutch_instance_code);

-- (Re)create the code-fill trigger
drop trigger if exists trg_clutch_instance_code on public.clutch_instances;
create trigger trg_clutch_instance_code
before insert on public.clutch_instances
for each row execute function public.trg_clutch_instance_code();
