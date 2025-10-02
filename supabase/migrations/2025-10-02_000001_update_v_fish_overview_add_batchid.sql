CREATE OR REPLACE VIEW public.v_fish_overview AS
SELECT
    f.id_uuid AS fish_id,
    f.fish_code,
    f.name AS fish_name,
    f.nickname,
    f.line_building_stage,
    f.created_by,
    f.date_of_birth,
    f.seed_batch_id,
    fta.transgene_base_code,
    fta.allele_number,
    tg.name AS transgene_name,
    ipt.plasmid_id AS injected_plasmid_id,
    p1.name AS injected_plasmid_name,
    irt.rna_id AS injected_rna_id,
    r.name AS injected_rna_name
FROM fish f
LEFT JOIN fish_transgene_alleles fta
    ON f.id_uuid = fta.fish_id
LEFT JOIN transgene_alleles ta
    ON fta.transgene_base_code = ta.transgene_base_code AND fta.allele_number = ta.allele_number
LEFT JOIN transgenes tg
    ON ta.transgene_base_code = tg.transgene_base_code
LEFT JOIN injected_plasmid_treatments ipt
    ON f.id_uuid = ipt.fish_id
LEFT JOIN plasmids p1
    ON ipt.plasmid_id = p1.id_uuid
LEFT JOIN injected_rna_treatments irt
    ON f.id_uuid = irt.fish_id
LEFT JOIN rnas r
    ON irt.rna_id = r.id_uuid;
