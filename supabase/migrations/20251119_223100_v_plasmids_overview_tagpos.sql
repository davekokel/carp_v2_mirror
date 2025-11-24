BEGIN;

DROP VIEW IF EXISTS public.v_plasmids_overview;

CREATE VIEW public.v_plasmids_overview AS
SELECT
  p.id   AS plasmid_id,
  p.code AS plasmid_code,
  0::bigint AS n_fusions
FROM public.plasmids p;

COMMIT;
