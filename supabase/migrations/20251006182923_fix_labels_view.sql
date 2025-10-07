BEGIN;
DROP VIEW IF EXISTS public.vw_fish_overview_with_label;
CREATE VIEW public.vw_fish_overview_with_label AS
SELECT
  v.*,
  NULL::text AS transgene_base_code_filled,
  NULL::text AS allele_code_filled,
  NULL::text AS allele_name_filled
FROM public.v_fish_overview v;
COMMIT;
