BEGIN;

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
