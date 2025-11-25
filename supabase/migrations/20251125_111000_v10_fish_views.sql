BEGIN;

-- v10_fish_lines_overview:
-- one row per fish_lines.id, with genotype_pretty built from join_line_alleles.
CREATE OR REPLACE VIEW public.v10_fish_lines_overview AS
SELECT
  fl.id                  AS line_id,
  fl.line_code,
  fl.nickname,
  fl.genetic_background,
  fl.line_building_stage,
  fl.created_at,
  string_agg(
    DISTINCT 'Tg(' || c.construct_code || ')' || ta.allele_name,
    '; ' ORDER BY 'Tg(' || c.construct_code || ')' || ta.allele_name
  ) AS genotype_pretty
FROM public.fish_lines fl
LEFT JOIN public.join_line_alleles jla
  ON jla.line_id = fl.id
LEFT JOIN public.constructs c
  ON c.id = jla.construct_id
LEFT JOIN public.transgene_alleles ta
  ON ta.transgene_base_code = c.construct_code
 AND ta.allele_number       = jla.allele_number
GROUP BY fl.id;

-- v10_fish_instances_overview:
-- fish_instances_v10 joined to fish_lines + v10_fish_lines_overview.
CREATE OR REPLACE VIEW public.v10_fish_instances_overview AS
SELECT
  fi.id          AS fish_instance_id,
  fi.fish_code,
  fi.line_id,
  fi.birthday,
  fi.notes       AS fish_notes,
  fi.created_at  AS fish_created_at,
  fl.line_code,
  fl.nickname    AS line_nickname,
  fl.genetic_background,
  fl.line_building_stage,
  fl.created_at  AS line_created_at,
  v10.genotype_pretty
FROM public.fish_instances_v10 fi
JOIN public.fish_lines fl
  ON fl.id = fi.line_id
LEFT JOIN public.v10_fish_lines_overview v10
  ON v10.line_id = fl.id;

COMMIT;
