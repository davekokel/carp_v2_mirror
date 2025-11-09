BEGIN;

WITH src AS (
  SELECT tf.id AS ft_id, d.id AS dye_id
  FROM public.ft_dyes ftd
  JOIN public.treatments_fluorescent tf ON tf.ft_code = ftd.ft_code
  JOIN public.dyes d ON d.dye_code = ftd.dye_code
)
INSERT INTO public.join_ft_dyes(ft_id, dye_id)
SELECT s.ft_id, s.dye_id
FROM src s
LEFT JOIN public.join_ft_dyes j USING (ft_id, dye_id)
WHERE j.ft_id IS NULL;

WITH rp AS (
  SELECT DISTINCT f2.id AS ft_id, fu.id AS fusion_id
  FROM public.ft_proteins ftp
  JOIN public.treatments_fluorescent f2 ON f2.ft_code = ftp.ft_code
  JOIN public.fluors  fl ON fl.fluor_code = ftp.fluor_code
  JOIN public.tags    tg ON tg.tag_code   = ftp.tag_code
  JOIN public.fusions fu ON fu.fluor_id = fl.id AND fu.tag_id = tg.id
)
INSERT INTO public.join_ft_fusions(ft_id, fusion_id)
SELECT rp.ft_id, rp.fusion_id
FROM rp
LEFT JOIN public.join_ft_fusions j USING (ft_id, fusion_id)
WHERE j.ft_id IS NULL;

COMMIT;
