-- Ensure planned_crosses has the fields we need (add-if-missing, non-destructive)
alter table public.planned_crosses
  add column if not exists cross_code        text,         -- concept code (unique)
  add column if not exists name              text,
  add column if not exists nickname          text,
  add column if not exists mom_code          text,
  add column if not exists dad_code          text,
  add column if not exists mother_tank_id    uuid,
  add column if not exists father_tank_id    uuid,
  add column if not exists planned_for       date,
  add column if not exists status            text,         -- keep simple; or create an enum if you prefer
  add column if not exists notes             text,
  add column if not exists created_by        text,
  add column if not exists created_at        timestamptz default now(),
  add column if not exists updated_at        timestamptz;

-- unique concept code key (idempotent)
DO $$
BEGIN
  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and indexname='ux_planned_crosses_cross_code'
  ) then
    execute 'create unique index ux_planned_crosses_cross_code on public.planned_crosses (cross_code)';
  end if;
end
$$ LANGUAGE plpgsql;
DO $$
BEGIN
  EXECUTE 'ALTER TABLE public.planned_crosses ENABLE ROW LEVEL SECURITY';

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='public' AND tablename='planned_crosses'
      AND policyname='app_rw_select_planned_crosses'
  ) THEN
    EXECUTE 'CREATE POLICY app_rw_select_planned_crosses ON public.planned_crosses FOR SELECT TO app_rw USING (true)';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='public' AND tablename='planned_crosses'
      AND policyname='app_rw_insert_planned_crosses'
  ) THEN
    EXECUTE 'CREATE POLICY app_rw_insert_planned_crosses ON public.planned_crosses FOR INSERT TO app_rw WITH CHECK (true)';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='public' AND tablename='planned_crosses'
      AND policyname='app_rw_update_planned_crosses'
  ) THEN
    EXECUTE 'CREATE POLICY app_rw_update_planned_crosses ON public.planned_crosses FOR UPDATE TO app_rw USING (true) WITH CHECK (true)';
  END IF;
END;
$$ LANGUAGE plpgsql;

-- AUTHORITATIVE view for the concept grid (pull planned values + live-tank fallback)
create or replace view public.v_cross_concepts_overview as
select
  v.clutch_code::text                      as conceptual_cross_code, -- matches deploy’s “cross”
  v.clutch_code::text                      as clutch_code,           -- kept for convenience
  coalesce(v.clutch_name,'')::text         as name,
  coalesce(v.clutch_nickname,'')::text     as nickname,
  coalesce(pc.mom_code,'')::text           as mom_code,
  coalesce(pc.dad_code,'')::text           as dad_code,

  -- LIVE mom tank via memberships if mother_tank_id is null
  coalesce(
    (select c.tank_code
       from public.containers c
       where c.id_uuid = pc.mother_tank_id),
    (select c2.tank_code
       from public.fish f2
       join public.fish_tank_memberships m2 on m2.fish_id=f2.id and m2.left_at is null
       join public.containers c2 on c2.id_uuid=m2.container_id and c2.status in ('active','new_tank')
      where f2.fish_code = pc.mom_code
      order by coalesce(c2.activated_at, c2.created_at) desc nulls last
      limit 1),
    ''
  )::text as mom_code_tank,

  -- LIVE dad tank via memberships if father_tank_id is null
  coalesce(
    (select c.tank_code
       from public.containers c
       where c.id_uuid = pc.father_tank_id),
    (select c2.tank_code
       from public.fish f2
       join public.fish_tank_memberships m2 on m2.fish_id=f2.id and m2.left_at is null
       join public.containers c2 on c2.id_uuid=m2.container_id and c2.status in ('active','new_tank')
      where f2.fish_code = pc.dad_code
      order by coalesce(c2.activated_at, c2.created_at) desc nulls last
      limit 1),
    ''
  )::text as dad_code_tank,

  coalesce(v.n_treatments,0)::int          as n_treatments,
  coalesce(v.created_by,'')::text           as created_by,
  v.created_at::timestamptz                as created_at
from public.vw_planned_clutches_overview v
left join public.planned_crosses pc
  on pc.cross_code = v.clutch_code;
