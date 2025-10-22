DROP VIEW IF EXISTS public.v_cross_concepts_overview CASCADE;
CREATE VIEW public.v_cross_concepts_overview AS
SELECT
  v.clutch_code::text                  AS conceptual_cross_code,
  v.clutch_code::text                  AS clutch_code,
  COALESCE(v.clutch_name,'')::text     AS name,
  COALESCE(v.clutch_nickname,'')::text AS nickname,
  COALESCE(pc.mom_code,'')::text       AS mom_code,
  COALESCE(pc.dad_code,'')::text       AS dad_code,
  COALESCE(cm.tank_code,'')::text      AS mom_code_tank,
  COALESCE(cd.tank_code,'')::text      AS dad_code_tank,
  COALESCE(v.n_treatments,0)::int      AS n_treatments,
  COALESCE(v.created_by,'')::text      AS created_by,
  v.created_at::timestamptz            AS created_at
FROM public.v_planned_clutches_overview v
LEFT JOIN public.planned_crosses pc
  ON pc.cross_code = v.clutch_code
LEFT JOIN public.containers cm
  ON cm.id_uuid = pc.mother_tank_id
LEFT JOIN public.containers cd
  ON cd.id_uuid = pc.father_tank_id;
