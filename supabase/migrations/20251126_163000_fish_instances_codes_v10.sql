BEGIN;

-- 1) rename existing fish_code -> line_instance_code
ALTER TABLE public.fish_instances_v10
  RENAME COLUMN fish_code TO line_instance_code;

-- 2) add new canonical fish_code (FSH-uuid8)
ALTER TABLE public.fish_instances_v10
  ADD COLUMN fish_code text;

-- 3) optional backfill for existing rows:
-- derive a stable-ish FSH-xxxxxxx from the old line_instance_code + created_at
UPDATE public.fish_instances_v10
SET fish_code = 'FSH-' || substr(md5(line_instance_code || COALESCE(created_at::text, now()::text)), 1, 8)
WHERE line_instance_code IS NOT NULL
  AND fish_code IS NULL;

COMMIT;
