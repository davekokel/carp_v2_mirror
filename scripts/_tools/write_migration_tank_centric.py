from datetime import datetime
from pathlib import Path

sql = """
begin;

alter table public.cross_instances
  add column if not exists tank_pair_id uuid references public.tank_pairs(id);

update public.cross_instances ci
set tank_pair_id = tp.id
from public.tank_pairs tp
where tp.mother_tank_id = ci.mother_tank_id
  and tp.father_tank_id = ci.father_tank_id
  and ci.tank_pair_id is null;

alter table public.clutch_plans
  add column if not exists tank_pair_id uuid references public.tank_pairs(id);

update public.clutch_plans cp
set tank_pair_id = pc.tank_pair_id
from public.planned_crosses pc
where pc.clutch_id = cp.id
  and cp.tank_pair_id is null;

create unique index if not exists cross_instances_pair_date_uniq
  on public.cross_instances(tank_pair_id, cross_date);

create or replace view public.v_crosses as
with runs as (
  select
    ci.tank_pair_id,
    tp.tank_pair_code,
    tp.mother_tank_id,
    tp.father_tank_id,
    vtp.mom_fish_code as mom_code,
    vtp.dad_fish_code as dad_code,
    count(*)::int      as n_runs,
    max(ci.cross_date) as latest_cross_date,
    min(ci.created_by) as created_by,
    min(ci.created_at) as created_at
  from public.cross_instances ci
  join public.tank_pairs tp
    on tp.id = ci.tank_pair_id
  left join public.v_tank_pairs vtp
    on vtp.mother_tank_id = tp.mother_tank_id
   and vtp.father_tank_id = tp.father_tank_id
  group by
    ci.tank_pair_id, tp.tank_pair_code, tp.mother_tank_id, tp.father_tank_id,
    vtp.mom_fish_code, vtp.dad_fish_code
),
planned_only as (
  select
    cp.tank_pair_id,
    tp.tank_pair_code,
    tp.mother_tank_id,
    tp.father_tank_id,
    vtp.mom_fish_code as mom_code,
    vtp.dad_fish_code as dad_code,
    0::int     as n_runs,
    null::date as latest_cross_date,
    cp.created_by,
    cp.created_at
  from public.clutch_plans cp
  join public.tank_pairs tp
    on tp.id = cp.tank_pair_id
  left join public.v_tank_pairs vtp
    on vtp.mother_tank_id = tp.mother_tank_id
   and vtp.father_tank_id = tp.father_tank_id
  where not exists (select 1 from runs r where r.tank_pair_id = cp.tank_pair_id)
)
select
  coalesce(r.tank_pair_id, p.tank_pair_id)           as cross_key,
  coalesce(r.tank_pair_code, p.tank_pair_code)       as cross_code,
  coalesce(r.mom_code, p.mom_code)                   as mom_code,
  coalesce(r.dad_code, p.dad_code)                   as dad_code,
  coalesce(vs.status,'draft')                        as status,
  coalesce(r.n_runs, p.n_runs)                       as n_runs,
  coalesce(r.latest_cross_date, p.latest_cross_date) as latest_cross_date,
  coalesce(r.created_by, p.created_by)               as created_by,
  coalesce(r.created_at, p.created_at)               as created_at
from runs r
full join planned_only p on p.tank_pair_id = r.tank_pair_id
left join public.v_crosses_status vs on vs.id = coalesce(r.tank_pair_id, p.tank_pair_id);

commit;
""".lstrip()

root = Path(__file__).resolve().parents[1]
outdir = root / "supabase" / "migrations"
outdir.mkdir(parents=True, exist_ok=True)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
path = outdir / f"{ts}_tank_centric_crosses.sql"
path.write_text(sql, encoding="utf-8")
print(path)
