BEGIN;

-- For now, do not change the type of plasmids.construct_type.
-- Just ensure v_plasmids_overview exists in a simple, consistent form.

DROP VIEW IF EXISTS public.v_plasmids_overview;

CREATE VIEW public.v_plasmids_overview AS
SELECT
  p.id            AS plasmid_id,
  p.code          AS plasmid_code,
  p.construct_type,
  0::bigint       AS n_fusions
FROM public.plasmids p;

COMMIT;
