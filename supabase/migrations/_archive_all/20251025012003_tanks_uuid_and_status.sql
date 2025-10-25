begin;

-- 1) Add uuid + status to tanks (keep existing bigint tank_id)
alter table public.tanks
  add column if not exists tank_uuid uuid not null default gen_random_uuid(),
  add column if not exists status text;

update public.tanks set status='active' where status is null;

alter table public.tanks
  alter column status set default 'active';

do $$
begin
  if not exists (select 1 from pg_constraint where conname='chk_tanks_status') then
    alter table public.tanks
      add constraint chk_tanks_status check (status in ('active','new','retired','archived'));
  end if;
  if not exists (select 1 from pg_indexes where schemaname='public' and indexname='ux_tanks_tank_uuid') then
    create unique index ux_tanks_tank_uuid on public.tanks(tank_uuid);
  end if;
end $$;

-- 2) Update v_tanks to expose tank_uuid + status
create or replace view public.v_tanks as
select
  t.tank_code,
  t.fish_code,
  f.id::uuid   as fish_id,
  t.tank_uuid  as tank_uuid,
  t.status     as status,
  t.rack,
  t.position,
  t.created_at,
  t.created_by
from public.tanks t
left join public.fish f on f.fish_code = t.fish_code;

-- 3) Make autotank v2 set status='active'
create or replace function public.fn_fish_autocreate_tank_v2()
returns trigger
language plpgsql
as $$
declare
  v_code text;
  v_suffix int;
  v_created_by uuid;
begin
  v_code := new.fish_code;
  if v_code is null or v_code = '' then return new; end if;

  if not exists (select 1 from public.tanks where fish_code = v_code) then
    v_suffix := public.fn_next_tank_suffix_by_code(v_code);
    v_created_by := case when new.created_by is null or new.created_by::text='' then null else new.created_by::uuid end;
    insert into public.tanks (tank_code, fish_code, status, rack, position, created_at, created_by)
    values ('TANK('||v_code||')#'||v_suffix, v_code, 'active', null, null, now(), v_created_by);
  end if;
  return new;
end $$;

drop trigger if exists trg_fish_autotank on public.fish;
create trigger trg_fish_autotank
after insert on public.fish
for each row execute function public.fn_fish_autocreate_tank_v2();

commit;
