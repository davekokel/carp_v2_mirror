begin;

-- 1) Add a stored generated column for clutch birthday
do $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns  WHERE table_schema='public' AND table_name='cross_instances'
      AND column_name='clutch_birthday'
  ) THEN
    ALTER TABLE public.cross_instances
      ADD COLUMN clutch_birthday date
      GENERATED ALWAYS AS ((cross_date + interval '1 day')::date) STORED;
  END IF;
END$$;

comment on column public.cross_instances.clutch_birthday
is 'Clutch birthday = cross_date + 1 day (stored generated column)';

-- 2) Helpful index for date-range queries by birthday
create index if not exists ix_cross_instances_clutch_birthday
on public.cross_instances (clutch_birthday);

-- 3) (Optional) tighten base column: cross_date should be present for realized runs
-- Uncomment if you're ready to enforce:
-- ALTER TABLE public.cross_instances
--   ALTER COLUMN cross_date SET NOT NULL;

commit;
