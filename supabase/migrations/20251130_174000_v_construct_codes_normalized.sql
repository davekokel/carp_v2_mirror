BEGIN;

DROP VIEW IF EXISTS public.v_construct_codes_normalized;

CREATE VIEW public.v_construct_codes_normalized AS
SELECT
  c.id::uuid        AS construct_id,
  c.construct_code  AS construct_code,
  c.base_code       AS base_code,
  /* minimal, non-magical normalization: just expose the canonical base code */
  COALESCE(c.base_code, c.construct_code) AS code_normalized,
  ca.alias          AS alias
FROM public.constructs c
LEFT JOIN public.construct_aliases ca
  ON ca.construct_id = c.id;

COMMENT ON VIEW public.v_construct_codes_normalized IS
  'Constructs + aliases with a minimal normalized code (code_normalized = COALESCE(base_code, construct_code)) for LUTs like v10_load_fish_lines_from_fish_xlsx.';

COMMIT;
