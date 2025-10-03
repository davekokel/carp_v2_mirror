-- View: recent crosses with parent fish_codes and offspring list
CREATE OR REPLACE VIEW public.v_recent_crosses AS
SELECT
  c.id_uuid        AS cross_id,
  c.crossed_at,
  mom.fish_code    AS mom_code,
  dad.fish_code    AS dad_code,
  COUNT(f.id_uuid) AS offspring_count,
  ARRAY_REMOVE(ARRAY_AGG(f.fish_code ORDER BY f.created_at DESC), NULL) AS offspring_codes
FROM public.crosses c
JOIN public.fish mom ON mom.id_uuid = c.mom_id
JOIN public.fish dad ON dad.id_uuid = c.dad_id
LEFT JOIN public.fish f ON f.cross_id = c.id_uuid
GROUP BY c.id_uuid, c.crossed_at, mom.fish_code, dad.fish_code;
