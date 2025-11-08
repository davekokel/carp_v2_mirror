BEGIN;

INSERT INTO public.fluorescent_treatments(ft_code, ft_text)
VALUES ('FT-DEMO-01','demo: GFP + Alexa488')
ON CONFLICT (ft_code) DO UPDATE SET ft_text = EXCLUDED.ft_text;

INSERT INTO public.ft_protein_markers(ft_code, fluor_code, tag_code)
SELECT 'FT-DEMO-01','GFP',NULL
WHERE NOT EXISTS (
  SELECT 1 FROM public.ft_protein_markers
  WHERE ft_code='FT-DEMO-01' AND fluor_code='GFP' AND COALESCE(tag_code,'∅')=COALESCE(NULL,'∅')
);

INSERT INTO public.ft_dye_markers(ft_code, dye_code)
VALUES ('FT-DEMO-01','Alexa488')
ON CONFLICT (ft_code, dye_code) DO NOTHING;

DO $$
DECLARE fx uuid;
BEGIN
  SELECT id INTO fx FROM public.fish ORDER BY created_at DESC NULLS LAST LIMIT 1;
  IF fx IS NOT NULL THEN
    INSERT INTO public.join_fish_fluorescent_treatments(fish_id, ft_code)
    VALUES (fx, 'FT-DEMO-01')
    ON CONFLICT (fish_id, ft_code) DO NOTHING;
  END IF;
END$$;

COMMIT;
