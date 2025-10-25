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
  select 'FSH-' || to_char(current_date,'YY') || public._to_base36(nextval('public.fish_code_seq'), 4)
$$;

alter table public.fish
  add constraint if not exists uq_fish_fish_code unique (fish_code);

create or replace function public.fish_before_insert_code()
returns trigger
language plpgsql
as $$
begin
  if new.fish_code is null or btrim(new.fish_code) = '' then
    new.fish_code := public.make_fish_code_compact();
  end if;
  return new;
end
$$;

drop trigger if exists trg_fish_before_insert_code on public.fish;

create trigger trg_fish_before_insert_code
before insert on public.fish
for each row
execute function public.fish_before_insert_code();

COMMIT;
