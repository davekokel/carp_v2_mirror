begin;

-- Ensure the transgene base exists (idempotent helper)
create or replace function public.ensure_transgene_base(p_base_code text)
returns void
language plpgsql
as $$
declare
  v_base text := trim(p_base_code);
begin
  if v_base is null or v_base = '' then
    raise exception 'transgene base code required';
  end if;

  -- Try both possible column namings, insert using canonical column
  if not exists (select 1 from public.transgenes t
                 where t.transgene_base_code = v_base
                    or (exists (select 1 from information_schema.columns
                                 where table_schema='public' and table_name='transgenes'
                                   and column_name='base_code')
                        and t.base_code = v_base)) then
    insert into public.transgenes(transgene_base_code) values (v_base)
    on conflict do nothing;
  end if;
end
$$;

-- Fix ambiguity in ensure_allele_from_csv by qualifying/aliasing RETURNING columns
create or replace function public.ensure_allele_from_csv(
  p_base_code       text,
  p_allele_nickname text
)
returns table (
  allele_number     integer,
  allele_name       text,
  allele_nickname   text
)
language plpgsql
as $func$
declare
  v_base text := trim(p_base_code);
  v_nick text := nullif(trim(p_allele_nickname), '');
begin
  if v_base is null or v_base = '' then
    raise exception 'transgene base code required';
  end if;

  -- make sure the base row exists
  perform public.ensure_transgene_base(v_base);

  with ensure as (
    insert into public.transgene_alleles (transgene_base_code, allele_number, allele_name, allele_nickname)
    values (
      v_base,
      (select coalesce(max(ta.allele_number), 0) + 1
         from public.transgene_alleles ta
         where ta.transgene_base_code = v_base),
      null,
      v_nick
    )
    on conflict on constraint uq_transgene_alleles_base_num
    do update
      set allele_nickname = coalesce(excluded.allele_nickname, public.transgene_alleles.allele_nickname)
    -- << disambiguate RETURNING by qualifying and aliasing
    returning public.transgene_alleles.transgene_base_code as r_base,
             public.transgene_alleles.allele_number       as r_num
  ),
  labeled as (
    update public.transgene_alleles ta
       set allele_name = 'gu'||ensure.r_num::text
      from ensure
     where ta.transgene_base_code = ensure.r_base
       and ta.allele_number       = ensure.r_num
    returning ta.allele_number, ta.allele_name, ta.allele_nickname
  )
  select * from labeled;

end
$func$;

commit;
