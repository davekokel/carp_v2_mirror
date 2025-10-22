\set ON_ERROR_STOP on
begin;

-- Add a deterministic unique constraint on (planned_name, mom_code, dad_code).
-- If you also want to ignore case/whitespace, comment this and create an expression index instead.
do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'uq_clutch_plans_genotype_parents'
      and conrelid = 'public.clutch_plans'::regclass
  ) then
    alter table public.clutch_plans
      add constraint uq_clutch_plans_genotype_parents
      unique (planned_name, mom_code, dad_code);
  end if;
end$$;

commit;
