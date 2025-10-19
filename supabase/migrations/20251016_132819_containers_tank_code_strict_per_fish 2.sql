begin;

-- Drop existing shape constraint (whatever it is now)
do $$
DECLARE
  conname text;
BEGIN
  SELECT conname INTO conname
  FROM pg_constraint  WHERE conrelid = 'public.containers'::regclass
    AND contype = 'c'
    AND conname = 'chk_tank_code_shape';
  IF conname IS NOT NULL THEN
    EXECUTE format('ALTER TABLE public.containers DROP CONSTRAINT %I', conname);
  END IF;
END $$;

-- Enforce: TANK FSH-<two alnum chars><one+ alnum chars> #<positive int>
-- Examples that pass: TANK FSH-25000B #1, TANK FSH-25ABCD #12
-- Examples that fail: TANK-25ABCD, TANK FSH-25000B #0, empty/null (null is allowed)
alter table public.containers
add constraint chk_tank_code_shape
check (
    tank_code is NULL
    or tank_code ~ '^TANK FSH-[0-9A-Z]{2}[0-9A-Z]+ #[1-9][0-9]*$'
);

-- Keep uniqueness on codes (if present, re-use; else create)
create unique index if not exists uq_containers_tank_code
on public.containers (tank_code)
where tank_code is not NULL;

commit;
