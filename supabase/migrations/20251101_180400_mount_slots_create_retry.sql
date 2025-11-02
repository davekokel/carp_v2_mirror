BEGIN;

-- 1) Table + indexes
CREATE TABLE IF NOT EXISTS public.mount_slots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mount_id uuid NOT NULL REFERENCES public.mounts(id) ON UPDATE CASCADE ON DELETE CASCADE,
  well text NOT NULL CHECK (well IN ('top','bottom')),
  subwell smallint NOT NULL CHECK (subwell BETWEEN 1 AND 4),
  fish_id uuid NULL REFERENCES public.fish(id) ON UPDATE CASCADE ON DELETE SET NULL,
  UNIQUE (mount_id, well, subwell)
);
CREATE INDEX IF NOT EXISTS ix_mount_slots_mount ON public.mount_slots(mount_id);
CREATE INDEX IF NOT EXISTS ix_mount_slots_fish  ON public.mount_slots(fish_id);

-- 2) Slot seeding function (called by trigger function)
CREATE OR REPLACE FUNCTION public.ensure_mount_slots(p_mount_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO public.mount_slots (mount_id, well, subwell)
  SELECT p_mount_id, x.well, x.subwell
  FROM (VALUES ('top',1),('top',2),('top',3),('top',4),
               ('bottom',1),('bottom',2),('bottom',3),('bottom',4)) AS x(well,subwell)
  ON CONFLICT DO NOTHING;
END
$$;

-- 3) Backfill slots for all existing mounts
DO $$
BEGIN
  PERFORM public.ensure_mount_slots(m.id) FROM public.mounts m;
END $$;

COMMIT;
