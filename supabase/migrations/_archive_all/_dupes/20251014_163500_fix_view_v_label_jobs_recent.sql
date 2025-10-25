CREATE OR REPLACE VIEW public.v_labels_recent AS
SELECT
  j.id AS id_uuid,
  j.entity_type,
  j.entity_id,
  j.template,
  j.media,
  j.status,
  j.requested_by,
  j.requested_at,
  j.started_at,
  j.finished_at,
  j.num_labels,
  ((j.file_bytes IS NOT NULL) OR (j.file_url IS NOT NULL)) AS has_file
FROM public.label_jobs j
ORDER BY j.requested_at DESC;
