begin;

create sequence if not exists public.fish_pair_b36_seq;

create or replace function public.to_base36(n bigint)
returns text
language plpgsql
immutable
as $$
declare
  v bigint := n;
  s text := '';
  alphabet constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
begin
  if v < 0 then
    raise exception 'to_base36 expects nonnegative';
  end if;
  if v = 0 then
    return '0';
  end if;
  while v > 0 loop
    s := substr(alphabet, (v % 36) + 1, 1) || s;
    v := v / 36;
  end loop;
  return s;
end
$$;

create or replace function public.next_fish_pair_code()
returns text
language plpgsql
volatile
as $$
declare
  v bigint;
  b text;
begin
  v := nextval('public.fish_pair_b36_seq');
  b := public.to_base36(v);
  if length(b) < 5 then
    b := lpad(b, 5, '0');
  end if;
  return 'FP-' || b;
end
$$;

alter table public.fish_pairs
  alter column fish_pair_code set default public.next_fish_pair_code();

create or replace function public.trg_fish_pairs_code_b36()
returns trigger
language plpgsql
as $$
begin
  if new.fish_pair_code is null or new.fish_pair_code = '' then
    new.fish_pair_code := public.next_fish_pair_code();
  end if;
  return new;
end
$$;

drop trigger if exists trg_fish_pairs_code_b36 on public.fish_pairs;
create trigger trg_fish_pairs_code_b36
before insert on public.fish_pairs
for each row execute function public.trg_fish_pairs_code_b36();

do $$
begin
  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and indexname='uq_fish_pairs_fish_pair_code'
  ) then
    execute 'create unique index uq_fish_pairs_fish_pair_code on public.fish_pairs (fish_pair_code)';
  end if;
end
$$;

alter table public.fish_pairs
  drop constraint if exists fish_pair_code_format_chk;
alter table public.fish_pairs
  add constraint fish_pair_code_format_chk
  check (fish_pair_code ~ '^FP-[0-9A-Z]{5,}$');

update public.fish_pairs
set fish_pair_code = public.next_fish_pair_code()
where fish_pair_code is null;

commit;
