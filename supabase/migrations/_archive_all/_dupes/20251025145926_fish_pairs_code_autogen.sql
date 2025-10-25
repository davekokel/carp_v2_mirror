begin;

-- 1) Base36 helper (idempotent / harmless if already present)
create or replace function public.to_base36(n bigint)
returns text
language plpgsql
immutable
as $$
declare
  v bigint := n;
  s text := '';
  a constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  pos integer;
begin
  if v < 0 then
    raise exception 'to_base36 expects nonnegative';
  end if;
  if v = 0 then
    return '0';
  end if;
  while v > 0 loop
    pos := (v % 36)::int + 1;
    s := substr(a, pos, 1) || s;
    v := v / 36;
  end loop;
  return s;
end
$$;

-- 2) Sequence for FP codes (idempotent)
create sequence if not exists public.fish_pairs_code_seq start 1;

-- 3) Small wrapper to format FP-{B36}
create or replace function public.make_fp_code(v bigint)
returns text
language sql
immutable
as $$
  select 'FP-' || lpad(public.to_base36(v), 5, '0')
$$;

-- 4) BEFORE INSERT trigger to mint codes when fish_pair_code is null
create or replace function public.fish_pairs_code_autogen()
returns trigger
language plpgsql
as $$
declare
  candidate text;
begin
  if coalesce(new.fish_pair_code, '') = '' then
    candidate := public.make_fp_code(nextval('public.fish_pairs_code_seq'));
    new.fish_pair_code := candidate;
  end if;
  return new;
end
$$;

drop trigger if exists trg_fish_pairs_code_autogen on public.fish_pairs;
create trigger trg_fish_pairs_code_autogen
before insert on public.fish_pairs
for each row
execute function public.fish_pairs_code_autogen();

commit;
