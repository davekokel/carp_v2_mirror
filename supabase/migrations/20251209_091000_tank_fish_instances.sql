BEGIN;

CREATE TABLE IF NOT EXISTS public.tank_fish_instances (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tank_id uuid NOT NULL REFERENCES public.tanks(id) ON UPDATE CASCADE ON DELETE CASCADE,
  fish_instance_id uuid NOT NULL REFERENCES public.fish_instances_v10(id) ON UPDATE CASCADE ON DELETE RESTRICT
);

ALTER TABLE public.tank_fish_instances
  ADD CONSTRAINT tank_fish_instances_tank_fish_unique
  UNIQUE (tank_id, fish_instance_id);

CREATE INDEX IF NOT EXISTS idx_tank_fish_instances_tank_id
  ON public.tank_fish_instances (tank_id);

CREATE INDEX IF NOT EXISTS idx_tank_fish_instances_fish_instance_id
  ON public.tank_fish_instances (fish_instance_id);

COMMENT ON TABLE public.tank_fish_instances IS
  'Join table linking tanks to fish instances, allowing multiple fish per tank.';

COMMENT ON COLUMN public.tank_fish_instances.tank_id IS
  'FK to public.tanks(id): the physical tank.';

COMMENT ON COLUMN public.tank_fish_instances.fish_instance_id IS
  'FK to public.fish_instances_v10(id): an occupant of this tank.';

COMMIT;
