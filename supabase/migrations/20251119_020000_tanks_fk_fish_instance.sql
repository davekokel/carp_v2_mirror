BEGIN;

ALTER TABLE public.tanks
ADD CONSTRAINT fk_tanks_fish_instance
FOREIGN KEY (fish_id)
REFERENCES public.fish_instance(id)
ON UPDATE CASCADE
ON DELETE RESTRICT
NOT VALID;

-- optional but recommended to validate existing data
ALTER TABLE public.tanks
VALIDATE CONSTRAINT fk_tanks_fish_instance;

COMMIT;
