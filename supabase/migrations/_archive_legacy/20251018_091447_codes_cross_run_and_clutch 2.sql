-- 1) Columns
alter table public.cross_instances add column if not exists run_number int;
alter table public.cross_instances add column if not exists cross_run_code text;
alter table public.clutches add column if not exists clutch_instance_code text;

-- 2) Backfill run_number
with ranked as (
    select
        id,
        row_number() over (
            partition by tank_pair_id
            order by cross_date nulls last, created_at nulls last, id
        ) as rn
    from public.cross_instances
)

update public.cross_instances ci
set run_number = r.rn
from ranked AS r
where
    ci.id = r.id
    and (ci.run_number is null or ci.run_number <> r.rn);

-- 3) Backfill cross_run_code from tank_pairs + run_number
update public.cross_instances ci
set cross_run_code = 'CR-' || tp.tank_pair_code || '-' || ci.run_number::text
from public.tank_pairs AS tp
where
    tp.id = ci.tank_pair_id
    and (ci.cross_run_code is null or ci.cross_run_code !~ '^CR-');

-- 4) Backfill clutch_instance_code from cross_run_code AS update public.clutches cl
set clutch_instance_code = 'CI-' || ci.cross_run_code
from public.cross_instances AS ci
where
    cl.cross_instance_id = ci.id
    and (cl.clutch_instance_code is null or cl.clutch_instance_code !~ '^CI-');

-- 5) Constraints (idempotency + per-pair run numbering)
do $$
begin
  if not exists (select 1 from pg_constraint  where conname='ux_cross_instances_tp_run') then
    alter table public.cross_instances add constraint ux_cross_instances_tp_run unique (tank_pair_id, run_number);
  end if;
  if not exists (select 1 from pg_constraint  where conname='ux_cross_instances_tp_date') then
    alter table public.cross_instances add constraint ux_cross_instances_tp_date unique (tank_pair_id, cross_date);
  end if;
end$$;

-- 6) Make tank_pair_code immutable
create or replace function public.trg_tank_pairs_immutable_code()
returns trigger language plpgsql as $$
begin
  if new.tank_pair_code is distinct from old.tank_pair_code AS then
    raise exception 'tank_pair_code is immutable';
  end if;
  return new;
end$$;

drop trigger if exists trg_tank_pairs_immutable_code on public.tank_pairs;
create trigger trg_tank_pairs_immutable_code
before update on public.tank_pairs
for each row execute function public.trg_tank_pairs_immutable_code();

-- 7) Cross run minting trigger
create or replace function public.trg_cross_instances_set_codes()
returns trigger language plpgsql as $$
declare tp_code text;
declare next_run int;
begin
  if new.tank_pair_id is null then
    return new;
  end if;

  select tank_pair_code into tp_code
  from public.tank_pairs  where id = new.tank_pair_id;

  if tp_code is null then
    raise exception 'tank_pair not found for %', new.tank_pair_id;
  end if;

  if new.run_number is null then
    select coalesce(max(run_number), 0) + 1
    into next_run
    from public.cross_instances  where tank_pair_id = new.tank_pair_id;
    new.run_number := next_run;
  end if;

  if new.cross_run_code is null or new.cross_run_code = '' then
    new.cross_run_code := 'CR-' || tp_code || '-' || new.run_number::text;
  end if;

  return new;
end$$;

drop trigger if exists trg_cross_instances_set_codes on public.cross_instances;
create trigger trg_cross_instances_set_codes
before insert on public.cross_instances
for each row execute function public.trg_cross_instances_set_codes();

-- 8) Clutch code minting trigger
create or replace function public.trg_clutches_set_code()
returns trigger language plpgsql as $$
declare cr text;
begin
  if new.clutch_instance_code is not null and new.clutch_instance_code <> '' then
    return new;
  end if;

  if new.cross_instance_id is null then
    return new;
  end if;

  select cross_run_code into cr
  from public.cross_instances  where id = new.cross_instance_id;

  if cr is not null then
    new.clutch_instance_code := 'CI-' || cr;
  end if;

  return new;
end$$;

drop trigger if exists trg_clutches_set_code on public.clutches;
create trigger trg_clutches_set_code
before insert on public.clutches
for each row execute function public.trg_clutches_set_code();

-- 9) Helpful indexes
create index if not exists ix_cross_instances_cross_run_code on public.cross_instances (cross_run_code);
create index if not exists ix_clutches_clutch_instance_code on public.clutches (clutch_instance_code);
