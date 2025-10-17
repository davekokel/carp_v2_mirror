BEGIN;

create index if not exists ix_planned_crosses_cross_id on public.planned_crosses(cross_id);
create index if not exists ix_cross_instances_cross_id on public.cross_instances(cross_id);
create index if not exists ix_clutch_instances_cross_instance_id on public.clutch_instances(cross_instance_id);

update public.planned_crosses pc
set cross_id = x.id
from public.crosses x
where pc.cross_id is null
  and upper(trim(x.mother_code)) = upper(trim(pc.mom_code))
  and upper(trim(x.father_code)) = upper(trim(pc.dad_code));

with missing as (
  select distinct pc.mom_code, pc.dad_code
  from public.planned_crosses pc
  left join public.crosses x
    on upper(trim(x.mother_code)) = upper(trim(pc.mom_code))
   and upper(trim(x.father_code)) = upper(trim(pc.dad_code))
  where pc.cross_id is null and x.id is null
),
ins as (
  insert into public.crosses (mother_code, father_code, created_by, cross_nickname)
  select m.mom_code, m.dad_code, 'system', null
  from missing m
  returning id, mother_code, father_code
)
update public.planned_crosses pc
set cross_id = i.id
from ins i
where pc.cross_id is null
  and upper(trim(i.mother_code)) = upper(trim(pc.mom_code))
  and upper(trim(i.father_code)) = upper(trim(pc.dad_code));

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.planned_crosses'::regclass
      and conname = 'fk_planned_crosses_cross'
  ) then
    alter table public.planned_crosses
      add constraint fk_planned_crosses_cross
      foreign key (cross_id) references public.crosses(id)
      on delete restrict
      deferrable initially deferred;
  end if;
end$$;

alter table public.planned_crosses
  alter column cross_id set not null;

do $$
declare
  n_ci int;
  n_cl int;
begin
  select count(*) into n_ci from public.cross_instances where cross_id is null;
  select count(*) into n_cl from public.clutch_instances where cross_instance_id is null;
  if n_ci > 0 then
    raise exception 'cross_instances.cross_id has % NULL row(s). Backfill or delete before enforcing FK.', n_ci
      using errcode = '23514';
  end if;
  if n_cl > 0 then
    raise exception 'clutch_instances.cross_instance_id has % NULL row(s). Backfill or delete before enforcing FK.', n_cl
      using errcode = '23514';
  end if;
end$$;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.cross_instances'::regclass
      and conname = 'fk_cross_instances_cross'
  ) then
    alter table public.cross_instances
      add constraint fk_cross_instances_cross
      foreign key (cross_id) references public.crosses(id)
      on delete restrict
      deferrable initially deferred;
  end if;
end$$;

alter table public.cross_instances
  alter column cross_id set not null;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.clutch_instances'::regclass
      and conname = 'fk_clutch_instances_cross_instance'
  ) then
    alter table public.clutch_instances
      add constraint fk_clutch_instances_cross_instance
      foreign key (cross_instance_id) references public.cross_instances(id)
      on delete restrict
      deferrable initially deferred;
  end if;
end$$;

alter table public.clutch_instances
  alter column cross_instance_id set not null;

do $$
begin
  if not exists (select 1 from pg_type where typname = 'clutch_plan_status') then
    create type clutch_plan_status as enum ('draft','ready','scheduled','closed');
  end if;
end$$;

alter table public.clutch_plans
  add column if not exists status clutch_plan_status not null default 'draft';

create or replace function public.trg_cp_require_planned_crosses()
returns trigger
language plpgsql
as $$
declare
  v_has int;
begin
  if (TG_OP = 'UPDATE') and (OLD.status = 'draft') and (NEW.status <> 'draft') then
    select count(*) into v_has
    from public.planned_crosses pc
    where pc.clutch_id = NEW.id
      and pc.cross_id is not null;
    if coalesce(v_has,0) = 0 then
      raise exception 'Cannot set status %: no planned_crosses with cross_id for clutch_plan %',
        NEW.status, NEW.clutch_code
        using errcode = '23514';
    end if;
  end if;
  return NEW;
end
$$;

drop trigger if exists cp_require_planned_crosses on public.clutch_plans;
create trigger cp_require_planned_crosses
before update on public.clutch_plans
for each row
execute function public.trg_cp_require_planned_crosses();

COMMIT;
