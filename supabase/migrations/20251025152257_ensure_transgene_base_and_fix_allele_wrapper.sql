begin;

-- 1) Ensure a transgene base exists (idempotent)
create or replace function public.ensure_transgene_base(p_base_code text)
returns void
language plpgsql
as $$
begin
  if p_base_code is null or trim(p_base_code) = '' then
    return;
  end if;

  insert into public.transgenes (transgene_base_code)
  values (trim(p_base_code))
  on conflict (transgene_base_code) do nothing;
end
$$;

-- 2) Ensure-allele wrapper: keep signature/OUTs, only extend the body
--    OUTs must match existing definition: (allele_number int, allele_name text, allele_nickname text)
create or replace function public.ensure_allele_from_csv(
  p_base_code        text,
  p_allele_nickname  text
)
returns table(allele_number int, allele_name text, allele_nickname text)
language plpgsql
as $func$
declare
  v_base text := trim(p_base_code);
  v_nick text := nullif(trim(p_allele_nickname), '');
begin
  -- Make sure the parent exists for FK
  perform public.ensure_transgene_base(v_base);

  -- Create or reuse allele row under (base, number) uniqueness;
  -- nickname is stored if provided; name always 'gu'||number
  with ensure as (
    insert into public.transgene_alleles (transgene_base_code, allele_number, allele_name, allele_nickname)
    values (v_base,
            -- DB rule for next global or per-base number:
            -- rely on your existing mechanism; if you use a sequence/global allocator,
            -- replace 'nextval(...)'. Here we reuse your UNIQUE constraint + COALESCE update.
            -- We'll pick the next number as: 1 + max(number) for this base when inserting;
            -- BUT to avoid race conditions we stick to your existing constraint path:
            -- we select a number in a subquery and then ON CONFLICT updates nickname only.
            (
              select coalesce(max(ta.allele_number), 0) + 1
              from public.transgene_alleles ta
              where ta.transgene_base_code = v_base
            ),
            null,  -- set below
            v_nick)
    on conflict on constraint uq_transgene_alleles_base_num
    do update set allele_nickname = coalesce(excluded.allele_nickname, public.transgene_alleles.allele_nickname)
    returning transgene_base_code, allele_number
  )
  , labeled as (
    update public.transgene_alleles ta
    set allele_name = 'gu'||ensure.allele_number::text
    from ensure
    where ta.transgene_base_code = ensure.transgene_base_code
      and ta.allele_number       = ensure.allele_number
    returning ta.allele_number, ta.allele_name, ta.allele_nickname
  )
  select * from labeled;

end
$func$;

commit;
