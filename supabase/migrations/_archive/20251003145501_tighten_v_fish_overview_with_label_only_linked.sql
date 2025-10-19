begin;

-- Rebuild v_fish_overview_with_label using only baseline-safe tables, and
-- include ONLY fish that have at least one genotype link.
drop view if exists public.v_fish_overview_with_label cascade;

create view public.v_fish_overview_with_label as
select
    v.id,
    v.fish_code,
    v.name,
    v.transgene_base_code_filled,
    v.allele_code_filled,
    v.allele_name_filled,
    v.created_at,
    v.created_by,
    fsb.seed_batch_id as batch_label
from public.v_fish_overview as v
left join public.fish_seed_batches as fsb
    on v.id = fsb.fish_id
where
    exists (
        select 1 from public.fish_transgene_alleles as t
        where t.fish_id = v.id
    )
order by v.created_at desc;

commit;
