-- Add a linkage to the realized run (cross_instances) if not present
alter table public.clutch_instances
  add column if not exists cross_instance_id uuid;

-- Unique per run (if you want comments-only duplicates, remove this)
create unique index if not exists ux_ci_cross_instance_id
  on public.clutch_instances(cross_instance_id)
  where cross_instance_id is not null;

-- Safe FK (NOT VALID); validate later after orphan check
DO $$
BEGIN
  if not exists (select 1 from pg_constraint where conname='fk_ci_xrun') then
    alter table public.clutch_instances
      add constraint fk_ci_xrun
      foreign key (cross_instance_id) references public.cross_instances(id_uuid) not valid;
  end if;
end
$$ LANGUAGE plpgsql;
