BEGIN;

CREATE OR REPLACE VIEW public.v_fish_fluorescent_markers AS
SELECT
    f.fish_code,
    ARRAY_AGG(DISTINCT jft.ft_code ORDER BY jft.ft_code) AS markers,
    ARRAY_AGG(DISTINCT ftpr.fluor_code ORDER BY ftpr.fluor_code) AS fluors,
    ARRAY_AGG(DISTINCT ftpr.tag_code   ORDER BY ftpr.tag_code)   AS tags,
    ARRAY_AGG(DISTINCT ftd.dye_code    ORDER BY ftd.dye_code)    AS dyes
FROM public.fish f
LEFT JOIN public.join_fish_fluorescent_treatments jft
       ON jft.fish_id = f.id
LEFT JOIN public.ft_proteins ftpr
       ON ftpr.ft_code = jft.ft_code
LEFT JOIN public.ft_dyes ftd
       ON ftd.ft_code = jft.ft_code
GROUP BY f.fish_code;

COMMIT;
