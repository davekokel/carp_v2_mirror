BEGIN;

CREATE SEQUENCE IF NOT EXISTS public.tank_code_seq START 1;

CREATE OR REPLACE FUNCTION public._to_base36(n bigint, pad int)
RETURNS text LANGUAGE plpgsql IMMUTABLE AS $$
declare
  chars constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  x bigint := n;
  out text := '';
  d int;
begin
  if x < 0 then
    raise exception 'negative not allowed';
  end if;
  if x = 0 then
    out := '0';
  else
    while x > 0 loop
      d := (x % 36);
      out := substr(chars, d+1, 1) || out;
      x := x / 36;
    end loop;
  end if;
  if length(out) < pad then
    out := lpad(out, pad, '0');
  end if;
  return out;
end
$$;

CREATE OR REPLACE FUNCTION public.make_tank_code_compact()
RETURNS text
LANGUAGE sql
AS $$
  select 'TANK-' || to_char(current_date,'YY') || public._to_base36(nextval('public.tank_code_seq'), 4)
$$;
DO $$
begin
  if to_regclass('public.tanks') is not null
     and exists (
       select 1
       from information_schema.columns
       where table_schema='public' and table_name='tanks' and column_name='tank_code'
     )
  then
    if not exists (
      select 1 from pg_constraint
      where conname='uq_tanks_tank_code' and conrelid='public.tanks'::regclass
    ) then
      alter table public.tanks add constraint uq_tanks_tank_code unique (tank_code);
    end if;

    create or replace function public.tanks_before_insert_code()
    returns trigger
    language plpgsql
    as $f$
    begin
      if new.tank_code is null or btrim(new.tank_code) = '' then
        new.tank_code := public.make_tank_code_compact();
      end if;
      return new;
    end
    $f$;

    drop trigger if exists trg_tanks_before_insert_code on public.tanks;

    create trigger trg_tanks_before_insert_code
    before insert on public.tanks
    for each row
    execute function public.tanks_before_insert_code();
  else
    raise notice 'public.tanks.tank_code not found; created function/sequence only.';
  end if;
end$$;

COMMIT;
