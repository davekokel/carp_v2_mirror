BEGIN;
DO 28762
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='container_status') THEN
    CREATE TYPE container_status AS ENUM ('planned','active','inactive','retired','unknown');
  END IF;
END$$;

DROP VIEW IF EXISTS public.v_containers_crossing_candidates;

ALTER TABLE public.containers ALTER COLUMN status DROP DEFAULT;

ALTER TABLE public.containers
  ALTER COLUMN status TYPE container_status USING
    CASE
      WHEN status::text IN ('planned','active','inactive','retired','unknown') THEN status::container_status
      ELSE 'unknown'::container_status
    END;

ALTER TABLE public.containers ALTER COLUMN status SET DEFAULT 'planned'::container_status;

CREATE OR REPLACE VIEW public.v_containers_crossing_candidates AS
SELECT id_uuid, container_type, label, status, created_by, created_at, note
FROM public.containers
WHERE container_type IN ('inventory_tank','crossing_tank','holding_tank','nursery_tank','petri_dish');

COMMIT;
