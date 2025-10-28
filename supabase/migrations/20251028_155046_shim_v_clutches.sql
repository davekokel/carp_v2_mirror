BEGIN;
/* Compatibility shim for pages expecting public.v_clutches */
CREATE OR REPLACE VIEW public.v_clutches AS
SELECT
  cci.clutch_code,                    -- e.g., CI(...), CL(...)
  NULL::text        AS name,          -- page expects these; keep blank for now
  NULL::text        AS nickname,
  cci.mom_fish_code AS mom_code,
  cci.dad_fish_code AS dad_code,
  cci.created_by    AS created_by,
  cci.created_at    AS created_at
FROM public.v_cross_clutch_instances cci;
COMMIT;
