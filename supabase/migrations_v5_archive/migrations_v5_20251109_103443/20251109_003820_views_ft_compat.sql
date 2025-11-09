BEGIN;

CREATE OR REPLACE VIEW public.v_ft_dyes AS
SELECT tf.ft_code, d.dye_code
FROM public.join_ft_dyes j
JOIN public.treatments_fluorescent tf ON tf.id = j.ft_id
JOIN public.dyes d ON d.id = j.dye_id;

CREATE OR REPLACE VIEW public.v_ft_proteins AS
SELECT tf.ft_code, fl.fluor_code, tg.tag_code
FROM public.join_ft_fusions j
JOIN public.treatments_fluorescent tf ON tf.id = j.ft_id
JOIN public.fusions fu ON fu.id = j.fusion_id
JOIN public.fluors fl ON fl.id = fu.fluor_id
JOIN public.tags   tg ON tg.id = fu.tag_id;

COMMIT;
