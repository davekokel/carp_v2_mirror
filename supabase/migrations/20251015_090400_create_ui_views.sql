CREATE OR REPLACE VIEW public.v_fish_overview AS
 SELECT fish_code,
    name,
    nickname,
    line_building_stage,
    date_birth,
    genetic_background,
    created_at,
    NULLIF(array_to_string(ARRAY( SELECT (fa2.transgene_base_code || '^'::text) || fa2.allele_number::text
           FROM fish_transgene_alleles fa2
          WHERE fa2.fish_id = f.id
          ORDER BY fa2.transgene_base_code, fa2.allele_number), '; '::text), ''::text) AS genotype_text,
    date_part('day'::text, now() - date_birth::timestamp with time zone)::integer AS age_days
   FROM fish f
  ORDER BY created_at DESC;
;

CREATE OR REPLACE VIEW public.v_cross_concepts_overview AS
 SELECT cp.clutch_code AS conceptual_cross_code,
    cp.clutch_name AS name,
    cp.clutch_nickname AS nickname,
    hum.mom_tank_label AS mom_code,
    hum.dad_tank_label AS dad_code,
    hum.mom_tank_label AS mom_code_tank,
    hum.dad_tank_label AS dad_code_tank,
    cp.created_at
   FROM vw_clutches_concept_overview cp
     LEFT JOIN vw_clutches_overview_human hum ON hum.clutch_code = cp.clutch_code;
;
