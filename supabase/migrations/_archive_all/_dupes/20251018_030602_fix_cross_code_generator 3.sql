-- 1) Sequence (create if missing)
create sequence if not exists public.seq_cross_code;

-- 2) Code generator: CROSS-YY + 4+ alnum suffix (zero-padded numeric works)
--    Pattern expected by chk_cross_code_shape: '^CROSS-[0-9A-Z]{2}[0-9A-Z]{4,}$'
create or replace function public.gen_cross_code() returns text
language plpgsql as $$
declare
  yy text := to_char(current_date, 'YY');
  n  bigint := nextval('public.seq_cross_code');
begin
  -- Example: CROSS-25 + 0001  => 'CROSS-250001' (no spaces, no hyphen after year)
  return 'CROSS-' || yy || to_char(n, 'FM0000');
end$$;

-- 3) Trigger to auto-fill cross_code if NULL or invalid
create or replace function public.trg_cross_code_fill() returns trigger
language plpgsql as $$
begin
  if NEW.cross_code is null
     or NEW.cross_code !~ '^CROSS-[0-9A-Z]{2}[0-9A-Z]{4,}$' then
    NEW.cross_code := public.gen_cross_code();
  end if;
  return NEW;
end$$;

drop trigger if exists trg_cross_code_fill on public.crosses;
create trigger trg_cross_code_fill
before insert or update on public.crosses
for each row execute function public.trg_cross_code_fill();

-- 4) Backfill any existing rows with bad or space-padded codes
update public.crosses
set cross_code = public.gen_cross_code()
where
    cross_code is not null
    and cross_code !~ '^CROSS-[0-9A-Z]{2}[0-9A-Z]{4,}$';
