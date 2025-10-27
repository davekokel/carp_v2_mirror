-- Canonical v_fish_rich: include fish_uuid for downstream joins.
-- Use OR REPLACE to avoid breaking dependent views.
CREATE OR REPLACE VIEW public.v_fish_rich AS
SELECT
  f.fish_uuid::uuid AS fish_uuid,
  f.fish_code::text AS fish_code,
  /* keep a placeholder; you can swap to a real join later */
  NULL::text        AS genotype_text
FROM public.fish f;
