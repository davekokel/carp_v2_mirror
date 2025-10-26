CREATE VIEW public.v_fish_overview_rich AS
 WITH current_tanks AS (
         SELECT f_1.id AS fish_id,
            array_agg(DISTINCT t.tank_code ORDER BY t.tank_code) AS tank_codes,
            min(t.tank_code) AS tank_code,
            (array_agg(DISTINCT t.status ORDER BY t.status))[1] AS tank_status,
            (array_agg(DISTINCT t.rack ORDER BY t.rack))[1] AS tank_rack,
            (array_agg(DISTINCT t."position" ORDER BY t."position"))[1] AS tank_position
           FROM (public.fish f_1
             LEFT JOIN public.tanks t ON ((t.fish_code = f_1.fish_code)))
          GROUP BY f_1.id
        ), geno_rows AS (
         SELECT DISTINCT fta.fish_id,
            fta.transgene_base_code,
            fta.allele_number,
            ((('Tg('::text || fta.transgene_base_code) || ')'::text) || COALESCE(ta.allele_name, ta.allele_nickname, ('#'::text || (fta.allele_number)::text))) AS transgene_pretty
           FROM (public.fish_transgene_alleles fta
             LEFT JOIN public.transgene_alleles ta ON (((ta.transgene_base_code = fta.transgene_base_code) AND (ta.allele_number = fta.allele_number))))
        ), geno AS (
         SELECT r.fish_id,
            min(r.transgene_base_code) AS transgene_base_code,
            array_agg(r.transgene_base_code ORDER BY r.transgene_base_code) AS transgene_base_codes,
            array_agg(r.allele_number ORDER BY r.allele_number) AS allele_number_list,
            array_agg(((r.transgene_base_code || '-'::text) || lpad((r.allele_number)::text, 2, '0'::text)) ORDER BY r.transgene_base_code, r.allele_number) AS allele_code_list,
            string_agg(r.transgene_pretty, '; '::text ORDER BY r.transgene_base_code, r.allele_number) AS transgene_pretty_name,
            string_agg(r.transgene_pretty, '; '::text ORDER BY r.transgene_base_code, r.allele_number) AS genotype_rollup
           FROM geno_rows r
          GROUP BY r.fish_id
        ), counts AS (
         SELECT vf.fish_code,
            COALESCE(vf.n_tanks, 0) AS n_living_tanks
           FROM public.v_fish vf
        )
 SELECT f.id,
    f.fish_code,
    COALESCE(f.name, ''::text) AS fish_name,
    COALESCE(f.nickname, ''::text) AS fish_nickname,
    COALESCE(f.genetic_background, ''::text) AS genetic_background,
    COALESCE(f.line_building_stage, ''::text) AS line_building_stage,
    f.date_birth,
    f.created_at,
    f.created_by,
    COALESCE(cnt.n_living_tanks, 0) AS n_living_tanks,
    COALESCE(ct.tank_code, ''::text) AS tank_code,
    COALESCE(ct.tank_codes, '{}'::text[]) AS tank_codes,
    COALESCE(ct.tank_status, ''::text) AS tank_status,
    COALESCE(ct.tank_rack, ''::text) AS tank_rack,
    COALESCE(ct.tank_position, ''::text) AS tank_position,
    COALESCE(g.transgene_base_code, ''::text) AS transgene_base_code,
    COALESCE(g.transgene_base_codes, '{}'::text[]) AS transgene_base_codes,
    COALESCE(g.allele_number_list, '{}'::integer[]) AS allele_number_list,
    COALESCE(g.allele_code_list, '{}'::text[]) AS allele_code_list,
    COALESCE(g.transgene_pretty_name, ''::text) AS transgene_pretty_name,
    COALESCE(g.genotype_rollup, ''::text) AS genotype_rollup
   FROM (((public.fish f
     LEFT JOIN counts cnt ON ((cnt.fish_code = f.fish_code)))
     LEFT JOIN current_tanks ct ON ((ct.fish_id = f.id)))
     LEFT JOIN geno g ON ((g.fish_id = f.id)));
