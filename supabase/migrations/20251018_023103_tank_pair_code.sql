-- 1) sequence for the numeric suffix (per year is nice-to-have; we'll encode year in the code)
create sequence if not exists public.seq_tank_pair_code;

-- 2) generator function: TP-YY-NNNN
create or replace function public.gen_tank_pair_code() returns text
language plpgsql as $$
declare
  yy text := to_char(current_date, 'YY');
  n bigint;
begin
  n := nextval('public.seq_tank_pair_code');
  return format('TP-%s-%04s', yy, n::text);
end$$;

-- 3) add column + backfill + constraints
alter table public.tank_pairs
add column if not exists tank_pair_code text;

update public.tank_pairs
set tank_pair_code = public.gen_tank_pair_code()
where tank_pair_code is null;

alter table public.tank_pairs
alter column tank_pair_code set not null;

create unique index if not exists uq_tank_pairs_code on public.tank_pairs (tank_pair_code);

-- 4) trigger to auto-mint on insert if not supplied
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

-- 5) update the overview view to include the code column
create or replace view public.v_tank_pairs_overview as
select
    tp.id,
    tp.tank_pair_code,                      -- ← new
    tp.concept_id,
    tp.status,
    tp.created_by,
    tp.created_at,
    fp.id as fish_pair_id,
    mf.fish_code as mom_fish_code,
    df.fish_code as dad_fish_code,
    tp.mother_tank_id,
    mt.tank_code as mom_tank_code,
    tp.father_tank_id,
    dt.tank_code as dad_tank_code,
    coalesce(cp.clutch_code, cp.id::text) as clutch_code
from public.tank_pairs AS tp
inner join public.fish_pairs AS fp on tp.fish_pair_id = fp.id
inner join public.fish AS mf on fp.mom_fish_id = mf.id
inner join public.fish AS df on fp.dad_fish_id = df.id
left join public.clutch_plans AS cp on tp.concept_id = cp.id
inner join public.containers AS mt on tp.mother_tank_id = mt.id
inner join public.containers AS dt on tp.father_tank_id = dt.id;
