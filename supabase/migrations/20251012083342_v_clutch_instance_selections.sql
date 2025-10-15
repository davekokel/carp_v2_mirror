-- Alias view for readability: selections made on a run (distinct rows)
create or replace view public.v_clutch_instance_selections as
select
  id_uuid              as selection_id,
  cross_instance_id,
  created_at           as selection_created_at,
  annotated_at         as selection_annotated_at,
  red_intensity,
  green_intensity,
  notes,
  annotated_by,
  label
from public.clutch_instances;

-- Helpful indexes on the underlying table (idempotent)
DO $$
BEGIN
  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and tablename='clutch_instances' and indexname='ix_ci_cross_instance_id'
  ) then
    create index ix_ci_cross_instance_id on public.clutch_instances(cross_instance_id);
  end if;

  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and tablename='clutch_instances' and indexname='ix_ci_created_at'
  ) then
    create index ix_ci_created_at on public.clutch_instances(created_at);
  end if;
end
$$ LANGUAGE plpgsql;
