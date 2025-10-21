begin;

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

create or replace function public.fn_ingest_allele_row_csv(p_base text, p_csv_allele_nickname text)
returns int
language plpgsql
as $$
declare
  v_base text := btrim(p_base);
  v_nick text := nullif(btrim(coalesce(p_csv_allele_nickname,'')), '');
  v_num  int;
  v_name text;
begin
  perform public.fn_ensure_transgene_base(v_base);

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

  insert into public.transgene_alleles(transgene_base_code, allele_nickname)
  values (v_base, v_nick)
  returning allele_number into v_num;

  v_name := 'gu' || v_num::text;

  update public.transgene_alleles ta
     set allele_name     = coalesce(ta.allele_name, v_name),
         allele_nickname = coalesce(ta.allele_nickname, v_nick, v_name)
   where ta.transgene_base_code = v_base
     and ta.allele_number       = v_num;

  return v_num;
end
$$;

commit;
