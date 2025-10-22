-- 1) Ensure the column exists
alter table public.clutches
add column if not exists clutch_instance_code text;

-- 2) Unique index (create after backfill in case of conflicts, but it's idempotent)
create unique index if not exists uq_clutches_instance_code
on public.clutches (clutch_instance_code);

-- 3) Trigger: CI-<cross_run_code> (and add -02, -03… if multiple clutches share a run)
create or replace function public.trg_clutch_instance_code_fill() returns trigger
language plpgsql as $$
declare
  v_run  text;
  v_base text;
  v_code text;
  i      int := 1;
begin
  if new.clutch_instance_code is not null and btrim(new.clutch_instance_code) <> '' then
    return new;
  end if;

  -- Get the cross run code for this clutch's cross_instance
  select ci.cross_run_code into v_run
  from public.cross_instances AS ci
  where ci.id = new.cross_instance_id;

  -- Build the base code; if no run (shouldn't happen), use a safe fallback
  v_base := 'CI-' || coalesce(v_run, 'UNSET');

  v_code := v_base;

  -- If the base already exists, append -02, -03, ... until unique
  while exists (select 1 from public.clutches AS c where c.clutch_instance_code = v_code) loop
    i := i + 1;
    v_code := v_base || '-' || lpad(i::text, 2, '0');
  end loop;

  new.clutch_instance_code := v_code;
  return new;
end$$;

drop trigger if exists trg_clutch_instance_code_fill on public.clutches;
create trigger trg_clutch_instance_code_fill
before insert on public.clutches
for each row execute function public.trg_clutch_instance_code_fill();

-- 4) Backfill existing rows that are NULL/blank using the same logic deterministically
--    Base code per run + row_number() to add -02, -03… where needed.
with candidates as (
    select
        cl.id, 'CI-' || ci.cross_run_code as base_code,
        row_number() over (partition by cl.cross_instance_id order by cl.created_at, cl.id) as rn
    from public.clutches AS cl
    inner join public.cross_instances AS ci on cl.cross_instance_id = ci.id
    where cl.clutch_instance_code is null or btrim(cl.clutch_instance_code) = ''
),

resolved as (
    select
        id,
        case
            when rn = 1 then base_code
            else base_code || '-' || lpad(rn::text, 2, '0')
        end as code_suggested
    from candidates
)

update public.clutches cl
set clutch_instance_code = r.code_suggested
from resolved AS r
where
    cl.id = r.id
    and (cl.clutch_instance_code is null or btrim(cl.clutch_instance_code) = '');

-- 5) Enforce NOT NULL going forward
alter table public.clutches
alter column clutch_instance_code set not null;
