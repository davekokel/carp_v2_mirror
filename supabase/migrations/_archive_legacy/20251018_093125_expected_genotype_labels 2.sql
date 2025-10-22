create or replace function public.gen_expected_genotype_label(mom_code text, dad_code text)
returns text
language sql
stable
as $$
with mom as (
  select trim(coalesce(allele_name, '')) as an, allele_number
  from public.v_fish_overview_all  where fish_code = mom_code
),
dad as (
  select trim(coalesce(allele_name, '')) as an, allele_number
  from public.v_fish_overview_all  where fish_code = dad_code
),
lab as (
  select case
           when an <> '' then an || coalesce('#' || allele_number::text, '')
           else null
         end as lbl
  from mom AS union all
  select case
           when an <> '' then an || coalesce('#' || allele_number::text, '')
           else null
         end
  from dad
)
select coalesce(string_agg(distinct lbl, ' ; ' order by lbl), '')
from lab  where lbl is not null
$$;

alter table public.clutch_plans add column if not exists expected_genotype text;
alter table public.clutches add column if not exists expected_genotype text;

create or replace function public.trg_clutch_plans_set_expected()
returns trigger
language plpgsql
as $$
begin
  if coalesce(new.expected_genotype, '') = '' then
    new.expected_genotype := public.gen_expected_genotype_label(new.mom_code, new.dad_code);
  end if;
  return new;
end$$;

drop trigger if exists trg_clutch_plans_set_expected on public.clutch_plans;
create trigger trg_clutch_plans_set_expected
before insert or update on public.clutch_plans
for each row execute function public.trg_clutch_plans_set_expected();

create or replace function public.trg_clutches_set_expected()
returns trigger
language plpgsql
as $$
declare m text; d text;
begin
  if coalesce(new.expected_genotype, '') <> '' then
    return new;
  end if;

  if new.cross_instance_id is null then
    return new;
  end if;

  select x.mother_code, x.father_code
  into m, d
  from public.cross_instances AS ci
  join public.crosses AS x on x.id = ci.cross_id
  where ci.id = new.cross_instance_id;

  if m is not null and d is not null then
    new.expected_genotype := public.gen_expected_genotype_label(m, d);
  end if;

  return new;
end$$;

drop trigger if exists trg_clutches_set_expected on public.clutches;
create trigger trg_clutches_set_expected
before insert or update on public.clutches
for each row execute function public.trg_clutches_set_expected();

update public.clutch_plans cp
set expected_genotype = public.gen_expected_genotype_label(cp.mom_code, cp.dad_code)
where coalesce(expected_genotype, '') = '';

update public.clutches cl
set expected_genotype = public.gen_expected_genotype_label(x.mother_code, x.father_code)
from public.cross_instances AS ci
inner join public.crosses AS x on ci.cross_id = x.id
where
    cl.cross_instance_id = ci.id
    and coalesce(cl.expected_genotype, '') = '';

create or replace view public.v_clutch_expected_genotype as
select
    cl.id as clutch_id,
    coalesce(cl.expected_genotype, public.gen_expected_genotype_label(x.mother_code, x.father_code))
        as expected_genotype
from public.clutches AS cl
left join public.cross_instances AS ci on cl.cross_instance_id = ci.id
left join public.crosses AS x on ci.cross_id = x.id;
