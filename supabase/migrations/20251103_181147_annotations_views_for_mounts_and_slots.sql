BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- Latest annotations (row-wise) for MOUNTS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW public.v_mount_annotations_latest AS
WITH ranked AS (
  SELECT
    m.id                        AS mount_id,
    a.id                        AS annotation_id,
    a.kind_code,
    a.label,
    a.value_type,
    ja.value_num,
    ja.value_text,
    ja.created_at,
    ROW_NUMBER() OVER (
      PARTITION BY m.id, a.id
      ORDER BY ja.created_at DESC, ja.id DESC
    ) AS rn
  FROM public.join_annotations ja
  JOIN public.annotations a
    ON a.id = ja.annotation_id
  JOIN public.mounts m
    ON lower(ja.target_type) IN ('mount')
   AND ja.target_id = m.id
)
SELECT
  mount_id,
  annotation_id,
  kind_code,
  label,
  value_type,
  value_num,
  value_text,
  created_at
FROM ranked
WHERE rn = 1;

-- JSON pivot per mount: {kind_code: value_text_or_num}
CREATE OR REPLACE VIEW public.v_mount_annotations_pivot_json AS
SELECT
  l.mount_id,
  jsonb_object_agg(
    l.kind_code,
    CASE
      WHEN l.value_type IN ('num','number','float','int','integer') THEN to_jsonb(l.value_num)
      ELSE to_jsonb(l.value_text)
    END
  ) AS annotations_json
FROM public.v_mount_annotations_latest l
GROUP BY l.mount_id;

-- ─────────────────────────────────────────────────────────────────────────────
-- Latest annotations (row-wise) for MOUNT SLOTS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW public.v_mount_slot_annotations_latest AS
WITH ranked AS (
  SELECT
    s.id                        AS mount_slot_id,
    a.id                        AS annotation_id,
    a.kind_code,
    a.label,
    a.value_type,
    ja.value_num,
    ja.value_text,
    ja.created_at,
    ROW_NUMBER() OVER (
      PARTITION BY s.id, a.id
      ORDER BY ja.created_at DESC, ja.id DESC
    ) AS rn
  FROM public.join_annotations ja
  JOIN public.annotations a
    ON a.id = ja.annotation_id
  JOIN public.mount_slots s
    ON lower(ja.target_type) IN ('mount_slot','mountslot')
   AND ja.target_id = s.id
)
SELECT
  mount_slot_id,
  annotation_id,
  kind_code,
  label,
  value_type,
  value_num,
  value_text,
  created_at
FROM ranked
WHERE rn = 1;

-- JSON pivot per mount_slot
CREATE OR REPLACE VIEW public.v_mount_slot_annotations_pivot_json AS
SELECT
  l.mount_slot_id,
  jsonb_object_agg(
    l.kind_code,
    CASE
      WHEN l.value_type IN ('num','number','float','int','integer') THEN to_jsonb(l.value_num)
      ELSE to_jsonb(l.value_text)
    END
  ) AS annotations_json
FROM public.v_mount_slot_annotations_latest l
GROUP BY l.mount_slot_id;

COMMIT;
