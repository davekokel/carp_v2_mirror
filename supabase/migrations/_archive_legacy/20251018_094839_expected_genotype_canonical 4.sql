-- Canonical, nickname-free expected genotype:
-- Builds distinct, sorted tokens of form: base_code#allele_number
-- Source of truth: v_fish_overview_all must expose transgene_base_code, allele_number
create or replace function public.gen_expected_genotype_label(mom_code text, dad_code text)
returns text
language sql
stable
as $$
with mom as (
  select trim(coalesce(transgene_base_code, '')) as bc, allele_number
  from public.v_fish_overview_all  where fish_code = mom_code
),
dad as (
  select trim(coalesce(transgene_base_code, '')) as bc, allele_number
  from public.v_fish_overview_all  where fish_code = dad_code
),
tokens as (
  select case
           when bc <> '' and allele_number is not null
             then bc || '#' || allele_number::text
           else null
         end as t
  from mom AS union all
  select case
           when bc <> '' and allele_number is not null
             then bc || '#' || allele_number::text
           else null
         end
  from dad
)
select coalesce(string_agg(distinct t, ' ; ' order by t), '')
from tokens  where t is not null
$$;

-- Backfill with the canonical form (no nicknames)
update public.clutch_plans cp
set expected_genotype = public.gen_expected_genotype_label(cp.mom_code, cp.dad_code)
where coalesce(expected_genotype, '') <> public.gen_expected_genotype_label(cp.mom_code, cp.dad_code);

update public.clutches cl
set expected_genotype = public.gen_expected_genotype_label(x.mother_code, x.father_code)
from public.cross_instances AS ci
inner join public.crosses AS x on ci.cross_id = x.id
where
    cl.cross_instance_id = ci.id
    and coalesce(cl.expected_genotype, '') <> public.gen_expected_genotype_label(x.mother_code, x.father_code);
