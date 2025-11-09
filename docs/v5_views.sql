CREATE OR REPLACE VIEW public.v_clutch_instances AS  SELECT cl.id AS clutch_instance_id,
    cl.clutch_instance_code AS clutch_code,
    cl.cross_instance_id AS cross_id,
    cr.tank_pair_code,
    COALESCE(cl.created_at, cr.created_at) AS created_at
   FROM (clutch_instances cl
     JOIN crosses cr ON ((cr.id = cl.cross_instance_id)));;
CREATE OR REPLACE VIEW public.v_fish_main AS  WITH alleles AS (
         SELECT f_1.fish_code,
            jfta.transgene_base_code,
            jfta.allele_number,
            ta.allele_name,
            ta.allele_nickname
           FROM ((fish f_1
             JOIN join_fish_transgene_alleles jfta ON ((jfta.fish_id = f_1.id)))
             JOIN transgene_alleles ta ON (((ta.transgene_base_code = jfta.transgene_base_code) AND (ta.allele_number = jfta.allele_number))))
        ), pick AS (
         SELECT DISTINCT ON (a.fish_code) a.fish_code,
            a.transgene_base_code,
            a.allele_number,
            a.allele_name,
            a.allele_nickname
           FROM alleles a
          ORDER BY a.fish_code, a.allele_number DESC
        )
 SELECT f.id AS fish_id,
    f.fish_code,
    f.created_at,
    COALESCE(pick.transgene_base_code, ''::text) AS transgene_base_code,
    COALESCE(pick.allele_nickname, ''::text) AS allele_nickname,
    COALESCE(pick.allele_number, 0) AS allele_number,
    COALESCE(pick.allele_name, ''::text) AS allele_name,
    ((('Tg('::text || COALESCE(pick.transgene_base_code, ''::text)) || ')'::text) || COALESCE(pick.allele_nickname, ''::text)) AS transgene_pretty_nickname,
    ((('Tg('::text || COALESCE(pick.transgene_base_code, ''::text)) || ')'::text) || COALESCE(pick.allele_name, ''::text)) AS transgene_pretty_name
   FROM (fish f
     LEFT JOIN pick ON ((pick.fish_code = f.fish_code)));;
CREATE OR REPLACE VIEW public.v_fish_unified AS  WITH markers AS (
         SELECT f_1.fish_code,
            (((ta.transgene_base_code || '('::text) || ta.allele_name) || ')'::text) AS marker_label
           FROM ((join_fish_transgene_alleles jf
             JOIN transgene_alleles ta ON (((ta.transgene_base_code = jf.transgene_base_code) AND (ta.allele_number = jf.allele_number))))
             JOIN fish f_1 ON ((f_1.id = jf.fish_id)))
          WHERE (NULLIF(ta.allele_name, ''::text) IS NOT NULL)
        ), gp AS (
         SELECT m.fish_code,
            string_agg(DISTINCT m.marker_label, ', '::text ORDER BY m.marker_label) AS genotype_pretty
           FROM markers m
          GROUP BY m.fish_code
        )
 SELECT f.fish_code,
    COALESCE(gp.genotype_pretty, ''::text) AS genotype_pretty
   FROM (fish f
     LEFT JOIN gp ON ((gp.fish_code = f.fish_code)));;
CREATE OR REPLACE VIEW public.v_ft_dyes AS  SELECT tf.ft_code,
    d.dye_code
   FROM ((join_ft_dyes j
     JOIN treatments_fluorescent tf ON ((tf.id = j.ft_id)))
     JOIN dyes d ON ((d.id = j.dye_id)));;
CREATE OR REPLACE VIEW public.v_ft_proteins AS  SELECT tf.ft_code,
    fl.fluor_code,
    tg.tag_code
   FROM ((((join_ft_fusions j
     JOIN treatments_fluorescent tf ON ((tf.id = j.ft_id)))
     JOIN fusions fu ON ((fu.id = j.fusion_id)))
     JOIN fluors fl ON ((fl.id = fu.fluor_id)))
     JOIN tags tg ON ((tg.id = fu.tag_id)));;
CREATE OR REPLACE VIEW public.v_plasmids AS  SELECT p.id AS plasmid_id,
    p.code AS plasmid_code,
    p.name AS plasmid_name,
    p.created_at,
    COALESCE(string_agg(DISTINCT fl.fluor_code, ', '::text ORDER BY fl.fluor_code) FILTER (WHERE (fl.id IS NOT NULL)), ''::text) AS fluors,
    COALESCE(string_agg(DISTINCT tg.tag_code, ', '::text ORDER BY tg.tag_code) FILTER (WHERE (tg.id IS NOT NULL)), ''::text) AS tags
   FROM ((((plasmids p
     LEFT JOIN join_plasmid_fusions jpf ON ((jpf.plasmid_id = p.id)))
     LEFT JOIN fusions fu ON ((fu.id = jpf.fusion_id)))
     LEFT JOIN fluors fl ON ((fl.id = fu.fluor_id)))
     LEFT JOIN tags tg ON ((tg.id = fu.tag_id)))
  GROUP BY p.id, p.code, p.name, p.created_at;;
CREATE OR REPLACE VIEW public.v_rna_markers AS  SELECT r.id AS rna_id,
    r.rna_code,
    m.marker_code,
    m.created_at
   FROM (rnas r
     LEFT JOIN rna_markers m ON ((m.rna_id = r.id)));;
CREATE OR REPLACE VIEW public.v_rnas AS  SELECT r.id AS rna_id,
    r.rna_code,
    r.created_at,
    COALESCE(string_agg(DISTINCT fl.fluor_code, ', '::text ORDER BY fl.fluor_code) FILTER (WHERE (fl.id IS NOT NULL)), ''::text) AS fluors,
    COALESCE(string_agg(DISTINCT tg.tag_code, ', '::text ORDER BY tg.tag_code) FILTER (WHERE (tg.id IS NOT NULL)), ''::text) AS tags
   FROM ((((rnas r
     LEFT JOIN join_rna_fusions jrf ON ((jrf.rna_id = r.id)))
     LEFT JOIN fusions fu ON ((fu.id = jrf.fusion_id)))
     LEFT JOIN fluors fl ON ((fl.id = fu.fluor_id)))
     LEFT JOIN tags tg ON ((tg.id = fu.tag_id)))
  GROUP BY r.id, r.rna_code, r.created_at;;
CREATE OR REPLACE VIEW public.v_tanks AS  SELECT id AS tank_uuid,
    tank_code,
    regexp_replace(tank_code, '^.*\(([^)]+)\).*$'::text, '\1'::text) AS fish_code,
    (NULLIF(regexp_replace(tank_code, '^.*#([0-9]+).*$'::text, '\1'::text), ''::text))::integer AS tank_num,
    status,
    created_at
   FROM tanks t;;
