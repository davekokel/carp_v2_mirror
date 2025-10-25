-- 1) Fix generator to zero-pad (no spaces)
create or replace function public.gen_tank_pair_code() returns text
language plpgsql as $$
declare
  yy text := to_char(current_date, 'YY');
  n  bigint := nextval('public.seq_tank_pair_code');
begin
  return 'TP-' || yy || '-' || to_char(n, 'FM0000');
end$$;

-- 2) Backfill any existing codes that contain spaces in the numeric part
with parts as (
    select
        id,
        tank_pair_code,     -- e.g. '25-'
        substring(tank_pair_code from '^TP-(\d{2})-') as yydash,  -- digits at end
        regexp_replace(tank_pair_code, '.*?(\d+)$', '\1') as suffix
    from public.tank_pairs  where tank_pair_code ~ '\s' or tank_pair_code ~ 'TP-\d{2}-\d{1,3}$'
)

update public.tank_pairs tp
set
    tank_pair_code = 'TP-'
    || trim(trailing '-' from coalesce(parts.yydash, '')) || '-'
    || lpad(coalesce(parts.suffix, '0'), 4, '0')
from parts  where tp.id = parts.id;

-- 3) Keep trigger in place (no change needed). Just ensure it's present.
create or replace function public.trg_tank_pairs_set_code() returns trigger
language plpgsql as $$
begin
  if new.tank_pair_code is null or new.tank_pair_code = '' then
    new.tank_pair_code := public.gen_tank_pair_code();
  end if;
  return new;
end$$;

drop trigger if exists trg_tank_pairs_set_code on public.tank_pairs;
create trigger trg_tank_pairs_set_code
before insert on public.tank_pairs
for each row execute function public.trg_tank_pairs_set_code();
