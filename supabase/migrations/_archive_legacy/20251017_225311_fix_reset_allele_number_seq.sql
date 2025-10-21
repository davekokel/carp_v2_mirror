-- Correctly reset allele-number sequence:
-- empty table -> nextval() will return 1
-- non-empty   -> nextval() will return max(allele_number)+1

create or replace function public.reset_allele_number_seq() returns void
language plpgsql
as $$
declare
  v_max int;
begin
  select max(allele_number) into v_max from public.transgene_alleles;

  if v_max is null then
    -- empty table: set current value so that nextval() returns 1
    perform setval('public.transgene_allele_number_seq', 1, false);
  else
    -- non-empty: set current value to max; nextval() returns max+1
    perform setval('public.transgene_allele_number_seq', v_max, true);
  end if;
end;
$$;

comment on function public.reset_allele_number_seq() is
'If table empty, setval(..., 1, false) so nextval() -> 1; else setval(..., max, true) so nextval() -> max+1.';
