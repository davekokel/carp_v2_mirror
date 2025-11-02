BEGIN;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

INSERT INTO public.annotations (kind_code,label,value_type)
VALUES ('orientation','Orientation','text')
ON CONFLICT (kind_code) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.mount_slots (
  id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mount_id uuid NOT NULL REFERENCES public.mounts(id) ON UPDATE CASCADE ON DELETE CASCADE,
  well     text NOT NULL CHECK (well IN ('top','bottom')),
  subwell  smallint NOT NULL CHECK (subwell BETWEEN 1 AND 4),
  fish_id  uuid NULL,
  UNIQUE (mount_id, well, subwell)
);

CREATE INDEX IF NOT EXISTS ix_mount_slots_mount ON public.mount_slots(mount_id);
CREATE INDEX IF NOT EXISTS ix_mount_slots_fish  ON public.mount_slots(fish_id);

DO $$
DECLARE has_fish_id boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='id'
  ) INTO has_fish_id;

  BEGIN
    ALTER TABLE public.mount_slots DROP CONSTRAINT IF EXISTS mount_slots_fish_fk;
  EXCEPTION WHEN undefined_object THEN
  END;

  IF has_fish_id THEN
    EXECUTE 'ALTER TABLE public.mount_slots
             ADD CONSTRAINT mount_slots_fish_fk
             FOREIGN KEY (fish_id) REFERENCES public.fish(id)
             ON UPDATE CASCADE ON DELETE SET NULL';
  END IF;
END $$;

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

DO $$
BEGIN
  PERFORM public.ensure_mount_slots(m.id) FROM public.mounts m;
END $$;

CREATE OR REPLACE FUNCTION public.ensure_mount_slots_trg()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM public.ensure_mount_slots(NEW.id);
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_mounts_seed_slots ON public.mounts;

CREATE TRIGGER trg_mounts_seed_slots
AFTER INSERT ON public.mounts
FOR EACH ROW
EXECUTE FUNCTION public.ensure_mount_slots_trg();

CREATE OR REPLACE VIEW public.v_mount_slots AS
SELECT
  m.mount_code,
  m.id  AS mount_id,
  s.id  AS mount_slot_id,
  s.well,
  s.subwell
FROM public.mounts m
JOIN public.mount_slots s ON s.mount_id = m.id;

CREATE OR REPLACE VIEW public.v_mount_slot_annotations_pivot AS
WITH va AS (
  SELECT
    v.target_id  AS mount_slot_id,
    a.kind_code,
    v.value_num,
    v.value_text,
    v.created_at
  FROM public.v_annotations_latest v
  JOIN public.annotations a ON a.id = v.annotation_id
  WHERE v.target_type = 'mount_slot'
)
SELECT
  vms.mount_code,
  vms.mount_id,
  vms.mount_slot_id,
  vms.well,
  vms.subwell,
  MAX(CASE WHEN va.kind_code='red_intensity'   THEN va.value_num  END) AS red_intensity,
  MAX(CASE WHEN va.kind_code='green_intensity' THEN va.value_num  END) AS green_intensity,
  MAX(CASE WHEN va.kind_code='orientation'     THEN va.value_text END) AS orientation,
  MAX(CASE WHEN va.kind_code='notes'           THEN va.value_text END) AS notes,
  MAX(va.created_at) AS annotations_last_at
FROM public.v_mount_slots vms
LEFT JOIN va ON va.mount_slot_id = vms.mount_slot_id
GROUP BY vms.mount_code, vms.mount_id, vms.mount_slot_id, vms.well, vms.subwell;

COMMIT;
