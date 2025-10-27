-- Ensure code uniqueness
create unique index if not exists uq_tank_pairs_code on public.tank_pairs (tank_pair_code);

-- Generator function: TP-YY##### with per-year rolling counter (advisory-locked)
create or replace function public.gen_tank_pair_code() returns trigger language plpgsql as $$
declare
  yy text;
  nxt int;
begin
  if new.tank_pair_code is not null then
    return new;
  end if;

  perform pg_advisory_xact_lock(88123456); -- serialize within txn

  yy := to_char(current_date, 'YY');

  select coalesce(max((regexp_match(tp.tank_pair_code, '^TP-'||yy||'(\d{5})$'))[1]::int), 0) + 1
    into nxt
  from public.tank_pairs tp
  where tp.tank_pair_code like 'TP-'||yy||'%';

  new.tank_pair_code := 'TP-'||yy||lpad(nxt::text, 5, '0');
  return new;
end
$$;

-- Trigger
drop trigger if exists trg_tank_pairs_set_code on public.tank_pairs;
create trigger trg_tank_pairs_set_code
before insert on public.tank_pairs
for each row
execute function public.gen_tank_pair_code();

-- Backfill any missing codes deterministically (ordered by created_at)
do $$
declare
  r record;
  yy text := to_char(current_date, 'YY');
  nxt int;
begin
  perform pg_advisory_xact_lock(88123456);

  select coalesce(max((regexp_match(tp.tank_pair_code, '^TP-'||yy||'(\d{5})$'))[1]::int), 0)
    into nxt
  from public.tank_pairs tp
  where tp.tank_pair_code like 'TP-'||yy||'%';

  for r in
    select id
    from public.tank_pairs
    where tank_pair_code is null
    order by created_at nulls last, id
  loop
    nxt := nxt + 1;
    update public.tank_pairs
       set tank_pair_code = 'TP-'||yy||lpad(nxt::text, 5, '0')
     where id = r.id;
  end loop;
end
$$;

-- View: keep existing column names/order; ensure fish_pair_code is populated
create or replace view public.v_tank_pairs as
select
  tp.tank_pair_code,                            -- 1
  fp.fish_pair_code,                            -- 2
  null::uuid          as mom_fish_id,           -- 3 (placeholder to preserve schema)
  null::uuid          as dad_fish_id,           -- 4
  vtm.fish_code       as mom_fish_code,         -- 5
  vtf.fish_code       as dad_fish_code,         -- 6
  vtm.tank_code       as mother_tank_code,      -- 7
  vtf.tank_code       as father_tank_code,      -- 8
  tp.created_at       as tank_pair_created_at,  -- 9
  fp.created_at       as pair_created_at        -- 10
from public.tank_pairs tp
left join public.fish_pairs fp on fp.id = tp.fish_pair_id
left join public.v_tanks vtm   on vtm.tank_uuid = tp.mother_tank_id
left join public.v_tanks vtf   on vtf.tank_uuid = tp.father_tank_id;

-- Quick guard: fail if duplicate codes (shouldn’t happen with the lock + unique index)
with dups as (
  select tank_pair_code, count(*) c from public.tank_pairs
  group by tank_pair_code having count(*) > 1
)
select case when exists(select 1 from dups) then
  raise_exception('Duplicate tank_pair_code values exist') else 1 end;