BEGIN;

DROP VIEW IF EXISTS public.v_tanks_overview;

CREATE VIEW public.v_tanks_overview AS
SELECT
  t.id::text                             AS tank_id,
  t.tank_code,
  t.status,
  fi.fish_code,
  fi.nickname                            AS fish_nickname,
  fi.instance_stage,
  fi.birthday,
  fi.genetic_background,
  fl.line_code,
  fl.nickname                            AS line_nickname,
  fl.line_building_stage,
  -- genotype-only labels (3 styles)
  fis.genotype_tg_style,
  fis.genotype_fluortag_style,
  fis.genotype_fluororganelle_style,
  -- treatment labels (3 styles; may be NULL for untreated fish)
  fis.treatment_codes,
  fis.treatment_label_tg_style,
  fis.treatment_label_fluortag_style,
  fis.treatment_label_fluororganelle_style,
  -- treatment > genotype if treated, genotype-only if untreated (3 styles)
  CASE
    WHEN fis.treatment_label_tg_style IS NOT NULL
         AND fis.treatment_label_tg_style <> ''
      THEN fis.treatment_label_tg_style || ' > ' || fis.genotype_tg_style
    ELSE fis.genotype_tg_style
  END AS treatment_or_genotype_tg_style,
  CASE
    WHEN fis.treatment_label_fluortag_style IS NOT NULL
         AND fis.treatment_label_fluortag_style <> ''
      THEN fis.treatment_label_fluortag_style || ' > ' || fis.genotype_fluortag_style
    ELSE fis.genotype_fluortag_style
  END AS treatment_or_genotype_fluortag_style,
  CASE
    WHEN fis.treatment_label_fluororganelle_style IS NOT NULL
         AND fis.treatment_label_fluororganelle_style <> ''
      THEN fis.treatment_label_fluororganelle_style || ' > ' || fis.genotype_fluororganelle_style
    ELSE fis.genotype_fluororganelle_style
  END AS treatment_or_genotype_fluororganelle_style,
  t.created_at
FROM public.tanks t
JOIN public.fish_instances_v10 fi
  ON fi.id = t.fish_instance_id
JOIN public.fish_lines fl
  ON fl.id = fi.line_id
LEFT JOIN public.v11_fish_instance_star_labels fis
  ON fis.fish_instance_id = fi.id;

COMMENT ON VIEW public.v_tanks_overview IS
'Canonical tanks overview (v11): tanks + fish + line + genotype + treatment labels, with treatment>genotype vs genotype-only in tg/fluor-tag/fluor-organelle styles.';

COMMIT;
