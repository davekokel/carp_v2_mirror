CREATE OR REPLACE VIEW public.vw_fish_overview_with_label AS
 WITH base AS (
         SELECT f.fish_code,
            f.name,
            f.nickname,
            f.line_building_stage,
            f.date_birth,
            f.genetic_background,
            f.created_by,
            f.created_at
           FROM fish f
        ), allele AS (
         SELECT DISTINCT ON (f2.fish_code) f2.fish_code,
            l.transgene_base_code,
            l.allele_number,
            ta.allele_nickname
           FROM fish_transgene_alleles l
             JOIN fish f2 ON f2.id = l.fish_id
             LEFT JOIN transgene_alleles ta ON ta.transgene_base_code = l.transgene_base_code AND ta.allele_number = l.allele_number
          ORDER BY f2.fish_code, l.transgene_base_code, l.allele_number
        ), batch AS (
         SELECT DISTINCT ON (f3.fish_code) f3.fish_code,
            m.seed_batch_id
           FROM fish_seed_batches_map m
             JOIN fish f3 ON f3.id = m.fish_id
          ORDER BY f3.fish_code, m.logged_at DESC NULLS LAST, m.created_at DESC NULLS LAST
        )
 SELECT b.fish_code,
    b.name,
    b.nickname,
    b.line_building_stage,
    b.date_birth,
    b.genetic_background,
    b.created_by,
    b.created_at,
    a.transgene_base_code AS transgene_base_code_filled,
    a.allele_number::text AS allele_code_filled,
    a.allele_nickname AS allele_name_filled,
    batch.seed_batch_id,
    batch.seed_batch_id AS batch_label,
    COALESCE(b.nickname, ''::text) AS nickname_print,
    COALESCE(b.genetic_background, ''::text) AS genetic_background_print,
    COALESCE(b.line_building_stage, ''::text) AS line_building_stage_print,
    COALESCE(to_char(b.date_birth::timestamp with time zone, 'YYYY-MM-DD'::text), ''::text) AS date_birth_print,
        CASE
            WHEN a.transgene_base_code IS NULL THEN ''::text
            WHEN a.allele_number IS NOT NULL THEN (a.transgene_base_code || '-'::text) || a.allele_number::text
            WHEN a.allele_nickname IS NOT NULL THEN (a.transgene_base_code || ' '::text) || a.allele_nickname
            ELSE a.transgene_base_code
        END AS genotype_print,
        CASE
            WHEN b.date_birth IS NOT NULL THEN CURRENT_DATE - b.date_birth
            ELSE NULL::integer
        END AS age_days,
        CASE
            WHEN b.date_birth IS NOT NULL THEN (CURRENT_DATE - b.date_birth) / 7
            ELSE NULL::integer
        END AS age_weeks,
    COALESCE(b.created_by, ''::text) AS created_by_enriched,
    NULL::text AS plasmid_injections_text,
    NULL::text AS rna_injections_text
   FROM base b
     LEFT JOIN allele a USING (fish_code)
     LEFT JOIN batch USING (fish_code)
  ORDER BY b.fish_code;
;

CREATE OR REPLACE VIEW public.vw_planned_clutches_overview AS
 WITH x AS (
         SELECT cp.id AS clutch_plan_id,
            pc.id AS planned_cross_id,
            cp.clutch_code,
            cp.planned_name AS clutch_name,
            cp.planned_nickname AS clutch_nickname,
            pc.cross_date,
            cp.created_by,
            cp.created_at,
            COALESCE(cp.note, pc.note) AS note
           FROM clutch_plans cp
             LEFT JOIN planned_crosses pc ON pc.clutch_id = cp.id
        ), tx AS (
         SELECT t.clutch_id AS clutch_plan_id,
            count(*)::integer AS n_treatments
           FROM clutch_plan_treatments t
          GROUP BY t.clutch_id
        )
 SELECT x.clutch_plan_id,
    x.planned_cross_id,
    x.clutch_code,
    x.clutch_name,
    x.clutch_nickname,
    x.cross_date,
    x.created_by,
    x.created_at,
    x.note,
    COALESCE(tx.n_treatments, 0) AS n_treatments
   FROM x
     LEFT JOIN tx ON tx.clutch_plan_id = x.clutch_plan_id
  ORDER BY (COALESCE(x.cross_date::timestamp with time zone, x.created_at)) DESC NULLS LAST;
;

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

