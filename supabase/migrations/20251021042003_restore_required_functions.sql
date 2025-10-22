\set ON_ERROR_STOP on
begin;

-- OPTIONAL helper (soft contract): ensure base row exists
create or replace function public.fn_ensure_transgene_base(p_base text)
returns void
language sql
as $$
  insert into public.transgenes (transgene_base_code)
  values (btrim(p_base))
  on conflict (transgene_base_code) do nothing
$$;

-- 1) Allele ingestion (reuse on same (base,nickname), keep nickname as TEXT)
create or replace function public.fn_ingest_allele_row_csv(p_base text, p_nickname text)
returns integer
language plpgsql
as $$
declare
  v_base text := btrim(p_base);
  v_raw  text := btrim(coalesce(p_nickname,''));
  v_nick text := nullif(v_raw,'');
  v_num  int;
  v_name text;
begin
  perform public.fn_ensure_transgene_base(v_base);

  -- canonicalize numeric-like nicknames '301.0' -> '301'
  if v_nick is not null and v_nick ~ '^[0-9]+(\.0+)?$' then
    v_nick := regexp_replace(v_nick, '\.0+$', '');
  end if;

  -- reuse if exists
  select allele_number into v_num
  from public.transgene_alleles
  where transgene_base_code = v_base
    and btrim(coalesce(allele_nickname,'')) = coalesce(v_nick,'')
  limit 1;

  if v_num is null then
    -- insert new (nickname may be null/empty)
    insert into public.transgene_alleles (transgene_base_code, allele_nickname)
    values (v_base, v_nick)
    on conflict (transgene_base_code, allele_nickname)
      where allele_nickname is not null and length(btrim(allele_nickname))>0
      do nothing
    returning allele_number into v_num;

    if v_num is null then
      -- conflict path or empty-nick path; select the row we just targeted
      select allele_number into v_num
      from public.transgene_alleles
      where transgene_base_code = v_base
        and btrim(coalesce(allele_nickname,'')) = coalesce(v_nick,'')
      limit 1;
    end if;

    -- default allele_name = 'guN' if not set
    v_name := 'gu' || v_num::text;
    update public.transgene_alleles
       set allele_name = coalesce(allele_name, v_name),
           allele_nickname = coalesce(allele_nickname, v_name)  -- only fills if NULL
     where transgene_base_code = v_base
       and allele_number = v_num;
  end if;

  return v_num;
end
$$;

-- 2) Add tank for fish: tank_code = 'TANK-'||fish_code||'-#n'
--    p_status is cast to enum public.tank_status
create or replace function public.fn_add_tank_for_fish(p_fish_id uuid, p_status text default 'new_tank', p_capacity int default null)
returns text
language plpgsql
as $$
declare
  v_code   text;
  v_fish   record;
  v_n      int;
begin
  select id, fish_code into v_fish from public.fish where id = p_fish_id;
  if v_fish.id is null then
    raise exception 'fish % not found', p_fish_id;
  end if;

  -- next suffix per fish (safe even if helper not present)
  select coalesce(max((regexp_replace(tank_code,'.*#',''))::int),0)+1
    into v_n
    from public.tanks
   where fish_id = p_fish_id;

  v_code := format('TANK-%s-#%s', v_fish.fish_code, v_n);

  insert into public.tanks (fish_id, tank_code, status, capacity)
  values (p_fish_id, v_code, p_status::public.tank_status, p_capacity);

  return v_code;
end
$$;

-- 3) Add ACTIVE tank (convenience)
create or replace function public.fn_add_active_tank_for_fish(p_fish_id uuid, p_capacity int default null)
returns text
language sql
as $$
  select public.fn_add_tank_for_fish($1, 'active', $2)
$$;

commit;
