begin;

create unique index if not exists uq_transgene_alleles_base_nickname
  on public.transgene_alleles(transgene_base_code, allele_nickname)
  where allele_nickname is not null and length(btrim(allele_nickname))>0;

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

-- Canonicalizer: if nickname matches ^\d+(\.0+)?$, store 'digits' only; else store raw string
create or replace function public.fn_canonical_allele_nick(p_nick text)
returns text
language sql
immutable
as $$
  select case
           when p_nick ~ '^[0-9]+(\.0+)?$'
             then regexp_replace(p_nick, '\.0+$', '')
           else p_nick
         end
$$;

create or replace function public.fn_ingest_allele_row_csv(p_base text, p_csv_allele_nickname text)
returns int
language plpgsql
as $$
declare
  v_base text := btrim(p_base);
  v_raw  text := nullif(btrim(coalesce(p_csv_allele_nickname,'')), '');
  v_nick text := case when v_raw is null then null else public.fn_canonical_allele_nick(v_raw) end;
  v_num  int;
  v_name text;
begin
  perform public.fn_ensure_transgene_base(v_base);

  -- REUSE if same canonical nickname already exists for THIS base
  if v_nick is not null then
    select allele_number into v_num
    from public.transgene_alleles
    where transgene_base_code = v_base
      and btrim(coalesce(allele_nickname,'')) = v_nick
    limit 1;
    if v_num is not null then
      return v_num;
    end if;
  end if;

  -- INSERT race-safe; store the CANONICAL nickname (text)
  insert into public.transgene_alleles(transgene_base_code, allele_nickname)
  values (v_base, v_nick)
  on conflict (transgene_base_code, allele_nickname)
    where allele_nickname is not null and length(btrim(allele_nickname))>0
    do nothing
  returning allele_number into v_num;

  if v_num is null then
    select allele_number into v_num
    from public.transgene_alleles
    where transgene_base_code = v_base
      and btrim(coalesce(allele_nickname,'')) = coalesce(v_nick,'')
    order by allele_number
    limit 1;
  end if;

  v_name := 'gu' || v_num::text;

  update public.transgene_alleles ta
     set allele_name     = coalesce(ta.allele_name, v_name),
         allele_nickname = case
                              when ta.allele_nickname is null or length(btrim(ta.allele_nickname))=0
                                then v_name
                              else ta.allele_nickname
                            end
   where ta.transgene_base_code = v_base
     and ta.allele_number       = v_num;

  return v_num;
end
$$;

commit;
