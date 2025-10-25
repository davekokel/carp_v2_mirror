begin;

create sequence if not exists public.transgene_allele_number_seq;

select setval('public.transgene_allele_number_seq',
  coalesce((select max(allele_number) from public.transgene_alleles),0)
);

alter table public.transgene_alleles
  alter column allele_number set default nextval('public.transgene_allele_number_seq');

do $$
begin
  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and indexname='uq_transgene_alleles_number'
  ) then
    create unique index uq_transgene_alleles_number
      on public.transgene_alleles(allele_number);
  end if;
end$$;

drop trigger if exists trg_transgene_alleles_bi_fill_number on public.transgene_alleles;
drop function if exists public.trg_transgene_alleles_bi_fill_number();
drop function if exists public.fn_next_allele_number(text);

drop index if exists uq_transgene_alleles_base_nick;

create or replace function public.fn_ensure_transgene_base(p_base text)
returns void
language plpgsql
as $$
declare
  v_base text := btrim(p_base);
begin
  if v_base is null or length(v_base)=0 then
    raise exception 'transgene_base_code is required';
  end if;
  insert into public.transgenes (transgene_base_code)
  select v_base
  where not exists (select 1 from public.transgenes where transgene_base_code=v_base);
end
$$;

create or replace function public.fn_ingest_allele_row_csv(p_base text, p_nickname text)
returns int
language plpgsql
as $$
declare
  v_base text := btrim(p_base);
  v_nick text := nullif(btrim(coalesce(p_nickname,'')), '');
  v_num  int;
begin
  perform public.fn_ensure_transgene_base(v_base);

  insert into public.transgene_alleles (transgene_base_code, allele_nickname)
  values (v_base, v_nick)
  returning allele_number into v_num;

  update public.transgene_alleles ta
     set allele_name = coalesce(ta.allele_name, 'gu' || v_num::text)
   where ta.transgene_base_code = v_base
     and ta.allele_number = v_num;

  return v_num;
end
$$;

commit;
