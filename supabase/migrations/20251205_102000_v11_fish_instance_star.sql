BEGIN;

DROP VIEW IF EXISTS public.v11_fish_instance_star CASCADE;

CREATE VIEW public.v11_fish_instance_star AS
SELECT
    fi.id                     AS fish_instance_id,
    fi.fish_code,
    fi.line_instance_code,
    fi.line_id,
    fl.line_code,
    fl.nickname               AS line_nickname,
    fl.genetic_background,
    fi.genotype_v11_id,

    g.genotype_code,
    g.genotype_pretty,
    g.genotype_basecodes,

    split_part(g.genotype_basecodes, '||', 1) AS genotype_basecode_code,

    fg.group_code             AS fish_group_code
FROM public.fish_instances_v10 fi
LEFT JOIN public.fish_lines fl
  ON fl.id = fi.line_id
LEFT JOIN public.genotypes_v11 g
  ON g.id = fi.genotype_v11_id
LEFT JOIN public.fish_groups fg
  ON fg.genotype_key = g.genotype_code;

COMMIT;
