BEGIN;

-- Add mother/father tank columns if they don't exist yet
ALTER TABLE public.tank_pairs
ADD COLUMN IF NOT EXISTS mother_tank_id uuid,
ADD COLUMN IF NOT EXISTS father_tank_id uuid;

-- Add FKs to tanks.id
ALTER TABLE public.tank_pairs
ADD CONSTRAINT fk_tank_pairs_mother_tank
FOREIGN KEY (mother_tank_id) REFERENCES public.tanks(id)
ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE public.tank_pairs
ADD CONSTRAINT fk_tank_pairs_father_tank
FOREIGN KEY (father_tank_id) REFERENCES public.tanks(id)
ON UPDATE CASCADE ON DELETE RESTRICT;

COMMIT;
