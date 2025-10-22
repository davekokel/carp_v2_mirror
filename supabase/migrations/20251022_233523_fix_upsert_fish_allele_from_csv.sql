create or replace function public.upsert_fish_allele_from_csv(
  v_fish_id uuid,
  v_base_code text,
  v_allele_nickname text
)
returns void
language plpgsql
as $$
declare
  v_num int;
  v_alias text;
  v_nick_final text;
begin
  if coalesce(v_base_code,'') = '' then
    return;
  end if;

  select r.allele_number
    into v_num
  from public.transgene_allele_registry r
  where r.transgene_base_code = v_base_code
    and coalesce(r.allele_nickname,'') = coalesce(v_allele_nickname,'')
  limit 1;

  if v_num is null then
    select coalesce(max(allele_number),0)+1
      into v_num
    from public.transgene_allele_registry;

    v_alias := 'gu' || v_num::text;
    v_nick_final := coalesce(nullif(v_allele_nickname,''), v_alias);

    insert into public.transgene_allele_registry(
      transgene_base_code, allele_number, allele_nickname, created_at
    )
    values (v_base_code, v_num, v_nick_final, now())
    on conflict do nothing;
  else
    v_alias := 'gu' || v_num::text;
  end if;

  insert into public.transgene_alleles(transgene_base_code, allele_number)
  values (v_base_code, v_num)
  on conflict do nothing;

  insert into public.fish_transgene_alleles(fish_id, transgene_base_code, allele_number)
  values (v_fish_id, v_base_code, v_num)
  on conflict do nothing;
end;
$$;
