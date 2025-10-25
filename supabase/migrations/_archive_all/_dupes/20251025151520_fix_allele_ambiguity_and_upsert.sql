begin;

-- 1) Ensure a named unique constraint exists on (transgene_base_code, allele_number)
do $$
begin
  if not exists (
    select 1
    from pg_constraint c
    join pg_class t on t.oid = c.conrelid
    where t.relname = 'transgene_alleles'
      and c.conname = 'uq_transgene_alleles_base_num'
  ) then
    alter table public.transgene_alleles
      add constraint uq_transgene_alleles_base_num
      unique (transgene_base_code, allele_number);
  end if;
end $$;

-- 2) Deterministic, DB-driven allele ensure (nickname treated as STRING; global guN)
create or replace function public.ensure_allele_from_csv(
  p_base_code     text,
  p_allele_nick   text
)
returns table(out_allele_number int, out_allele_name text, out_allele_nickname text)
language plpgsql
as $$
declare
  v_num  int;
  v_nick text := nullif(p_allele_nick, '');
begin
  -- a) reuse by registry (exact per-base nickname match)
  if v_nick is not null then
    select r.allele_number
      into v_num
      from public.transgene_allele_registry r
     where r.transgene_base_code = p_base_code
       and r.allele_nickname     = v_nick
     limit 1;
  end if;

  -- b) reuse an existing allele with same nickname for this base (if present)
  if v_num is null then
    select ta.allele_number
      into v_num
      from public.transgene_alleles ta
     where ta.transgene_base_code = p_base_code
       and coalesce(ta.allele_nickname,'') = coalesce(v_nick,'')
     limit 1;
  end if;

  -- c) otherwise mint next GLOBAL guN (unique across the entire DB)
  if v_num is null then
    select coalesce(max(allele_number),0) + 1
      into v_num
      from public.transgene_alleles;
  end if;

  -- d) upsert parent row; avoid ambiguity by targeting the constraint name
  insert into public.transgene_alleles (transgene_base_code, allele_number, allele_name, allele_nickname)
  values (p_base_code, v_num, 'gu'||v_num::text, v_nick)
  on conflict on constraint uq_transgene_alleles_base_num do update
    set allele_nickname = coalesce(excluded.allele_nickname, public.transgene_alleles.allele_nickname);

  -- e) return canonical outputs
  out_allele_number   := v_num;
  out_allele_name     := 'gu'||v_num::text;
  out_allele_nickname := coalesce(v_nick, 'gu'||v_num::text);
  return next;
end
$$;

-- 3) Wrapper your page calls. Reuses/mints and links to the fish.
create or replace function public.upsert_fish_allele_from_csv(
  p_fish_id       uuid,
  p_base_code     text,
  p_allele_nick   text
)
returns void
language plpgsql
as $$
declare
  a record;
begin
  select * into a
  from public.ensure_allele_from_csv(p_base_code, p_allele_nick);

  insert into public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number)
  values (p_fish_id, p_base_code, a.out_allele_number)
  on conflict (fish_id, transgene_base_code)
  do update set allele_number = excluded.allele_number;
end
$$;

commit;
