-- supabase/migrations/2025-10-02_update_vw_fish_overview_patch.sql

create or replace view public.vw_fish_overview as
select
    f.id as fish_id,
    f.fish_code,
    f.name as fish_name,
    f.nickname,
    f.line_building_stage,
    f.description,
    f.strain,
    f.birth_date,
    f.created_by,
    coalesce(fta.seed_batch_id, llf.seed_batch_id) as batch_label,
    fta.transgene_base_code,
    fta.allele_number,
    tg.name as transgene_name,
    tg.description as transgene_description,
    fta.zygosity,
    concat_ws(':', fta.transgene_base_code, fta.allele_number) as transgene_label,
    tmt.name as treatment_name,
    tmt.notes as treatment_notes,
    tmt.start_date,
    tmt.stop_date,
    tmt.treatment_type,
    tmt.concentration,
    tmt.unit
from public.fish f
left join public.fish_transgene_alleles fta on f.id = fta.fish_id
left join public.transgene_alleles ta on fta.transgene_base_code = ta.transgene_base_code and fta.allele_number = ta.allele_number
left join public.transgenes tg on ta.transgene_base_code = tg.transgene_base_code
left join public.fish_treatments ft on f.id = ft.fish_id
left join public.treatments tmt on ft.treatment_id = tmt.id
left join public.load_log_fish llf on f.id = llf.fish_id;