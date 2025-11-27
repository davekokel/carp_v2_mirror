BEGIN;

-- 1) one tank per fish instance
ALTER TABLE public.tanks
  ADD CONSTRAINT tanks_one_per_instance_unique_v11
  UNIQUE (fish_instance_id);

-- 2) unique fish_code per fish instance
ALTER TABLE public.fish_instances_v10
  ADD CONSTRAINT fish_instances_v10_fish_code_unique_v11
  UNIQUE (fish_code);

COMMIT;
