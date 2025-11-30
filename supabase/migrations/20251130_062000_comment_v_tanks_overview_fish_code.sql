BEGIN;

COMMENT ON COLUMN public.v_tanks_overview.fish_code IS
  'LINE instance code (fish_instances_v10.line_instance_code); used to join tanks to instances.';

COMMIT;
