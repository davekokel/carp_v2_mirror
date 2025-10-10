BEGIN;
ALTER TABLE public.planned_crosses
  ADD COLUMN IF NOT EXISTS mother_tank_id uuid REFERENCES public.containers(id_uuid),
  ADD COLUMN IF NOT EXISTS father_tank_id uuid REFERENCES public.containers(id_uuid);
COMMIT;
