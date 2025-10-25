-- Rebuild vw_fish_overview using only baseline-safe tables/columns.
-- No dependency on public.treatments; use at_time from injected_* tables.
create or replace view public.vw_fish_overview as
with genotype as (
    select
        fta.fish_id,
        string_agg(
            fta.transgene_base_code || ':' || fta.allele_number
            || case when coalesce(nullif(fta.zygosity, ''), '') <> '' then ' (' || fta.zygosity || ')' else '' end,
            ', ' order by fta.transgene_base_code, fta.allele_number
        ) as genotype_text
    from public.fish_transgene_alleles as fta
    group by fta.fish_id
),

rna_inj as (
    select
        irt.fish_id,
        max(irt.at_time) as last_rna_injection_at,
        string_agg(
            coalesce(r.rna_code, '(unknown)')
            || coalesce(' ' || irt.amount::text, '')
            || coalesce(' ' || irt.units, '')
            || case when coalesce(nullif(irt.note, ''), '') <> '' then ' [' || irt.note || ']' else '' end
            || coalesce(' @ ' || to_char(irt.at_time, 'YYYY-MM-DD'), ''),
            '; ' order by irt.at_time desc
        ) as rna_injections_text
    from public.injected_rna_treatments as irt
    left join public.rnas as r on irt.rna_id = r.id
    group by irt.fish_id
),

plasmid_inj as (
    select
        ipt.fish_id,
        max(ipt.at_time) as last_plasmid_injection_at,
        string_agg(
            coalesce(p.plasmid_code, '(unknown)')
            || coalesce(' ' || ipt.amount::text, '')
            || coalesce(' ' || ipt.units, '')
            || case when coalesce(nullif(ipt.note, ''), '') <> '' then ' [' || ipt.note || ']' else '' end
            || coalesce(' @ ' || to_char(ipt.at_time, 'YYYY-MM-DD'), ''),
            '; ' order by ipt.at_time desc
        ) as plasmid_injections_text
    from public.injected_plasmid_treatments as ipt
    left join public.plasmids as p on ipt.plasmid_id = p.id
    group by ipt.fish_id
)

select
    f.id as fish_id,
    f.fish_code,
    f.name as fish_name,
    f.created_by,
    f.date_birth,
    g.genotype_text,
    ri.last_rna_injection_at,
    ri.rna_injections_text,
    pi.last_plasmid_injection_at,
    pi.plasmid_injections_text
from public.fish as f
left join genotype as g on f.id = g.fish_id
left join rna_inj as ri on f.id = ri.fish_id
left join plasmid_inj as pi on f.id = pi.fish_id;
