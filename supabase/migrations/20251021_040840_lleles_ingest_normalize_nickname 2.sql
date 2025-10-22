begin;

-- Ensure global sequence + uniqueness are in place (no-ops if already set)
create sequence if not exists public.transgene_allele_number_seq;
select setval('public.transgene_allele_number_seq',
              coalesce((select max(allele_number) from public.transgene_alleles),0));
alter table public.transgene_alleles
  alter column allele_number set default nextval('public.transgene_allele_number_seq');
create unique index if not exists uq_transgene_alleles_number
  on public.transgene_alleles(allele_number);

-- Per-base nickname uniqueness (non-null, non-empty)
create unique index if not exists uq_transgene_alleles_base_nickname
  on public.transgene_alleles(transgene_base_code, allele_nickname)
  where allele_nickname is not null and length(btrim(allele_nickname))>0;

-- Ensure base exists (FK-safe)
create or replace function public.fn_ensure_transgene_base(p_base text)
returns void
language plpgsql
as $$
declare v_base text := btrim(p_base);
begin
  if v_base is null or length(v_base)=0 then
    raise exception 'transgene_base_code is required';
  end if;
  insert into public.transgenes(transgene_base_code)
  select v_base
  where not exists (select 1 from public.transgenes where transgene_base_code=v_base);
end
$$;

-- Ingest rule:
--  * CSV allele_nickname is ALWAYS a string
--  * If it looks numeric (e.g., '301', '301.0'), IGNORE it for matching & storage
--  * If non-numeric and already present for THIS base, REUSE that allele_number
--  * Otherwise, create a new allele (global number)
--  * Storage: allele_name='guN'; allele_nickname defaults to guN (we do not store CSV nicknames)
create or replace function public.fn_ingest_allele_row_csv(p_base text, p_csv_allele_nickname text)
returns int
language plpgsql
as $$
declare
  v_base  text := btrim(p_base);
  v_raw   text := btrim(coalesce(p_csv_allele_nickname,''));
  v_norm  text := null;        -- non-numeric nickname, if any
  v_num   int;
  v_name  text;
begin
  perform public.fn_ensure_transgene_base(v_base);

  -- treat numeric-looking CSV nicknames as absent
  if v_raw <> '' and v_raw !~ '^[0-9]+(\\.0+)?$' then
    v_norm := v_raw;
  end if;

  -- REUSE only if non-numeric nickname exists for THIS base
  if v_norm is not null then
    select allele_number into v_num
    from public.transgene_alleles
    where transgene_base_code = v_base
      and btrim(coalesce(allele_nickname,'')) = v_norm
    limit 1;
    if v_num is not null then
      return v_num;
    end if;
  end if;

  -- CREATE new allele (global sequence); we DO NOT store the CSV nickname
  insert into public.transgene_alleles(transgene_base_code)
  values (v_base)
  returning allele_number into v_num;

  v_name := 'gu' || v_num::text;

  -- default nickname = guN; humans may overwrite later
  update public.transgene_alleles ta
     set allele_name     = coalesce(ta.allele_name, v_name),
         allele_nickname = coalesce(ta.allele_nickname, v_name)
   where ta.transgene_base_code = v_base
     and ta.allele_number       = v_num;

  return v_num;
end
$$;

commit;
