BEGIN;

create sequence if not exists public.fish_code_seq start 1;

create or replace function public._to_base36(n bigint, pad int)
returns text language plpgsql immutable as $$
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

create or replace function public.make_fish_code_compact()
returns text
language sql
as $$
  select 'FSH-' ||
         to_char(current_date, 'YY') ||
         public._to_base36(nextval('public.fish_code_seq'), 4)
$$;

-- Optional: guard to enforce uniqueness at the table
do $$
begin
  if not exists (
    select 1
    from information_schema.table_constraints
    where table_schema='public'
      and table_name='fish'
      and constraint_type='UNIQUE'
      and constraint_name='uq_fish_fish_code'
  ) then
    alter table public.fish add constraint uq_fish_fish_code unique (fish_code);
  end if;
end$$;

COMMIT;
