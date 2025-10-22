begin;

-- Drop existing tank_code shape constraint if present
do $$
DECLARE conname text;
BEGIN
  SELECT conname INTO conname
  FROM pg_constraint  WHERE conrelid='public.containers'::regclass
    AND contype='c'
    AND conname='chk_tank_code_shape';
  IF conname IS NOT NULL THEN
    EXECUTE format('ALTER TABLE public.containers DROP CONSTRAINT %I', conname);
  END IF;
END $$;

-- Enforce only: TANK FSH-<FISH_CODE> #<n>   (no #0, case-insensitive A–Z, digits)
alter table public.containers
add constraint chk_tank_code_shape
check (
    tank_code is NULL
    or tank_code ~ '^TANK FSH-[0-9A-Z]{2}[0-9A-Z]+ #[1-9][0-9]*$'
);

-- Keep uniqueness on non-null codes
create unique index if not exists uq_containers_tank_code
on public.containers (tank_code)
where tank_code is not NULL;

commit;
