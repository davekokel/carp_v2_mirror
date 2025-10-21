--
-- PostgreSQL database dump
--

\restrict 4CeWM2n2bBZdqonbufYNdVzh3XYMgcbmGhwqwOaB9f0GNlfH8DxS1H3qNDAPrWE

-- Dumped from database version 17.6
-- Dumped by pg_dump version 18.0

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA public;


--
-- Name: clutch_plan_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.clutch_plan_status AS ENUM (
    'draft',
    'ready',
    'scheduled',
    'closed'
);


--
-- Name: container_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.container_status AS ENUM (
    'planned',
    'active',
    'to_kill',
    'retired'
);


--
-- Name: cross_plan_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.cross_plan_status AS ENUM (
    'planned',
    'canceled',
    'executed'
);


--
-- Name: _allele_display(text, integer, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public._allele_display(p_base text, p_num integer, p_nick text) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
  SELECT COALESCE(NULLIF(p_nick,''), 'Tg(' || p_base || ')' || p_num::text)
$$;


--
-- Name: _copy_plan_treatments_to_cit(uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public._copy_plan_treatments_to_cit(p_clutch_instance_id uuid) RETURNS integer
    LANGUAGE plpgsql
    AS $$
declare
  v_clutch_id uuid;
  v_cnt int := 0;
begin
  select cp.id
  into v_clutch_id
  from public.clutch_instances ci
  join public.cross_instances xi on xi.id = ci.cross_instance_id
  join public.crosses x          on x.id  = xi.cross_id
  join public.planned_crosses pc on pc.cross_id = x.id
  join public.clutch_plans cp    on cp.id = pc.clutch_id
  where ci.id = p_clutch_instance_id
  limit 1;

  if v_clutch_id is null then
    return 0;
  end if;

  insert into public.clutch_instance_treatments (
    clutch_instance_id, material_type, material_code, material_name, notes, created_by
  )
  select
    p_clutch_instance_id,
    coalesce(
      cpt.material_type,
      case
        when cpt.plasmid_code is not null then 'plasmid'
        when cpt.rna_code     is not null then 'rna'
        else 'generic'
      end
    ),
    coalesce(cpt.material_code, cpt.plasmid_code, cpt.rna_code),
    coalesce(cpt.material_name, cpt.plasmid_code, cpt.rna_code, cpt.material_code),
    cpt.notes,
    current_setting('app.user', true)
  from public.clutch_plan_treatments cpt
  where cpt.clutch_id = v_clutch_id
  on conflict (clutch_instance_id,
               lower(coalesce(material_type,'')),
               lower(coalesce(material_code,''))) do nothing;

  get diagnostics v_cnt = row_count;
  return v_cnt;
end
$$;


--
-- Name: apply_plasmid_treatment(uuid, uuid, numeric, text, timestamp with time zone, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.apply_plasmid_treatment(p_fish_id uuid, p_plasmid_id uuid, p_amount numeric, p_units text, p_at_time timestamp with time zone, p_note text) RETURNS void
    LANGUAGE plpgsql
    AS $$
  BEGIN
    IF to_regclass('public.injected_plasmid_treatments') IS NULL THEN
      RAISE NOTICE 'Skipping plasmid treatment: injected_plasmid_treatments not present.';
      RETURN;
    END IF;

    INSERT INTO public.injected_plasmid_treatments
      (fish_id, plasmid_id, amount, units, at_time, note)
    VALUES
      (p_fish_id, p_plasmid_id, p_amount, p_units, p_at_time, p_note)
    ON CONFLICT ON CONSTRAINT uq_ipt_natural DO NOTHING;
  END
  $$;


--
-- Name: apply_rna_treatment(uuid, uuid, numeric, text, timestamp with time zone, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.apply_rna_treatment(p_fish_id uuid, p_rna_id uuid, p_amount numeric, p_units text, p_at_time timestamp with time zone, p_note text) RETURNS void
    LANGUAGE plpgsql
    AS $$
  BEGIN
    IF to_regclass('public.injected_rna_treatments') IS NULL THEN
      RAISE NOTICE 'Skipping RNA treatment: injected_rna_treatments not present.';
      RETURN;
    END IF;

    INSERT INTO public.injected_rna_treatments
      (fish_id, rna_id, amount, units, at_time, note)
    VALUES
      (p_fish_id, p_rna_id, p_amount, p_units, p_at_time, p_note)
    ON CONFLICT ON CONSTRAINT uq_irt_natural DO NOTHING;
  END
  $$;


--
-- Name: assign_fish_to_tank(uuid, uuid, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.assign_fish_to_tank(p_fish_id uuid, p_container_id uuid, p_by text, p_note text DEFAULT NULL::text) RETURNS uuid
    LANGUAGE plpgsql
    AS $$
DECLARE
  rid uuid;
BEGIN
  UPDATE public.fish_tank_memberships
    SET left_at = now()
    WHERE fish_id = p_fish_id AND left_at IS NULL;

  INSERT INTO public.fish_tank_memberships (fish_id, container_id, note)
  VALUES (p_fish_id, p_container_id, p_note)
  RETURNING id INTO rid;

  PERFORM public.mark_container_active(p_container_id, p_by);
  RETURN rid;
END$$;


--
-- Name: create_label_job(text, uuid, text, text, text, jsonb, text, boolean); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.create_label_job(p_entity_type text, p_entity_id uuid, p_template text, p_media text, p_requested_by text, p_cards jsonb, p_dedupe_hash text DEFAULT NULL::text, p_replace boolean DEFAULT false) RETURNS uuid
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_job uuid;
  v_row jsonb;
  v_idx int := 0;
BEGIN
  IF p_dedupe_hash IS NOT NULL THEN
    IF p_replace THEN
      DELETE FROM public.label_jobs WHERE dedupe_hash = p_dedupe_hash;
    ELSE
      SELECT id_uuid INTO v_job FROM public.label_jobs WHERE dedupe_hash = p_dedupe_hash LIMIT 1;
      IF v_job IS NOT NULL THEN
        RETURN v_job; -- idempotent return
      END IF;
    END IF;
  END IF;

  INSERT INTO public.label_jobs(entity_type, entity_id, template, media, status, requested_by, source_params, dedupe_hash)
  VALUES (p_entity_type, p_entity_id, p_template, p_media, 'queued', p_requested_by, jsonb_build_object('cards_count', jsonb_array_length(p_cards)), p_dedupe_hash)
  RETURNING id_uuid INTO v_job;

  FOR v_row IN SELECT * FROM jsonb_array_elements(p_cards)
  LOOP
    v_idx := v_idx + 1;
    INSERT INTO public.label_items(job_id, seq, fish_code, tank_id, request_id, payload)
    VALUES (
      v_job,
      v_idx,
      COALESCE((v_row->>'fish_code'), NULL),
      NULL,
      NULLIF(v_row->>'request_id',''),
      v_row
    );
  END LOOP;

  UPDATE public.label_jobs SET num_labels = v_idx WHERE id_uuid = v_job;
  RETURN v_job;
END $$;


--
-- Name: create_offspring_batch(uuid, uuid, integer, text, date, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.create_offspring_batch(p_mother_id uuid, p_father_id uuid, p_count integer, p_created_by text DEFAULT NULL::text, p_birth_date date DEFAULT NULL::date, p_name_prefix text DEFAULT NULL::text) RETURNS TABLE(child_id uuid, fish_code text)
    LANGUAGE plpgsql
    AS $_$
  DECLARE
    i int;
    has_created_by boolean := public._table_has('public','fish','created_by');
    has_date_birth boolean := public._table_has('public','fish','date_birth');
    has_name       boolean := public._table_has('public','fish','name');
    cols text := 'id';
    vals text := 'gen_random_uuid()';
    fish_row record;
  BEGIN
    IF p_count IS NULL OR p_count < 1 THEN
      RAISE EXCEPTION 'p_count must be >= 1';
    END IF;

    -- build column list dynamically
    IF has_created_by THEN cols := cols||', created_by'; END IF;
    IF has_date_birth THEN cols := cols||', date_birth'; END IF;
    IF has_name       THEN cols := cols||', name';       END IF;

    FOR i IN 1..p_count LOOP
      vals := 'gen_random_uuid()';
      IF has_created_by THEN
        vals := vals||', '||quote_nullable(p_created_by);
      END IF;
      IF has_date_birth THEN
        vals := vals||', '||coalesce(quote_nullable(p_birth_date), 'null');
      END IF;
      IF has_name THEN
        vals := vals||', '||quote_nullable(
          CASE WHEN p_name_prefix IS NULL THEN NULL
               ELSE p_name_prefix||'-'||lpad(i::text,3,'0') END
        );
      END IF;

      EXECUTE format('insert into public.fish (%s) values (%s) returning id, fish_code', cols, vals)
      INTO fish_row;

      -- optional parent linkage
      BEGIN
        IF public._table_has('public','fish','mother_id') THEN
          EXECUTE 'update public.fish set mother_id = $1 where id = $2'
          USING p_mother_id, fish_row.id;
        END IF;
        IF public._table_has('public','fish','father_id') THEN
          EXECUTE 'update public.fish set father_id = $1 where id = $2'
          USING p_father_id, fish_row.id;
        END IF;
      EXCEPTION WHEN undefined_column THEN
        NULL;
      END;

      child_id  := fish_row.id;
      fish_code := fish_row.fish_code;
      RETURN NEXT;
    END LOOP;
  END
  $_$;


--
-- Name: ensure_clutch_for_cross_instance(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ensure_clutch_for_cross_instance() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
declare has_created_by boolean;
begin
  select exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='clutch_instances' and column_name='created_by'
  ) into has_created_by;

  if exists (select 1 from public.clutch_instances where cross_instance_id = new.id) then
    return new;
  end if;

  if has_created_by then
    insert into public.clutch_instances (cross_instance_id, birthday, created_by)
    values (new.id, coalesce(new.cross_date, current_date), coalesce(new.created_by, 'system'));
  else
    insert into public.clutch_instances (cross_instance_id, birthday)
    values (new.id, coalesce(new.cross_date, current_date));
  end if;

  return new;
end $$;


--
-- Name: ensure_inventory_tank(text, text, public.container_status); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ensure_inventory_tank(p_label text, p_by text, p_status public.container_status DEFAULT 'active'::public.container_status) RETURNS uuid
    LANGUAGE plpgsql
    AS $$
DECLARE
  rid uuid;
BEGIN
  SELECT id_uuid INTO rid
  FROM public.containers
  WHERE container_type='inventory_tank' AND COALESCE(label,'') = COALESCE(p_label,'')
  ORDER BY created_at ASC
  LIMIT 1;

  IF rid IS NULL THEN
    INSERT INTO public.containers (container_type, label, status, created_by, note)
    VALUES ('inventory_tank', p_label, COALESCE(p_status,'active'), p_by, NULL)
    RETURNING id_uuid INTO rid;
  ELSE
    IF p_status='active' THEN
      PERFORM public.mark_container_active(rid, p_by);
    END IF;
  END IF;

  RETURN rid;
END$$;


--
-- Name: ensure_inventory_tank_text(text, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ensure_inventory_tank_text(p_label text, p_by text, p_status text) RETURNS uuid
    LANGUAGE plpgsql
    AS $$
BEGIN
  RETURN public.ensure_inventory_tank(p_label, p_by, p_status::container_status);
END$$;


--
-- Name: ensure_inventory_tank_v(text, text, public.container_status, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ensure_inventory_tank_v(p_label text, p_by text, p_status public.container_status DEFAULT 'active'::public.container_status, p_volume_l integer DEFAULT NULL::integer) RETURNS uuid
    LANGUAGE plpgsql
    AS $$
DECLARE
  rid uuid;
BEGIN
  SELECT id_uuid INTO rid
    FROM public.containers
   WHERE container_type='inventory_tank'
     AND COALESCE(label,'') = COALESCE(p_label,'')
   ORDER BY created_at ASC
   LIMIT 1;

  IF rid IS NULL THEN
    INSERT INTO public.containers (container_type, label, tank_code, status, created_by, tank_volume_l, note)
    VALUES ('inventory_tank', p_label, public.gen_tank_code(), COALESCE(p_status,'active'), p_by, p_volume_l, NULL)
    RETURNING id_uuid INTO rid;
  ELSE
    IF p_status='active' THEN
      PERFORM public.mark_container_active(rid, p_by);
    END IF;
    UPDATE public.containers
       SET tank_volume_l = COALESCE(tank_volume_l, p_volume_l)
     WHERE id_uuid = rid;
  END IF;

  RETURN rid;
END$$;


--
-- Name: ensure_inventory_tank_v_text(text, text, text, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ensure_inventory_tank_v_text(p_label text, p_by text, p_status text, p_volume_l integer) RETURNS uuid
    LANGUAGE plpgsql
    AS $$
BEGIN
  RETURN public.ensure_inventory_tank_v(p_label, p_by, p_status::container_status, p_volume_l);
END$$;


--
-- Name: ensure_rna_for_plasmid(text, text, text, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ensure_rna_for_plasmid(p_plasmid_code text, p_suffix text, p_name text, p_created_by text, p_notes text) RETURNS TABLE(rna_id uuid, rna_code text)
    LANGUAGE plpgsql
    AS $$
declare
  v_plasmid_id uuid;
  v_code text;
begin
  select id into v_plasmid_id
  from public.plasmids
  where code = p_plasmid_code
  limit 1;

  if v_plasmid_id is null then
    raise exception 'ensure_rna_for_plasmid: plasmid code % not found', p_plasmid_code;
  end if;

  -- If no explicit name provided, generate from plasmid code + suffix
  v_code := coalesce(nullif(p_name,''), p_plasmid_code || coalesce(p_suffix,''));

  insert into public.rnas(code, name, source_plasmid_id, created_by, notes)
  values (v_code, v_code, v_plasmid_id, nullif(p_created_by,''), nullif(p_notes,''))
  on conflict (code) do update
    set name = excluded.name,
        source_plasmid_id = coalesce(excluded.source_plasmid_id, public.rnas.source_plasmid_id),
        created_by        = coalesce(excluded.created_by,        public.rnas.created_by),
        notes             = coalesce(excluded.notes,             public.rnas.notes)
  returning id, code
  into rna_id, rna_code;

  return next;
end;
$$;


--
-- Name: ensure_transgene_allele(text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ensure_transgene_allele(p_transgene_base_code text, p_allele_nickname text, OUT ret_allele_number text) RETURNS text
    LANGUAGE plpgsql
    AS $_$
declare
  v_nick    text := nullif(btrim(p_allele_nickname), '');
  v_num_int int  := null;
begin
  -- 0) ensure base exists to satisfy FK
  perform public.ensure_transgene_base(p_transgene_base_code);

  -- 1) reuse by nickname (global)
  if v_nick is not null and lower(v_nick) <> 'new' then
    select ta.allele_number
      into v_num_int
    from public.transgene_alleles ta
    where ta.allele_nickname = v_nick
    limit 1;

    -- 1b) if not found and nickname is digits, reuse by number (global)
    if v_num_int is null and v_nick ~ '^\d+$' then
      select ta.allele_number
        into v_num_int
      from public.transgene_alleles ta
      where ta.allele_number = v_nick::int
      limit 1;
    end if;
  end if;

  -- 2) mint if still null
  if v_num_int is null then
    v_num_int := nextval('public.transgene_allele_number_seq')::int;
  end if;

  -- 3) upsert base+number; set nickname if provided
  insert into public.transgene_alleles(transgene_base_code, allele_number, allele_nickname)
  values (p_transgene_base_code, v_num_int, v_nick)
  on conflict (transgene_base_code, allele_number) do update
    set allele_nickname = coalesce(excluded.allele_nickname, public.transgene_alleles.allele_nickname);

  ret_allele_number := v_num_int::text;
  return;
end;
$_$;


--
-- Name: FUNCTION ensure_transgene_allele(p_transgene_base_code text, p_allele_nickname text, OUT ret_allele_number text); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.ensure_transgene_allele(p_transgene_base_code text, p_allele_nickname text, OUT ret_allele_number text) IS 'Ensures base exists; reuses allele by nickname/number globally; mints only if no match. Inserts integer allele_number; returns text.';


--
-- Name: ensure_transgene_base(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ensure_transgene_base(p_base text) RETURNS void
    LANGUAGE plpgsql
    AS $$
begin
  if coalesce(nullif(p_base,''),'') is null then
    return;
  end if;
  -- Try insert; ignore if already present
  begin
    insert into public.transgenes (transgene_base_code)
    values (p_base)
    on conflict (transgene_base_code) do nothing;
  exception when undefined_table then
    -- If the table doesn't exist in this env, do nothing.
    null;
  end;
end;
$$;


--
-- Name: FUNCTION ensure_transgene_base(p_base text); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.ensure_transgene_base(p_base text) IS 'Insert transgene base if missing (no-op if present).';


--
-- Name: fish_before_insert_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fish_before_insert_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $_$
BEGIN
  IF NEW.fish_code IS NULL
     OR btrim(NEW.fish_code) = ''
     OR NEW.fish_code !~ '^FSH-[0-9]{2}[0-9A-Z]{4,}$' THEN
    NEW.fish_code := public.make_fish_code_yy_seq36(now());
  END IF;
  RETURN NEW;
END $_$;


--
-- Name: fish_bi_set_fish_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fish_bi_set_fish_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $_$
DECLARE
  v bigint;
  r int;
  s text := '';
  yy text;
  digits constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
BEGIN
  IF NEW.fish_code IS NULL OR NEW.fish_code !~ '^FSH-\d{2}[0-9A-Z]{4}$' THEN
    -- two-digit UTC year
    yy := to_char(timezone('UTC', now()), 'YY');

    -- next sequence value → base36
    v := nextval('public.fish_code_seq');
    IF v = 0 THEN
      s := '0';
    ELSE
      WHILE v > 0 LOOP
        r := (v % 36)::int;
        s := substr(digits, r+1, 1) || s;
        v := v / 36;
      END LOOP;
    END IF;

    -- left-pad base36 to 4 chars
    s := lpad(s, 4, '0');

    NEW.fish_code := 'FSH-' || yy || s;
  END IF;
  RETURN NEW;
END;
$_$;


--
-- Name: fish_birthday_sync(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fish_birthday_sync() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
  -- If 'birthday' provided, mirror to date_birth
  if tg_op in ('INSERT','UPDATE') then
    if new.birthday is not null and (new.date_birth is distinct from new.birthday) then
      new.date_birth := new.birthday;
    end if;
    -- If only date_birth provided (legacy writers), mirror to birthday
    if new.date_birth is not null and (new.birthday is distinct from new.date_birth) then
      new.birthday := new.date_birth;
    end if;
  end if;
  return new;
end;
$$;


--
-- Name: FUNCTION fish_birthday_sync(); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.fish_birthday_sync() IS 'Keeps fish.birthday and fish.date_birth in sync during transition to birthday as canonical.';


--
-- Name: gen_clutch_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_clutch_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
  n bigint := nextval('public.seq_clutch_code');
  yy text := to_char(current_date, 'YY');
  alphabet text := '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
  x bigint := n;
  out text := '';
  r int;
BEGIN
  IF x = 0 THEN out := '0'; END IF;
  WHILE x > 0 LOOP
    r := (x % 32);
    out := substr(alphabet, r+1, 1) || out;
    x := x / 32;
  END LOOP;
  -- left-pad to 4 chars for readability
  WHILE length(out) < 4 LOOP
    out := '0' || out;
  END LOOP;
  RETURN 'CL-' || yy || out;
END$$;


--
-- Name: gen_clutch_instance_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_clutch_instance_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE y text := to_char(current_date,'YY'); n bigint;
BEGIN SELECT nextval('public.clutch_instance_code_seq') INTO n; RETURN format('CI-%s%05s', y, n); END;
$$;


--
-- Name: gen_clutch_strain(text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_clutch_strain(mom_code text, dad_code text) RETURNS text
    LANGUAGE sql STABLE
    AS $$
with m as (
  select distinct btrim(v.genetic_background) as s
  from public.v_fish_overview_all v
  where v.fish_code = mom_code and btrim(coalesce(v.genetic_background,'')) <> ''
),
d as (
  select distinct btrim(v.genetic_background) as s
  from public.v_fish_overview_all v
  where v.fish_code = dad_code and btrim(coalesce(v.genetic_background,'')) <> ''
),
u as (
  select s from m
  union
  select s from d
)
select case
         when (select count(*) from u) = 0 then null
         when (select count(*) from u) = 1 then (select s from u)
         else (select string_agg(s, ' ; ' order by s) from u)
       end;
$$;


--
-- Name: gen_cross_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_cross_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
declare
  yy text := to_char(current_date, 'YY');
  n  bigint := nextval('public.seq_cross_code');
begin
  -- Example: CROSS-25 + 0001  => 'CROSS-250001' (no spaces, no hyphen after year)
  return 'CROSS-' || yy || to_char(n, 'FM0000');
end$$;


--
-- Name: gen_cross_code_name(text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_cross_code_name(p_mom_code text, p_dad_code text) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
  select coalesce(p_mom_code,'') || ' × ' || coalesce(p_dad_code,'')
$$;


--
-- Name: gen_cross_genotype(text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_cross_genotype(p_mom_code text, p_dad_code text) RETURNS text
    LANGUAGE sql STABLE
    AS $$
  SELECT public.gen_fish_genotype(p_mom_code) || ' × ' || public.gen_fish_genotype(p_dad_code)
$$;


--
-- Name: gen_cross_name(text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_cross_name(mom text, dad text) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
  SELECT trim(coalesce(NULLIF(mom,''),'?')) || ' × ' || trim(coalesce(NULLIF(dad,''),'?'));
$$;


--
-- Name: gen_cross_run_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_cross_run_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE y text := to_char(current_date,'YY'); n bigint;
BEGIN SELECT nextval('public.cross_run_code_seq') INTO n; RETURN format('XR-%s%05s', y, n); END;
$$;


--
-- Name: gen_expected_genotype_label(text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_expected_genotype_label(mom_code text, dad_code text) RETURNS text
    LANGUAGE sql STABLE
    AS $$
with mom as (
  select trim(coalesce(allele_name,'')) as an, allele_number
  from public.v_fish_overview_all
  where fish_code = mom_code
),
dad as (
  select trim(coalesce(allele_name,'')) as an, allele_number
  from public.v_fish_overview_all
  where fish_code = dad_code
),
lab as (
  select case
           when an <> '' then an || coalesce('#' || allele_number::text, '')
           else null
         end as lbl
  from mom
  union all
  select case
           when an <> '' then an || coalesce('#' || allele_number::text, '')
           else null
         end
  from dad
)
select coalesce(string_agg(distinct lbl, ' ; ' order by lbl), '')
from lab
where lbl is not null
$$;


--
-- Name: gen_fish_genotype(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_fish_genotype(p_fish_code text) RETURNS text
    LANGUAGE sql STABLE
    AS $$
  WITH alias AS (
    SELECT alias FROM public.cross_parent_aliases WHERE parent_code = p_fish_code
  ),
  alleles AS (
    SELECT
      ta.transgene_base_code AS base,
      ta.allele_number       AS num,
      NULLIF(ta.allele_nickname,'') AS nick
    FROM public.fish f
    JOIN public.fish_transgene_alleles fta
      ON fta.fish_id = f.id
    JOIN public.transgene_alleles ta
      ON ta.transgene_base_code = fta.transgene_base_code
     AND ta.allele_number       = fta.allele_number
    WHERE f.fish_code = p_fish_code
  ),
  built AS (
    SELECT STRING_AGG(public._allele_display(base,num,nick), ' + ' ORDER BY base, num) AS g
    FROM alleles
  )
  SELECT
    COALESCE( (SELECT alias FROM alias),
              NULLIF((SELECT g FROM built), ''),
              p_fish_code )
$$;


--
-- Name: gen_tank_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_tank_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
  yy int := (extract(year from now())::int % 100);
  c  bigint;
BEGIN
  INSERT INTO public.tank_year_counters(year,n) VALUES (yy,0)
  ON CONFLICT (year) DO NOTHING;

  UPDATE public.tank_year_counters
     SET n = tank_year_counters.n + 1
   WHERE year = yy
  RETURNING n INTO c;

  RETURN format('TANK-%02s-%04s', yy, c);
END$$;


--
-- Name: gen_tank_code_for_fish(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_tank_code_for_fish(p_fish_code text) RETURNS text
    LANGUAGE plpgsql
    AS $_$
DECLARE
  next_n int;
BEGIN
  -- Find the max trailing number for this fish's tanks: 'TANK <FISH_CODE> #<n>'
  SELECT COALESCE(MAX( (substring(tank_code FROM '#([0-9]+)$'))::int ), 0) + 1
  INTO next_n
  FROM public.containers
  WHERE tank_code LIKE ('TANK ' || p_fish_code || ' #%');

  RETURN 'TANK ' || p_fish_code || ' #' || next_n;
END
$_$;


--
-- Name: gen_tank_pair_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_tank_pair_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
declare
  yy text := to_char(current_date, 'YY');
  n  bigint := nextval('public.seq_tank_pair_code');
begin
  return 'TP-' || yy || '-' || to_char(n, 'FM0000');
end$$;


--
-- Name: inherit_transgene_alleles(uuid, uuid, uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.inherit_transgene_alleles(child_id uuid, mother_id uuid, father_id uuid) RETURNS void
    LANGUAGE plpgsql
    AS $$
  BEGIN
    IF to_regclass('public.fish_transgene_alleles') IS NULL
       OR to_regclass('public.transgene_alleles') IS NULL THEN
      RAISE NOTICE 'Skipping inheritance: missing fish_transgene_alleles/transgene_alleles.';
      RETURN;
    END IF;

    INSERT INTO public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number, zygosity)
    SELECT child_id, x.transgene_base_code, x.allele_number, 'unknown'
    FROM (
      SELECT DISTINCT transgene_base_code, allele_number
      FROM public.fish_transgene_alleles
      WHERE fish_id IN (mother_id, father_id)
    ) x
    ON CONFLICT DO NOTHING;
  END
  $$;


--
-- Name: is_container_live(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.is_container_live(s text) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    AS $$
  select s in ('active','new_tank')
$$;


--
-- Name: make_fish_code_compact(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.make_fish_code_compact() RETURNS text
    LANGUAGE sql
    AS $$
  SELECT 'FSH-' || to_char(current_date,'YY') || util_mig._to_base36(nextval('public.fish_code_seq'), 4)
$$;


--
-- Name: make_fish_code_yy_seq36(timestamp with time zone); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.make_fish_code_yy_seq36(ts timestamp with time zone DEFAULT now()) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
  yy_i int  := extract(year from ts)::int;
  yy   text := to_char(ts, 'YY');
  k    bigint;
BEGIN
  INSERT INTO public.fish_year_counters(year, n)
  VALUES (yy_i, 1)
  ON CONFLICT (year) DO UPDATE
    SET n = public.fish_year_counters.n + 1
  RETURNING n INTO k;

  RETURN 'FSH-' || yy || util_mig._to_base36(k, 4);
END $$;


--
-- Name: make_tank_code_compact(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.make_tank_code_compact() RETURNS text
    LANGUAGE sql
    AS $$
  select 'TANK-' || to_char(current_date,'YY') || util_mig._to_base36(nextval('public.tank_code_seq'), 4)
$$;


--
-- Name: mark_container_active(uuid, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.mark_container_active(p_id uuid, p_by text) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  UPDATE public.containers
  SET status='active',
      status_changed_at=now(),
      activated_at=COALESCE(activated_at, now())
  WHERE id_uuid=p_id;
END$$;


--
-- Name: mark_container_inactive(uuid, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.mark_container_inactive(p_id uuid, p_by text) RETURNS void
    LANGUAGE plpgsql
    AS $$ BEGIN
  PERFORM public.set_container_status(p_id, 'to_kill', p_by, 'compat: inactive→to_kill');
END $$;


--
-- Name: mark_container_retired(uuid, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.mark_container_retired(p_id uuid, p_by text, p_reason text DEFAULT NULL::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  UPDATE public.containers
  SET status='retired',
      status_changed_at=now(),
      deactivated_at=COALESCE(deactivated_at, now()),
      note = CASE WHEN p_reason IS NOT NULL AND p_reason <> '' THEN COALESCE(note,'') || CASE WHEN note IS NULL OR note='' THEN '' ELSE E'
' END || ('retired @ '||now()||' by '||COALESCE(p_by,'?')||COALESCE(' — '||p_reason,'')) ELSE note END
  WHERE id_uuid=p_id;
END$$;


--
-- Name: mark_container_to_kill(uuid, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.mark_container_to_kill(p_id uuid, p_by text, p_reason text DEFAULT NULL::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  UPDATE public.containers
  SET status='to_kill',
      status_changed_at=now(),
      deactivated_at=COALESCE(deactivated_at, now()),
      note = CASE WHEN p_reason IS NOT NULL AND p_reason <> '' THEN COALESCE(note,'') || CASE WHEN note IS NULL OR note='' THEN '' ELSE E'
' END || ('to_kill @ '||now()||' by '||COALESCE(p_by,'?')||COALESCE(' — '||p_reason,'')) ELSE note END
  WHERE id_uuid=p_id;
END$$;


--
-- Name: next_fish_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.next_fish_code() RETURNS text
    LANGUAGE sql
    AS $$
  SELECT 'FSH-' || to_char(nextval('public.fish_code_seq'), 'FM000000');
$$;


--
-- Name: normalize_cross_code(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.normalize_cross_code(p_code text) RETURNS text
    LANGUAGE sql STABLE
    AS $$
  SELECT CASE
    WHEN p_code IS NULL OR length(btrim(p_code))=0 THEN NULL
    WHEN upper(p_code) ~ '^CR-'     THEN 'CROSS-' || substr(upper(p_code), 4)
    WHEN upper(p_code) ~ '^CROSS-'  THEN upper(p_code)
    ELSE upper(p_code)
  END
$$;


--
-- Name: possible_parents_by_tokens(text[], integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.possible_parents_by_tokens(tokens text[], min_hits integer DEFAULT 1) RETURNS TABLE(fish_code text, hits text[], hits_count integer, genotype text, genetic_background text, n_live integer)
    LANGUAGE sql STABLE
    AS $$
with toks as (
  select distinct lower(trim(t)) as tok
  from unnest(coalesce(tokens, array[]::text[])) as t
  where length(trim(t)) >= 3
),
match as (
  select s.fish_code,
         s.genotype,
         s.genetic_background,
         s.n_live,
         array_agg(t.tok order by t.tok) filter (where t.tok is not null and s.txt like ('%'||t.tok||'%')) as hits
  from public.v_fish_search s
  left join toks t on true
  where s.n_live > 0
  group by s.fish_code, s.genotype, s.genetic_background, s.n_live
)
select m.fish_code,
       coalesce(m.hits, array[]::text[]) as hits,
       coalesce(cardinality(m.hits), 0)  as hits_count,
       m.genotype,
       m.genetic_background,
       m.n_live
from match m
where coalesce(cardinality(m.hits),0) >= greatest(min_hits, 0)
order by hits_count desc, n_live desc, m.fish_code;
$$;


--
-- Name: FUNCTION possible_parents_by_tokens(tokens text[], min_hits integer); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.possible_parents_by_tokens(tokens text[], min_hits integer) IS 'Return fish with live tanks whose genotype/background matches any of the given tokens; ranked by #hits, then n_live.';


--
-- Name: refresh_mv_fish_search(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.refresh_mv_fish_search() RETURNS void
    LANGUAGE plpgsql
    AS $$
begin
  -- If the MV exists but is not yet populated, do a normal refresh
  if exists (
    select 1
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relname = 'mv_fish_search'
      and c.relkind = 'm'
      and not c.relispopulated
  ) then
    execute 'REFRESH MATERIALIZED VIEW public.mv_fish_search';
  else
    -- MV is populated (or will be by now) → use concurrent to avoid write locks
    execute 'REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_fish_search';
  end if;
end;
$$;


--
-- Name: refresh_mv_overview_clutches_daily(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.refresh_mv_overview_clutches_daily() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_clutches_daily;
  RETURN NULL;
END
$$;


--
-- Name: refresh_mv_overview_crosses_daily(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.refresh_mv_overview_crosses_daily() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_crosses_daily;
  RETURN NULL;
END
$$;


--
-- Name: refresh_mv_overview_fish_daily(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.refresh_mv_overview_fish_daily() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_fish_daily;
  RETURN NULL;
END
$$;


--
-- Name: refresh_mv_overview_mounts_daily(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.refresh_mv_overview_mounts_daily() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_mounts_daily;
  RETURN NULL;
END
$$;


--
-- Name: refresh_mv_overview_plasmids_daily(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.refresh_mv_overview_plasmids_daily() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_plasmids_daily;
  RETURN NULL;
END
$$;


--
-- Name: refresh_mv_overview_tanks_daily(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.refresh_mv_overview_tanks_daily() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_tanks_daily;
  RETURN NULL;
END
$$;


--
-- Name: reset_allele_number_seq(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.reset_allele_number_seq() RETURNS void
    LANGUAGE plpgsql
    AS $$
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


--
-- Name: FUNCTION reset_allele_number_seq(); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.reset_allele_number_seq() IS 'If table empty, setval(..., 1, false) so nextval() -> 1; else setval(..., max, true) so nextval() -> max+1.';


--
-- Name: safe_drop_view(text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.safe_drop_view(_schema text, _name text) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname=_schema AND viewname=_name) THEN
    EXECUTE format('DROP VIEW %I.%I CASCADE', _schema, _name);
  END IF;
END$$;


--
-- Name: set_container_status(uuid, public.container_status, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_container_status(p_id uuid, p_new public.container_status, p_by text, p_reason text DEFAULT NULL::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_old container_status;
  v_allowed boolean := false;
BEGIN
  SELECT status INTO v_old FROM public.containers WHERE id_uuid = p_id FOR UPDATE;
  IF v_old IS NULL THEN RAISE EXCEPTION 'container % not found', p_id; END IF;
  IF v_old = p_new THEN
    UPDATE public.containers SET status_changed_at = now() WHERE id_uuid = p_id;
    RETURN;
  END IF;
  v_allowed :=
       (v_old = 'planned' AND p_new IN ('active','retired'))
    OR (v_old = 'active'  AND p_new IN ('to_kill','retired'))
    OR (v_old = 'to_kill' AND p_new IN ('retired'))
    OR (v_old = 'retired' AND p_new IN ('retired'));
  IF NOT v_allowed THEN RAISE EXCEPTION 'illegal status transition: % → %', v_old, p_new; END IF;

  UPDATE public.containers
  SET status = p_new,
      status_changed_at = now(),
      activated_at   = CASE WHEN p_new='active' THEN COALESCE(activated_at, now()) ELSE activated_at END,
      deactivated_at = CASE WHEN p_new IN ('to_kill','retired') THEN COALESCE(deactivated_at, now()) ELSE deactivated_at END,
      note = CASE
               WHEN p_reason IS NOT NULL AND p_reason <> ''
                 THEN COALESCE(note,'') || CASE WHEN note IS NULL OR note='' THEN '' ELSE E'
' END ||
                      ('status: '||v_old||' → '||p_new||' @ '||now()||' by '||COALESCE(p_by,'?')||COALESCE(' — '||p_reason,''))
               ELSE note
             END
  WHERE id_uuid = p_id;

  INSERT INTO public.container_status_history(container_id, old_status, new_status, changed_by, reason)
  VALUES (p_id, v_old, p_new, p_by, p_reason);
END $$;


--
-- Name: tg_upsert_fish_seed_maps(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.tg_upsert_fish_seed_maps() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  INSERT INTO public.fish_seed_batches (fish_id, seed_batch_id, updated_at)
  VALUES (NEW.fish_id, NEW.seed_batch_id, now())
  ON CONFLICT (fish_id)
  DO UPDATE SET seed_batch_id = EXCLUDED.seed_batch_id,
                updated_at    = EXCLUDED.updated_at;
  RETURN NULL;
END
$$;


--
-- Name: to_base36(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.to_base36(n integer) RETURNS text
    LANGUAGE plpgsql IMMUTABLE
    AS $$
DECLARE
    digits TEXT := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    result TEXT := '';
    remainder INT;
    num INT := n;
BEGIN
    IF n < 0 THEN
        RAISE EXCEPTION 'Negative values not supported';
    ELSIF n = 0 THEN
        RETURN '0';
    END IF;

    WHILE num > 0 LOOP
        remainder := num % 36;
        result := substr(digits, remainder + 1, 1) || result;
        num := num / 36;
    END LOOP;

    RETURN result;
END;
$$;


--
-- Name: transgene_alleles_autofill(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.transgene_alleles_autofill() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
  if new.allele_number is null then
    new.allele_number := nextval('public.transgene_allele_number_seq')::int;
  end if;
  new.allele_name := 'gu' || new.allele_number::text;
  return new;
end;
$$;


--
-- Name: FUNCTION transgene_alleles_autofill(); Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON FUNCTION public.transgene_alleles_autofill() IS 'Fill allele_number from global sequence iff NULL; set allele_name=''gu''||allele_number.';


--
-- Name: trg_cit_on_insert_copy_template(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_cit_on_insert_copy_template() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
  perform public._copy_plan_treatments_to_cit(new.id);
  return new;
end
$$;


--
-- Name: trg_clutch_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_clutch_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.clutch_code IS NULL OR btrim(NEW.clutch_code) = '' THEN
    NEW.clutch_code := public.gen_clutch_code();
  END IF;
  RETURN NEW;
END$$;


--
-- Name: trg_clutch_instance_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_clutch_instance_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN IF NEW.clutch_instance_code IS NULL OR btrim(NEW.clutch_instance_code)='' THEN NEW.clutch_instance_code:=public.gen_clutch_instance_code(); END IF; RETURN NEW; END;
$$;


--
-- Name: trg_clutch_instance_code_fill(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_clutch_instance_code_fill() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
declare
  v_run  text;
  v_base text;
  v_code text;
  i      int := 1;
begin
  if new.clutch_instance_code is not null and btrim(new.clutch_instance_code) <> '' then
    return new;
  end if;

  -- Get the cross run code for this clutch's cross_instance
  select ci.cross_run_code into v_run
  from public.cross_instances ci
  where ci.id = new.cross_instance_id;

  -- Build the base code; if no run (shouldn't happen), use a safe fallback
  v_base := 'CI-' || coalesce(v_run, 'UNSET');

  v_code := v_base;

  -- If the base already exists, append -02, -03, ... until unique
  while exists (select 1 from public.clutches c where c.clutch_instance_code = v_code) loop
    i := i + 1;
    v_code := v_base || '-' || lpad(i::text, 2, '0');
  end loop;

  new.clutch_instance_code := v_code;
  return new;
end$$;


--
-- Name: trg_clutch_instances_alloc_seq(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_clutch_instances_alloc_seq() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_next int;
  v_run text;
BEGIN
  IF NEW.seq IS NULL OR NEW.seq = 0 THEN
    INSERT INTO public.clutch_instance_seq(cross_instance_id, last)
    VALUES (NEW.cross_instance_id, 0)
    ON CONFLICT (cross_instance_id) DO UPDATE
      SET last = public.clutch_instance_seq.last + 1
    RETURNING last INTO v_next;

    NEW.seq := v_next::smallint;
  END IF;

  -- v_run already looks like "XR-2510001"; do NOT add another "XR-"
  SELECT cross_run_code INTO v_run
  FROM public.cross_instances
  WHERE id = NEW.cross_instance_id;

  NEW.clutch_instance_code := v_run || '-' || lpad(NEW.seq::text, 2, '0');
  RETURN NEW;
END
$$;


--
-- Name: trg_clutch_plans_set_expected(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_clutch_plans_set_expected() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
  if coalesce(new.expected_genotype,'') = '' then
    new.expected_genotype := public.gen_expected_genotype_label(new.mom_code, new.dad_code);
  end if;
  return new;
end$$;


--
-- Name: trg_clutches_set_birthday(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_clutches_set_birthday() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
declare dt date;
begin
  if new.date_birth is not null then
    return new;
  end if;

  if new.cross_instance_id is null then
    return new;
  end if;

  select (ci.cross_date + interval '1 day')::date
  into dt
  from public.cross_instances ci
  where ci.id = new.cross_instance_id;

  if dt is not null then
    new.date_birth := dt;
  end if;

  return new;
end$$;


--
-- Name: trg_clutches_set_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_clutches_set_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
declare cr text;
begin
  if new.cross_instance_id is null then
    return new;
  end if;

  if tg_op = 'INSERT'
     or new.cross_instance_id is distinct from old.cross_instance_id
     or new.clutch_instance_code is null
     or new.clutch_instance_code !~ '^CI-CR-' then
    select cross_run_code into cr
    from public.cross_instances
    where id = new.cross_instance_id;

    if cr is not null then
      new.clutch_instance_code := 'CI-' || cr;
    end if;
  end if;

  return new;
end$$;


--
-- Name: trg_clutches_set_expected(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_clutches_set_expected() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
declare m text; d text;
begin
  if coalesce(new.expected_genotype,'') <> '' then
    return new;
  end if;

  if new.cross_instance_id is null then
    return new;
  end if;

  select x.mother_code, x.father_code
  into m, d
  from public.cross_instances ci
  join public.crosses x on x.id = ci.cross_id
  where ci.id = new.cross_instance_id;

  if m is not null and d is not null then
    new.expected_genotype := public.gen_expected_genotype_label(m, d);
  end if;

  return new;
end$$;


--
-- Name: trg_containers_activate_on_label(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_containers_activate_on_label() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF TG_OP = 'UPDATE'
     AND OLD.status = 'new_tank'
     AND NEW.label IS NOT NULL
     AND NEW.label IS DISTINCT FROM OLD.label THEN
    NEW.status := 'active';
    NEW.status_changed_at := now();
  END IF;
  RETURN NEW;
END
$$;


--
-- Name: trg_cp_require_planned_crosses(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_cp_require_planned_crosses() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
declare
  v_has int;
begin
  if (TG_OP = 'UPDATE') and (OLD.status = 'draft') and (NEW.status <> 'draft') then
    select count(*) into v_has
    from public.planned_crosses pc
    where pc.clutch_id = NEW.id
      and pc.cross_id is not null;
    if coalesce(v_has,0) = 0 then
      raise exception 'Cannot set status %: no planned_crosses with cross_id for clutch_plan %',
        NEW.status, NEW.clutch_code
        using errcode = '23514';
    end if;
  end if;
  return NEW;
end
$$;


--
-- Name: trg_cross_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_cross_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN IF NEW.cross_code IS NULL OR btrim(NEW.cross_code)='' THEN NEW.cross_code:=public.gen_cross_code(); END IF; RETURN NEW; END;
$$;


--
-- Name: trg_cross_code_fill(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_cross_code_fill() RETURNS trigger
    LANGUAGE plpgsql
    AS $_$
begin
  if NEW.cross_code is null
     or NEW.cross_code !~ '^CROSS-[0-9A-Z]{2}[0-9A-Z]{4,}$' then
    NEW.cross_code := public.gen_cross_code();
  end if;
  return NEW;
end$_$;


--
-- Name: trg_cross_code_normalize(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_cross_code_normalize() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  -- Normalize unconditionally; other BEFORE triggers may set NEW.cross_code
  NEW.cross_code := public.normalize_cross_code(NEW.cross_code);
  RETURN NEW;
END
$$;


--
-- Name: trg_cross_instances_set_codes(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_cross_instances_set_codes() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
declare tp_code text;
declare next_run int;
begin
  if new.tank_pair_id is null then
    return new;
  end if;

  select tank_pair_code into tp_code
  from public.tank_pairs
  where id = new.tank_pair_id;

  if tp_code is null then
    raise exception 'tank_pair not found for %', new.tank_pair_id;
  end if;

  if new.run_number is null then
    select coalesce(max(run_number), 0) + 1
    into next_run
    from public.cross_instances
    where tank_pair_id = new.tank_pair_id;
    new.run_number := next_run;
  end if;

  if new.cross_run_code is null or new.cross_run_code = '' then
    new.cross_run_code := 'CR-' || tp_code || '-' || new.run_number::text;
  end if;

  return new;
end$$;


--
-- Name: trg_cross_name_fill(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_cross_name_fill() RETURNS trigger
    LANGUAGE plpgsql
    AS $_$
declare
  v_name text;
begin
  -- Prefer an explicit name if provided
  if NEW.cross_name is not null and btrim(NEW.cross_name) <> '' then
    return NEW;
  end if;

  -- Try cross_name_code (if table has it)
  begin
    execute 'select ($1).cross_name_code::text' into v_name using NEW;
  exception when undefined_column then
    v_name := null;
  end;

  if v_name is null or btrim(v_name) = '' then
    -- Try cross_code
    begin
      execute 'select ($1).cross_code::text' into v_name using NEW;
    exception when undefined_column then
      v_name := null;
    end;
  end if;

  if v_name is null or btrim(v_name) = '' then
    -- Try mother_code × father_code
    declare
      v_m text; v_d text;
    begin
      begin execute 'select ($1).mother_code::text' into v_m using NEW; exception when undefined_column then v_m := null; end;
      begin execute 'select ($1).father_code::text' into v_d using NEW; exception when undefined_column then v_d := null; end;
      if v_m is not null and v_d is not null then
        v_name := v_m || '×' || v_d;
      end if;
    end;
  end if;

  NEW.cross_name := coalesce(v_name, NEW.cross_name, '');
  return NEW;
end$_$;


--
-- Name: trg_cross_run_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_cross_run_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN IF NEW.cross_run_code IS NULL OR btrim(NEW.cross_run_code)='' THEN NEW.cross_run_code:=public.gen_cross_run_code(); END IF; RETURN NEW; END;
$$;


--
-- Name: trg_crosses_set_code_and_genotype(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_crosses_set_code_and_genotype() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
  new.cross_name_code := public.gen_cross_code_name(new.mother_code, new.father_code);
  if new.cross_name_genotype is null or btrim(new.cross_name_genotype) = '' then
    new.cross_name_genotype := public.gen_cross_genotype(new.mother_code, new.father_code);
  end if;
  return new;
end
$$;


--
-- Name: trg_crosses_set_cross_name(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_crosses_set_cross_name() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
  new.cross_name := public.gen_cross_name(new.mother_code, new.father_code);
  return new;
end
$$;


--
-- Name: trg_crosses_set_names(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_crosses_set_names() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
  new.cross_name := coalesce(new.cross_nickname, public.gen_cross_name(new.mother_code, new.father_code));
  return new;
end
$$;


--
-- Name: trg_fish_autotank(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_fish_autotank() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_label text := COALESCE(NEW.nickname, NEW.name, 'Holding Tank');
  v_container_id uuid;
  v_code text;
BEGIN
  -- Derive the tank_code from this fish's code
  v_code := public.gen_tank_code_for_fish(NEW.fish_code);

  -- Create holding tank with per-fish code
  INSERT INTO public.containers (container_type, status, label, tank_code, created_by)
  VALUES ('holding_tank', 'new_tank', v_label, v_code, COALESCE(NEW.created_by, 'system'))
  RETURNING id INTO v_container_id;

  -- Link fish → tank (handle schema variants)
  BEGIN
    INSERT INTO public.fish_tank_memberships (fish_id, container_id, started_at)
    VALUES (NEW.id, v_container_id, now());
  EXCEPTION WHEN undefined_column THEN
    INSERT INTO public.fish_tank_memberships (fish_id, container_id, joined_at)
    VALUES (NEW.id, v_container_id, now());
  END;

  RETURN NEW;
END
$$;


--
-- Name: trg_log_container_status(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_log_container_status() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.status IS DISTINCT FROM OLD.status THEN
    INSERT INTO public.container_status_history(container_id, old_status, new_status, changed_by, reason)
    VALUES (NEW.id_uuid, OLD.status, NEW.status, current_user, 'trigger');
  END IF;
  RETURN NEW;
END $$;


--
-- Name: trg_mounts_alloc_seq(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_mounts_alloc_seq() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_next int;
  v_run  text;
BEGIN
  -- Per-run seq for mount_code (unchanged)
  IF NEW.seq IS NULL OR NEW.seq = 0 THEN
    INSERT INTO public.mount_seq(cross_instance_id, last)
    VALUES (NEW.cross_instance_id, 0)
    ON CONFLICT (cross_instance_id) DO UPDATE
      SET last = public.mount_seq.last + 1
    RETURNING last INTO v_next;
    NEW.seq := v_next::smallint;
  END IF;

  -- Machine code: MT-<run>-NN
  SELECT cross_run_code INTO v_run FROM public.cross_instances WHERE id = NEW.cross_instance_id;
  NEW.mount_code := 'MT-' || v_run || '-' || lpad(NEW.seq::text, 2, '0');

  -- Day-global label: MT-YYYY-MM-DD #N
  INSERT INTO public.mount_label_seq_day(mount_date, last)
  VALUES (NEW.mount_date, 1)
  ON CONFLICT (mount_date) DO UPDATE
    SET last = public.mount_label_seq_day.last + 1
  RETURNING last INTO v_next;

  NEW.mount_label := 'MT-' || to_char(NEW.mount_date, 'YYYY-MM-DD') || ' #' || v_next::text;

  RETURN NEW;
END
$$;


--
-- Name: trg_plasmid_auto_ensure_rna(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_plasmid_auto_ensure_rna() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.supports_invitro_rna IS TRUE
     AND NEW.code IS NOT NULL
     AND btrim(NEW.code) <> '' THEN
    -- Call the helper; we don't need its return values here
    PERFORM public.ensure_rna_for_plasmid(NEW.code, '-RNA', NEW.name, NEW.created_by, NEW.notes);
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: trg_registry_fill_modern(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_registry_fill_modern() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.transgene_base_code IS NULL THEN
    NEW.transgene_base_code := NEW.base_code;
  END IF;
  IF NEW.allele_nickname IS NULL THEN
    NEW.allele_nickname := NEW.legacy_label;
  END IF;
  RETURN NEW;
END
$$;


--
-- Name: trg_set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END
$$;


--
-- Name: trg_tank_pairs_immutable_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_tank_pairs_immutable_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
  if new.tank_pair_code is distinct from old.tank_pair_code then
    raise exception 'tank_pair_code is immutable';
  end if;
  return new;
end$$;


--
-- Name: trg_tank_pairs_set_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_tank_pairs_set_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
  if new.tank_pair_code is null or new.tank_pair_code = '' then
    new.tank_pair_code := public.gen_tank_pair_code();
  end if;
  return new;
end$$;


--
-- Name: upsert_fish_by_batch_name_dob(text, text, date, text, text, text, text, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.upsert_fish_by_batch_name_dob(p_seed_batch_id text, p_name text, p_date_birth date, p_genetic_background text DEFAULT NULL::text, p_nickname text DEFAULT NULL::text, p_line_building_stage text DEFAULT NULL::text, p_description text DEFAULT NULL::text, p_notes text DEFAULT NULL::text, p_created_by text DEFAULT NULL::text) RETURNS TABLE(fish_id uuid, fish_code text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
declare
  v_id   uuid;
  v_code text;
begin
  -- try existing (batch, name, dob)
  select f.id, f.fish_code
    into v_id, v_code
  from public.fish f
  join public.fish_seed_batches_map m
    on m.fish_id = f.id
   and m.seed_batch_id = p_seed_batch_id
  where f.name = p_name
    and f.date_birth = p_date_birth
  limit 1;

  if v_id is not null then
    update public.fish
       set name                = coalesce(p_name, name),
           date_birth          = coalesce(p_date_birth, date_birth),
           genetic_background  = coalesce(p_genetic_background, genetic_background),
           nickname            = coalesce(p_nickname, nickname),
           line_building_stage = coalesce(p_line_building_stage, line_building_stage),
           description         = coalesce(p_description, description),
           notes               = coalesce(p_notes, notes),
           created_by          = coalesce(p_created_by, created_by)
     where id = v_id;

    return query select v_id, v_code;
  end if;

  -- insert new
  insert into public.fish (
    name, date_birth, genetic_background, nickname,
    line_building_stage, description, notes, created_by
  )
  values (
    p_name, p_date_birth, p_genetic_background, p_nickname,
    p_line_building_stage, p_description, p_notes, p_created_by
  )
  returning id, public.fish.fish_code
  into v_id, v_code;

  -- map to batch (idempotent)
  insert into public.fish_seed_batches_map (fish_id, seed_batch_id)
  values (v_id, p_seed_batch_id)
  on conflict do nothing;

  return query select v_id, v_code;
end;
$$;


--
-- Name: upsert_transgene_allele_label(text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.upsert_transgene_allele_label(p_base text, p_label text, OUT out_allele_number integer) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
  base_norm  text := btrim(p_base);
  label_norm text := nullif(btrim(p_label), '');
  k bigint := hashtextextended(base_norm, 0);
BEGIN
  IF base_norm IS NULL OR base_norm = '' THEN
    RAISE EXCEPTION 'base code required';
  END IF;

  -- 1) Reuse by allele_code (preferred)
  IF label_norm IS NOT NULL THEN
    SELECT ta.allele_number
      INTO out_allele_number
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = base_norm
      AND lower(btrim(ta.allele_code)) = lower(label_norm)
    LIMIT 1;
    IF FOUND THEN RETURN; END IF;

    -- 2) Reuse by allele_name (fallback)
    SELECT ta.allele_number
      INTO out_allele_number
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = base_norm
      AND lower(btrim(ta.allele_name)) = lower(label_norm)
    LIMIT 1;
    IF FOUND THEN
      -- ensure code is stored for next time
      UPDATE public.transgene_alleles
      SET allele_code = COALESCE(allele_code, label_norm)
      WHERE transgene_base_code = base_norm AND allele_number = out_allele_number;
      RETURN;
    END IF;
  END IF;

  -- 3) Allocate next number (race-safe per base)
  PERFORM pg_advisory_xact_lock(k);
  SELECT COALESCE(MAX(allele_number)+1, 1)
    INTO out_allele_number
  FROM public.transgene_alleles
  WHERE transgene_base_code = base_norm;

  INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, allele_code, allele_name)
  VALUES (base_norm, out_allele_number, label_norm, label_norm)
  ON CONFLICT (transgene_base_code, allele_number) DO NOTHING;

  RETURN;
END$$;


--
-- Name: upsert_transgene_allele_name(text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.upsert_transgene_allele_name(p_base text, p_name text, OUT out_allele_number integer) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
  base_norm text := btrim(p_base);
  name_norm text := nullif(btrim(p_name), '');
  k bigint := hashtextextended(base_norm, 0);
BEGIN
  IF base_norm IS NULL OR base_norm = '' THEN
    RAISE EXCEPTION 'base code required';
  END IF;

  -- Try to reuse by (base, name)
  IF name_norm IS NOT NULL THEN
    SELECT ta.allele_number
      INTO out_allele_number
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = base_norm
      AND lower(btrim(ta.allele_name)) = lower(name_norm)
    LIMIT 1;

    IF FOUND THEN
      RETURN; -- reuse existing number
    END IF;
  END IF;

  -- Allocate a new number with an advisory lock to avoid races
  PERFORM pg_advisory_xact_lock(k);

  SELECT COALESCE(MAX(allele_number)+1, 1)
    INTO out_allele_number
  FROM public.transgene_alleles
  WHERE transgene_base_code = base_norm;

  INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, allele_name)
  VALUES (base_norm, out_allele_number, name_norm)
  ON CONFLICT (transgene_base_code, allele_number) DO NOTHING;

  RETURN;
END$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: allele_nicknames; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.allele_nicknames (
    base_code text NOT NULL,
    allele_code text NOT NULL,
    allele_nickname text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: bruker_mount; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bruker_mount (
    mount_code text NOT NULL,
    mounting_orientation text NOT NULL,
    n_top integer DEFAULT 0 NOT NULL,
    n_bottom integer DEFAULT 0 NOT NULL,
    clutch_instance_id uuid,
    time_mounted timestamp with time zone DEFAULT now()
);


--
-- Name: bruker_mounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bruker_mounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    selection_id uuid NOT NULL,
    mount_date date NOT NULL,
    mount_time time without time zone NOT NULL,
    n_top integer NOT NULL,
    n_bottom integer NOT NULL,
    orientation text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    mount_code text,
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT bruker_mounts_n_bottom_check CHECK ((n_bottom >= 0)),
    CONSTRAINT bruker_mounts_n_top_check CHECK ((n_top >= 0)),
    CONSTRAINT bruker_mounts_orientation_check CHECK ((orientation = ANY (ARRAY['dorsal'::text, 'ventral'::text, 'left'::text, 'right'::text, 'front'::text, 'back'::text, 'other'::text])))
);


--
-- Name: clutch_containers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clutch_containers (
    container_id uuid NOT NULL,
    clutch_id uuid NOT NULL,
    is_mixed boolean DEFAULT true NOT NULL,
    selection_label text,
    source_container_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text NOT NULL,
    note text,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: clutch_genotype_options; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clutch_genotype_options (
    clutch_id uuid NOT NULL,
    allele_code text,
    transgene_base_code text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: clutch_instance_code_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.clutch_instance_code_seq
    START WITH 10000
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: clutch_instance_seq; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clutch_instance_seq (
    cross_instance_id uuid NOT NULL,
    last integer NOT NULL
);


--
-- Name: clutch_instance_treatments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clutch_instance_treatments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clutch_instance_id uuid NOT NULL,
    material_type text,
    material_code text,
    material_name text,
    notes text,
    created_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: clutch_instances; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clutch_instances (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    label text,
    phenotype text,
    notes text,
    red_selected boolean,
    red_intensity text,
    red_note text,
    green_selected boolean,
    green_intensity text,
    green_note text,
    annotated_by text,
    annotated_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    cross_instance_id uuid NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    birthday date,
    created_by text,
    seq smallint NOT NULL,
    clutch_instance_code text NOT NULL
);


--
-- Name: clutch_plan_treatments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clutch_plan_treatments (
    clutch_id uuid NOT NULL,
    material_type text NOT NULL,
    material_code text NOT NULL,
    material_name text,
    dose numeric,
    units text,
    at_hpf numeric,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    CONSTRAINT clutch_plan_treatments_material_type_check CHECK ((material_type = ANY (ARRAY['plasmid'::text, 'rna'::text])))
);


--
-- Name: clutch_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clutch_plans (
    mom_code text NOT NULL,
    dad_code text NOT NULL,
    cross_date date DEFAULT CURRENT_DATE NOT NULL,
    note text,
    created_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    planned_name text,
    planned_nickname text,
    clutch_code text,
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    status public.clutch_plan_status DEFAULT 'draft'::public.clutch_plan_status NOT NULL,
    expected_genotype text
);


--
-- Name: clutch_treatments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clutch_treatments (
    clutch_id uuid NOT NULL,
    type text NOT NULL,
    reagent_id uuid,
    amount numeric,
    units text,
    at_time timestamp with time zone,
    note text,
    created_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    CONSTRAINT clutch_treatments_type_check CHECK ((type = ANY (ARRAY['injected_plasmid'::text, 'injected_rna'::text])))
);


--
-- Name: clutches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clutches (
    cross_id uuid NOT NULL,
    batch_label text,
    seed_batch_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text NOT NULL,
    note text,
    date_birth date,
    run_id uuid,
    planned_cross_id uuid,
    cross_instance_id uuid,
    clutch_instance_code text NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clutch_code text,
    expected_genotype text
);


--
-- Name: container_status_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.container_status_history (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    container_id uuid NOT NULL,
    old_status public.container_status NOT NULL,
    new_status public.container_status NOT NULL,
    changed_at timestamp with time zone DEFAULT now() NOT NULL,
    changed_by text,
    reason text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: containers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.containers (
    container_type text NOT NULL,
    label text,
    status text DEFAULT 'planned'::public.container_status NOT NULL,
    created_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    note text,
    request_id uuid,
    status_changed_at timestamp with time zone DEFAULT now() NOT NULL,
    activated_at timestamp with time zone,
    deactivated_at timestamp with time zone,
    last_seen_at timestamp with time zone,
    last_seen_source text,
    tank_volume_l integer,
    tank_code text,
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    CONSTRAINT chk_containers_type_allowed CHECK ((container_type = ANY (ARRAY['inventory_tank'::text, 'crossing_tank'::text, 'holding_tank'::text, 'nursery_tank'::text, 'petri_dish'::text]))),
    CONSTRAINT chk_containers_volume_allowed CHECK (((tank_volume_l IS NULL) OR (tank_volume_l = ANY (ARRAY[2, 4, 8, 16])))),
    CONSTRAINT chk_tank_code_shape CHECK (((tank_code IS NULL) OR (tank_code ~ '^TANK FSH-[0-9A-Z]{2}[0-9A-Z]+ #[1-9][0-9]*$'::text))),
    CONSTRAINT containers_status_check CHECK ((status = ANY (ARRAY['planned'::text, 'new_tank'::text, 'active'::text, 'ready_to_kill'::text, 'inactive'::text])))
);


--
-- Name: cross_code_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cross_code_seq
    START WITH 10000
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cross_instances; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cross_instances (
    cross_id uuid NOT NULL,
    cross_date date DEFAULT CURRENT_DATE NOT NULL,
    mother_tank_id uuid,
    father_tank_id uuid,
    note text,
    created_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    cross_run_code text,
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clutch_birthday date GENERATED ALWAYS AS (((cross_date + '1 day'::interval))::date) STORED,
    tank_pair_id uuid,
    run_number integer
);


--
-- Name: COLUMN cross_instances.clutch_birthday; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.cross_instances.clutch_birthday IS 'Clutch birthday = cross_date + 1 day (stored generated column)';


--
-- Name: cross_parent_aliases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cross_parent_aliases (
    parent_code text NOT NULL,
    alias text NOT NULL
);


--
-- Name: cross_plan_genotype_alleles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cross_plan_genotype_alleles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    plan_id uuid NOT NULL,
    transgene_base_code text NOT NULL,
    allele_number integer NOT NULL,
    zygosity_planned text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: cross_plan_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cross_plan_runs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    plan_id uuid NOT NULL,
    seq integer NOT NULL,
    planned_date date NOT NULL,
    tank_a_id uuid,
    tank_b_id uuid,
    status text DEFAULT 'planned'::text NOT NULL,
    note text,
    created_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: cross_plan_treatments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cross_plan_treatments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    plan_id uuid NOT NULL,
    treatment_name text NOT NULL,
    amount numeric,
    units text,
    timing_note text,
    injection_mix text,
    treatment_notes text,
    rna_id uuid,
    plasmid_id uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT chk_cpt_one_reagent CHECK (((((rna_id IS NOT NULL))::integer + ((plasmid_id IS NOT NULL))::integer) <= 1))
);


--
-- Name: cross_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cross_plans (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    plan_date date NOT NULL,
    tank_a_id uuid,
    tank_b_id uuid,
    status public.cross_plan_status DEFAULT 'planned'::public.cross_plan_status NOT NULL,
    created_by text NOT NULL,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    mother_fish_id uuid,
    father_fish_id uuid,
    plan_title text,
    plan_nickname text,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: cross_run_code_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.cross_run_code_seq
    START WITH 10000
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: crosses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.crosses (
    mother_code text NOT NULL,
    father_code text NOT NULL,
    created_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    note text,
    planned_for date,
    cross_code text,
    cross_name_code text NOT NULL,
    cross_name_genotype text,
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    cross_name text,
    CONSTRAINT chk_cross_code_shape CHECK (((cross_code IS NULL) OR (cross_code ~ '^CROSS-[0-9A-Z]{2}[0-9A-Z]{4,}$'::text)))
);


--
-- Name: fish; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    fish_code text NOT NULL,
    name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    date_birth date,
    nickname text,
    line_building_stage text,
    genetic_background text,
    description text,
    notes text,
    updated_at timestamp with time zone DEFAULT now(),
    birthday date,
    CONSTRAINT chk_fish_code_shape CHECK (((fish_code IS NULL) OR (fish_code ~ '^FSH-[0-9A-Z]{2}[0-9A-Z]+$'::text))),
    CONSTRAINT ck_fish_fish_code_format CHECK ((fish_code ~ '^FSH-[0-9]{2}[0-9A-Z]{4,}$'::text))
);


--
-- Name: COLUMN fish.genetic_background; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.fish.genetic_background IS 'Background genetic strain (from CSV: genetic_background).';


--
-- Name: fish_code_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish_code_audit (
    id bigint NOT NULL,
    at timestamp with time zone DEFAULT now() NOT NULL,
    fish_id uuid,
    fish_code text,
    app_name text,
    client_addr inet,
    pid integer,
    note text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: fish_code_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fish_code_audit_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fish_code_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fish_code_audit_id_seq OWNED BY public.fish_code_audit.id;


--
-- Name: fish_code_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fish_code_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fish_csv; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.fish_csv AS
 SELECT fish_code,
    COALESCE(((row_to_json(f.*))::jsonb ->> 'name'::text), ''::text) AS name,
    COALESCE(((row_to_json(f.*))::jsonb ->> 'nickname'::text), ''::text) AS nickname,
    COALESCE(((row_to_json(f.*))::jsonb ->> 'genetic_background'::text), ''::text) AS genetic_background,
    birthday,
    COALESCE(((row_to_json(f.*))::jsonb ->> 'created_by'::text), ''::text) AS created_by,
    created_at
   FROM public.fish f;


--
-- Name: VIEW fish_csv; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON VIEW public.fish_csv IS 'Writable CSV import view: accepts columns (fish_code, name, nickname, genetic_background?, birthday, created_by). birthday maps to fish.birthday.';


--
-- Name: fish_pairs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish_pairs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    mom_fish_id uuid NOT NULL,
    dad_fish_id uuid NOT NULL,
    created_by text,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_fish_pair_order CHECK ((mom_fish_id <= dad_fish_id))
);


--
-- Name: fish_seed_batches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish_seed_batches (
    fish_id uuid NOT NULL,
    seed_batch_id text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: fish_seed_batches_map; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish_seed_batches_map (
    fish_id uuid NOT NULL,
    seed_batch_id text,
    logged_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: fish_tank_memberships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish_tank_memberships (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    fish_id uuid NOT NULL,
    container_id uuid NOT NULL,
    joined_at timestamp with time zone DEFAULT now() NOT NULL,
    left_at timestamp with time zone,
    note text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: fish_transgene_alleles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish_transgene_alleles (
    fish_id uuid NOT NULL,
    transgene_base_code text NOT NULL,
    allele_number integer NOT NULL,
    zygosity text,
    allele_nickname text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: fish_year_counters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish_year_counters (
    year integer NOT NULL,
    n bigint DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: injected_plasmid_treatments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.injected_plasmid_treatments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    fish_id uuid NOT NULL,
    plasmid_id uuid NOT NULL,
    amount numeric,
    units text,
    at_time timestamp with time zone,
    note text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: injected_rna_treatments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.injected_rna_treatments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    fish_id uuid NOT NULL,
    rna_id uuid NOT NULL,
    amount numeric,
    units text,
    at_time timestamp with time zone,
    note text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: label_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.label_items (
    job_id uuid NOT NULL,
    seq integer NOT NULL,
    fish_code text,
    tank_id uuid,
    request_id uuid,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    qr_text text,
    rendered_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    CONSTRAINT label_items_seq_check CHECK ((seq > 0))
);


--
-- Name: label_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.label_jobs (
    entity_type text NOT NULL,
    entity_id uuid,
    template text DEFAULT 'tank_2.4x1.5'::text NOT NULL,
    media text DEFAULT '2.4x1.5'::text NOT NULL,
    status text DEFAULT 'queued'::text NOT NULL,
    requested_by text NOT NULL,
    requested_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    error_text text,
    num_labels integer DEFAULT 0 NOT NULL,
    file_url text,
    file_bytes bytea,
    source_params jsonb DEFAULT '{}'::jsonb NOT NULL,
    notes text,
    dedupe_hash text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    CONSTRAINT label_jobs_num_labels_check CHECK ((num_labels >= 0)),
    CONSTRAINT label_jobs_status_check CHECK ((status = ANY (ARRAY['queued'::text, 'processing'::text, 'done'::text, 'error'::text, 'cancelled'::text])))
);


--
-- Name: load_log_fish; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.load_log_fish (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    fish_id uuid NOT NULL,
    seed_batch_id text NOT NULL,
    row_key text NOT NULL,
    logged_at timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: mount_label_seq_day; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mount_label_seq_day (
    mount_date date NOT NULL,
    last integer NOT NULL
);


--
-- Name: mount_seq; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mount_seq (
    cross_instance_id uuid NOT NULL,
    last integer NOT NULL
);


--
-- Name: mounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    cross_instance_id uuid NOT NULL,
    mount_date date NOT NULL,
    sample_id text NOT NULL,
    mount_type text,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    created_by text,
    time_mounted timestamp with time zone,
    mounting_orientation text,
    n_top integer DEFAULT 0,
    n_bottom integer DEFAULT 0,
    seq smallint NOT NULL,
    mount_code text NOT NULL,
    mount_label text NOT NULL,
    CONSTRAINT ck_mounts_n_bottom_nonneg CHECK (((n_bottom IS NULL) OR (n_bottom >= 0))),
    CONSTRAINT ck_mounts_n_top_nonneg CHECK (((n_top IS NULL) OR (n_top >= 0)))
);


--
-- Name: transgene_alleles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transgene_alleles (
    transgene_base_code text NOT NULL,
    allele_number integer NOT NULL,
    allele_nickname text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    allele_name text
);


--
-- Name: v_fish_label_fields; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_fish_label_fields AS
 SELECT fish_code,
    nickname,
    name,
    NULL::text AS base_code,
    NULL::text AS tg_nick,
    line_building_stage AS stage,
    date_birth AS dob,
    NULLIF(array_to_string(ARRAY( SELECT ((fa2.transgene_base_code || '^'::text) || (fa2.allele_number)::text)
           FROM public.fish_transgene_alleles fa2
          WHERE (fa2.fish_id = f.id)
          ORDER BY fa2.transgene_base_code, fa2.allele_number), '; '::text), ''::text) AS genotype,
    genetic_background
   FROM public.fish f;


--
-- Name: v_fish_live_counts; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_fish_live_counts AS
 SELECT f.fish_code,
    (count(*))::integer AS n_live
   FROM ((public.fish f
     JOIN public.fish_tank_memberships m ON (((m.fish_id = f.id) AND (m.left_at IS NULL))))
     JOIN public.containers c ON ((c.id = m.container_id)))
  WHERE ((c.status = ANY (ARRAY['active'::text, 'new_tank'::text])) AND (c.container_type = ANY (ARRAY['inventory_tank'::text, 'holding_tank'::text, 'nursery_tank'::text])))
  GROUP BY f.fish_code;


--
-- Name: VIEW v_fish_live_counts; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON VIEW public.v_fish_live_counts IS 'Live tank membership per fish_code, filtered to active/new_tank & relevant tank types.';


--
-- Name: vw_fish_overview_with_label; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_fish_overview_with_label AS
 WITH base AS (
         SELECT f.fish_code,
            f.name,
            f.nickname,
            f.line_building_stage,
            f.date_birth,
            f.genetic_background,
            f.created_by,
            f.created_at
           FROM public.fish f
        ), allele AS (
         SELECT DISTINCT ON (f2.fish_code) f2.fish_code,
            l.transgene_base_code,
            l.allele_number,
            ta.allele_nickname
           FROM ((public.fish_transgene_alleles l
             JOIN public.fish f2 ON ((f2.id = l.fish_id)))
             LEFT JOIN public.transgene_alleles ta ON (((ta.transgene_base_code = l.transgene_base_code) AND (ta.allele_number = l.allele_number))))
          ORDER BY f2.fish_code, l.transgene_base_code, l.allele_number
        ), batch AS (
         SELECT DISTINCT ON (f3.fish_code) f3.fish_code,
            m.seed_batch_id
           FROM (public.fish_seed_batches_map m
             JOIN public.fish f3 ON ((f3.id = m.fish_id)))
          ORDER BY f3.fish_code, m.logged_at DESC NULLS LAST, m.created_at DESC NULLS LAST
        )
 SELECT b.fish_code,
    b.name,
    b.nickname,
    b.line_building_stage,
    b.date_birth,
    b.genetic_background,
    b.created_by,
    b.created_at,
    a.transgene_base_code AS transgene_base_code_filled,
    (a.allele_number)::text AS allele_code_filled,
    a.allele_nickname AS allele_name_filled,
    batch.seed_batch_id,
    batch.seed_batch_id AS batch_label,
    COALESCE(b.nickname, ''::text) AS nickname_print,
    COALESCE(b.genetic_background, ''::text) AS genetic_background_print,
    COALESCE(b.line_building_stage, ''::text) AS line_building_stage_print,
    COALESCE(to_char((b.date_birth)::timestamp with time zone, 'YYYY-MM-DD'::text), ''::text) AS date_birth_print,
        CASE
            WHEN (a.transgene_base_code IS NULL) THEN ''::text
            WHEN (a.allele_number IS NOT NULL) THEN ((a.transgene_base_code || '-'::text) || (a.allele_number)::text)
            WHEN (a.allele_nickname IS NOT NULL) THEN ((a.transgene_base_code || ' '::text) || a.allele_nickname)
            ELSE a.transgene_base_code
        END AS genotype_print,
        CASE
            WHEN (b.date_birth IS NOT NULL) THEN (CURRENT_DATE - b.date_birth)
            ELSE NULL::integer
        END AS age_days,
        CASE
            WHEN (b.date_birth IS NOT NULL) THEN ((CURRENT_DATE - b.date_birth) / 7)
            ELSE NULL::integer
        END AS age_weeks,
    COALESCE(b.created_by, ''::text) AS created_by_enriched,
    NULL::text AS plasmid_injections_text,
    NULL::text AS rna_injections_text
   FROM ((base b
     LEFT JOIN allele a USING (fish_code))
     LEFT JOIN batch USING (fish_code))
  ORDER BY b.fish_code;


--
-- Name: vw_fish_standard; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_fish_standard AS
 WITH base AS (
         SELECT f.id,
            f.fish_code,
            COALESCE(f.name, ''::text) AS name,
            COALESCE(f.nickname, ''::text) AS nickname,
            f.date_birth,
            f.created_at,
            COALESCE(f.created_by, ''::text) AS created_by_raw
           FROM public.fish f
        ), label AS (
         SELECT v.fish_code,
            v.genotype_print AS genotype,
            COALESCE(v.genetic_background_print, v.genetic_background) AS genetic_background,
            COALESCE(v.line_building_stage, v.line_building_stage_print) AS stage,
            v.batch_label,
            v.seed_batch_id,
            v.transgene_base_code_filled AS transgene_base_code,
            v.allele_code_filled AS allele_code,
            v.created_by_enriched,
            NULLIF(v.plasmid_injections_text, ''::text) AS plasmid_injections_text,
            NULLIF(v.rna_injections_text, ''::text) AS rna_injections_text
           FROM public.vw_fish_overview_with_label v
        ), tank_counts AS (
         SELECT m.fish_id,
            (count(*))::integer AS n_living_tanks
           FROM (public.fish_tank_memberships m
             JOIN public.containers c ON ((c.id = m.container_id)))
          WHERE ((m.left_at IS NULL) AND (c.container_type = 'inventory_tank'::text) AND (c.deactivated_at IS NULL) AND (COALESCE(c.status, ''::text) = ANY (ARRAY['active'::text, 'planned'::text])))
          GROUP BY m.fish_id
        ), roll AS (
         SELECT l1.fish_code,
            TRIM(BOTH '; '::text FROM concat_ws('; '::text,
                CASE
                    WHEN (l1.plasmid_injections_text IS NOT NULL) THEN ('plasmid: '::text || l1.plasmid_injections_text)
                    ELSE NULL::text
                END,
                CASE
                    WHEN (l1.rna_injections_text IS NOT NULL) THEN ('RNA: '::text || l1.rna_injections_text)
                    ELSE NULL::text
                END)) AS treatments_rollup
           FROM label l1
        )
 SELECT b.id,
    b.fish_code,
    b.name,
    b.nickname,
    l.genotype,
    l.genetic_background,
    l.stage,
    b.date_birth,
    (CURRENT_DATE - b.date_birth) AS age_days,
    b.created_at,
    COALESCE(l.created_by_enriched, b.created_by_raw) AS created_by,
    COALESCE(l.batch_label, l.seed_batch_id) AS batch_display,
    l.transgene_base_code,
    l.allele_code,
    r.treatments_rollup,
    COALESCE(t.n_living_tanks, 0) AS n_living_tanks
   FROM (((base b
     LEFT JOIN label l USING (fish_code))
     LEFT JOIN roll r USING (fish_code))
     LEFT JOIN tank_counts t ON ((t.fish_id = b.id)));


--
-- Name: v_fish_standard_clean; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_fish_standard_clean AS
 WITH vs AS (
         SELECT vw_fish_standard.id,
            vw_fish_standard.fish_code,
            vw_fish_standard.name,
            vw_fish_standard.nickname,
            vw_fish_standard.genotype,
            vw_fish_standard.genetic_background,
            vw_fish_standard.stage,
            vw_fish_standard.date_birth,
            vw_fish_standard.age_days,
            vw_fish_standard.created_at,
            vw_fish_standard.created_by,
            vw_fish_standard.batch_display,
            vw_fish_standard.transgene_base_code,
            vw_fish_standard.allele_code,
            vw_fish_standard.treatments_rollup,
            vw_fish_standard.n_living_tanks
           FROM public.vw_fish_standard
        ), src AS (
         SELECT f.fish_code,
            COALESCE(vs.genotype, ''::text) AS genotype,
            COALESCE(vs.genetic_background, ''::text) AS genetic_background,
            vs.date_birth AS birthday,
            COALESCE((to_jsonb(vs.*) ->> 'transgene_base_code'::text), (to_jsonb(vs.*) ->> 'transgene'::text), (to_jsonb(vs.*) ->> 'transgene_print'::text), ''::text) AS transgene_base,
            f.created_at,
            COALESCE(f.created_by, ''::text) AS created_by,
            COALESCE(f.name, ''::text) AS fish_name_base,
            COALESCE(f.nickname, ''::text) AS fish_nickname_base
           FROM (public.fish f
             LEFT JOIN vs ON ((vs.fish_code = f.fish_code)))
        ), joined AS (
         SELECT s.fish_code,
            s.genotype,
            s.genetic_background,
            s.birthday,
            s.transgene_base,
            s.created_at,
            s.created_by,
            s.fish_name_base,
            s.fish_nickname_base,
            l.name AS name_labeled,
            l.nickname AS nickname_labeled
           FROM (src s
             LEFT JOIN public.v_fish_label_fields l ON ((l.fish_code = s.fish_code)))
        ), fmt AS (
         SELECT joined.fish_code,
            COALESCE(joined.name_labeled, joined.fish_name_base) AS name,
            COALESCE(joined.nickname_labeled, joined.fish_nickname_base) AS nickname,
            joined.genotype,
            joined.genetic_background,
            joined.birthday,
            joined.transgene_base,
            joined.created_at,
            joined.created_by
           FROM joined
        ), roll AS (
         SELECT f.fish_code,
            f.name,
            f.nickname,
            f.genotype,
            f.genetic_background,
            f.birthday,
            f.transgene_base,
            f.created_at,
            f.created_by,
            ta.allele_nickname,
            ta.allele_number,
            ta.allele_name,
            TRIM(BOTH FROM regexp_replace(concat_ws(' '::text,
                CASE
                    WHEN (NULLIF(f.transgene_base, ''::text) IS NOT NULL) THEN (f.transgene_base ||
                    CASE
                        WHEN (ta.allele_number IS NOT NULL) THEN (('('::text || (ta.allele_number)::text) || ')'::text)
                        ELSE ''::text
                    END)
                    ELSE NULL::text
                END), '\s+'::text, ' '::text, 'g'::text)) AS genotype_rollup_clean
           FROM (fmt f
             LEFT JOIN public.transgene_alleles ta ON ((ta.transgene_base_code = f.transgene_base)))
        )
 SELECT fish_code,
    name,
    nickname,
    genotype,
    genetic_background,
    birthday,
    transgene_base,
    allele_number,
    allele_name,
    allele_nickname,
        CASE
            WHEN ((NULLIF(transgene_base, ''::text) IS NOT NULL) AND (NULLIF(COALESCE(allele_nickname, ''::text), ''::text) IS NOT NULL)) THEN ((('Tg('::text || transgene_base) || ')'::text) || allele_nickname)
            ELSE ''::text
        END AS transgene_pretty_nickname,
        CASE
            WHEN ((NULLIF(transgene_base, ''::text) IS NOT NULL) AND (NULLIF(COALESCE(allele_name, ''::text), ''::text) IS NOT NULL)) THEN ((('Tg('::text || transgene_base) || ')'::text) || allele_name)
            ELSE ''::text
        END AS transgene_pretty_name,
    genotype_rollup_clean,
    created_at,
    created_by
   FROM roll;


--
-- Name: VIEW v_fish_standard_clean; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON VIEW public.v_fish_standard_clean IS 'Clean fish overview with name/nickname; includes genotype/background/birthday/transgene_base, allele fields, pretty strings, background-free rollup, and audit fields.';


--
-- Name: v_fish_search; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_fish_search AS
 SELECT f.fish_code,
    lower(((COALESCE(sc.genotype, ''::text) || ' '::text) || COALESCE(sc.genetic_background, ''::text))) AS txt,
    COALESCE(sc.genotype, ''::text) AS genotype,
    COALESCE(sc.genetic_background, ''::text) AS genetic_background,
    COALESCE(l.n_live, 0) AS n_live
   FROM ((public.fish f
     LEFT JOIN public.v_fish_standard_clean sc ON ((sc.fish_code = f.fish_code)))
     LEFT JOIN public.v_fish_live_counts l ON ((l.fish_code = f.fish_code)));


--
-- Name: mv_fish_search; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.mv_fish_search AS
 SELECT DISTINCT ON (fish_code) fish_code,
    txt,
    genotype,
    genetic_background,
    n_live
   FROM public.v_fish_search
  ORDER BY fish_code, n_live DESC, genotype, txt
  WITH NO DATA;


--
-- Name: mv_overview_clutches_daily; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.mv_overview_clutches_daily AS
 SELECT COALESCE((annotated_at)::date, (created_at)::date) AS annot_day,
    count(*) AS annotations_count,
    max(COALESCE(annotated_at, created_at)) AS last_annotated
   FROM public.clutch_instances ci
  GROUP BY COALESCE((annotated_at)::date, (created_at)::date)
  ORDER BY COALESCE((annotated_at)::date, (created_at)::date) DESC
  WITH NO DATA;


--
-- Name: planned_crosses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.planned_crosses (
    clutch_id uuid,
    mom_code text NOT NULL,
    dad_code text NOT NULL,
    crossing_tank_id uuid,
    cross_date date DEFAULT CURRENT_DATE NOT NULL,
    note text,
    created_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    mother_tank_id uuid,
    father_tank_id uuid,
    cross_code text,
    cross_id uuid NOT NULL,
    cross_instance_id uuid,
    is_canonical boolean DEFAULT true NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    name text,
    nickname text,
    planned_for date,
    status text,
    notes text,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: mv_overview_crosses_daily; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.mv_overview_crosses_daily AS
 SELECT ci.cross_date AS run_day,
    count(*) AS runs_count,
    count(DISTINCT pc.clutch_id) AS clutches_count,
    max(ci.cross_date) AS last_run_date
   FROM (public.cross_instances ci
     JOIN public.planned_crosses pc ON ((pc.cross_id = ci.cross_id)))
  GROUP BY ci.cross_date
  ORDER BY ci.cross_date DESC
  WITH NO DATA;


--
-- Name: mv_overview_fish_daily; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.mv_overview_fish_daily AS
 SELECT (created_at)::date AS fish_day,
    count(*) AS fish_created,
    sum(
        CASE
            WHEN (date_birth = (created_at)::date) THEN 1
            ELSE 0
        END) AS births_logged,
    max(created_at) AS last_created
   FROM public.fish f
  GROUP BY ((created_at)::date)
  ORDER BY ((created_at)::date) DESC
  WITH NO DATA;


--
-- Name: mv_overview_mounts_daily; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.mv_overview_mounts_daily AS
 WITH base AS (
         SELECT m.mount_date AS mount_day,
            m.id AS mount_id,
            m.cross_instance_id,
            COALESCE(m.n_top, 0) AS n_top,
            COALESCE(m.n_bottom, 0) AS n_bottom,
            m.mounting_orientation AS orientation,
            m.time_mounted,
            m.created_at
           FROM public.mounts m
        ), ctx AS (
         SELECT b.mount_day,
            b.mount_id,
            b.cross_instance_id,
            b.n_top,
            b.n_bottom,
            b.orientation,
            b.time_mounted,
            b.created_at,
            cp.clutch_code
           FROM (((base b
             JOIN public.cross_instances ci ON ((ci.id = b.cross_instance_id)))
             JOIN public.planned_crosses pc ON ((pc.cross_id = ci.cross_id)))
             JOIN public.clutch_plans cp ON ((cp.id = pc.clutch_id)))
        ), hist AS (
         SELECT c.mount_day,
            c.orientation,
            count(*) AS cnt
           FROM ctx c
          GROUP BY c.mount_day, c.orientation
        )
 SELECT ctx.mount_day,
    count(*) AS mounts_count,
    sum((ctx.n_top + ctx.n_bottom)) AS embryos_total_sum,
    count(DISTINCT ctx.cross_instance_id) AS runs_count,
    count(DISTINCT ctx.clutch_code) AS clutches_count,
    COALESCE(jsonb_object_agg(hist.orientation, hist.cnt) FILTER (WHERE (hist.orientation IS NOT NULL)), '{}'::jsonb) AS orientations_json,
    max(ctx.time_mounted) AS last_time_mounted
   FROM (ctx
     LEFT JOIN hist ON ((hist.mount_day = ctx.mount_day)))
  GROUP BY ctx.mount_day
  ORDER BY ctx.mount_day DESC
  WITH NO DATA;


--
-- Name: plasmids; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plasmids (
    code text NOT NULL,
    name text,
    nickname text,
    fluors text,
    resistance text,
    supports_invitro_rna boolean DEFAULT false NOT NULL,
    created_by text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: mv_overview_plasmids_daily; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.mv_overview_plasmids_daily AS
 SELECT (created_at)::date AS plasmid_day,
    count(*) AS plasmids_created,
    max(created_at) AS last_created
   FROM public.plasmids p
  GROUP BY ((created_at)::date)
  ORDER BY ((created_at)::date) DESC
  WITH NO DATA;


--
-- Name: mv_overview_tanks_daily; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.mv_overview_tanks_daily AS
 WITH base AS (
         SELECT (c.created_at)::date AS tank_day,
            c.id,
            c.status,
            c.activated_at,
            c.last_seen_at,
            c.created_at
           FROM public.containers c
          WHERE (c.container_type = ANY (ARRAY['inventory_tank'::text, 'holding_tank'::text, 'nursery_tank'::text]))
        )
 SELECT tank_day,
    count(*) AS tanks_created,
    sum(
        CASE
            WHEN (status = 'active'::text) THEN 1
            ELSE 0
        END) AS active_count,
    sum(
        CASE
            WHEN ((activated_at)::date = tank_day) THEN 1
            ELSE 0
        END) AS activated_count,
    max(last_seen_at) AS last_seen_at,
    max(created_at) AS last_created
   FROM base
  GROUP BY tank_day
  ORDER BY tank_day DESC
  WITH NO DATA;


--
-- Name: plasmid_registry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plasmid_registry (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    plasmid_code text NOT NULL,
    plasmid_nickname text,
    backbone text,
    insert_desc text,
    vendor text,
    lot_number text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: rna_registry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rna_registry (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    rna_code text NOT NULL,
    rna_nickname text,
    vendor text,
    lot_number text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: rnas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rnas (
    code text NOT NULL,
    name text,
    source_plasmid_id uuid,
    created_by text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: seed_batches; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.seed_batches AS
 SELECT NULL::text AS seed_batch_id,
    NULL::text AS batch_label
  WHERE false;


--
-- Name: selection_labels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.selection_labels (
    code text NOT NULL,
    display_name text NOT NULL,
    color_hex text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: seq_clutch_code; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.seq_clutch_code
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: seq_cross_code; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.seq_cross_code
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: seq_tank_pair_code; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.seq_tank_pair_code
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tank_code_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tank_code_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tank_pairs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tank_pairs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    concept_id uuid,
    fish_pair_id uuid NOT NULL,
    mother_tank_id uuid NOT NULL,
    father_tank_id uuid NOT NULL,
    status text DEFAULT 'selected'::text NOT NULL,
    created_by text,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    tank_pair_code text NOT NULL
);


--
-- Name: tank_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tank_requests (
    fish_id uuid NOT NULL,
    requested_count integer NOT NULL,
    fulfilled_count integer DEFAULT 0 NOT NULL,
    requested_for date,
    note text,
    status text DEFAULT 'open'::text NOT NULL,
    created_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    CONSTRAINT tank_requests_fulfilled_count_check CHECK ((fulfilled_count >= 0)),
    CONSTRAINT tank_requests_requested_count_check CHECK ((requested_count > 0)),
    CONSTRAINT tank_requests_status_check CHECK ((status = ANY (ARRAY['open'::text, 'fulfilled'::text, 'cancelled'::text])))
);


--
-- Name: tank_year_counters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tank_year_counters (
    year integer NOT NULL,
    n bigint DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: transgene_allele_counters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transgene_allele_counters (
    transgene_base_code text NOT NULL,
    next_number integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: transgene_allele_number_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transgene_allele_number_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transgene_allele_number_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transgene_allele_number_seq OWNED BY public.transgene_alleles.allele_number;


--
-- Name: SEQUENCE transgene_allele_number_seq; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON SEQUENCE public.transgene_allele_number_seq IS 'Global allele_number sequence; owned by transgene_alleles.allele_number so RESTART IDENTITY resets it.';


--
-- Name: transgene_allele_registry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transgene_allele_registry (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    transgene_base_code text NOT NULL,
    allele_number integer NOT NULL,
    allele_nickname text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    base_code text,
    legacy_label text,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: transgenes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transgenes (
    transgene_base_code text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: v_cit_rollup; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_cit_rollup AS
 SELECT ci.clutch_instance_code,
    (count(*))::integer AS treatments_count,
    string_agg(((COALESCE(t.material_type, ''::text) || ':'::text) || COALESCE(t.material_code, ''::text)), '; '::text ORDER BY t.created_at DESC NULLS LAST) AS treatments_pretty
   FROM (public.clutch_instance_treatments t
     JOIN public.clutch_instances ci ON ((ci.id = t.clutch_instance_id)))
  GROUP BY ci.clutch_instance_code;


--
-- Name: v_clutch_annotations_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutch_annotations_summary AS
 WITH link AS (
         SELECT cl.id AS clutch_id,
            ci.id AS selection_id,
            ci.cross_instance_id,
            ci.created_at,
            ci.annotated_at,
            ci.annotated_by,
            COALESCE(ci.red_selected, false) AS red_selected,
            COALESCE(ci.green_selected, false) AS green_selected,
            NULLIF(btrim(ci.red_intensity), ''::text) AS red_intensity,
            NULLIF(btrim(ci.green_intensity), ''::text) AS green_intensity,
            NULLIF(btrim(ci.notes), ''::text) AS notes,
            NULLIF(btrim(ci.label), ''::text) AS label
           FROM ((public.clutches cl
             JOIN public.cross_instances x ON ((x.id = cl.cross_instance_id)))
             JOIN public.clutch_instances ci ON ((ci.cross_instance_id = x.id)))
        ), latest AS (
         SELECT DISTINCT ON (link.clutch_id) link.clutch_id,
            link.selection_id,
            link.cross_instance_id,
            link.created_at,
            link.annotated_at,
            link.annotated_by,
            link.red_selected,
            link.green_selected,
            link.red_intensity,
            link.green_intensity,
            link.notes,
            link.label
           FROM link
          ORDER BY link.clutch_id, COALESCE(link.annotated_at, link.created_at) DESC, link.created_at DESC, link.selection_id DESC
        ), annotators AS (
         SELECT s.clutch_id,
            string_agg(s.annotated_by_txt, ', '::text ORDER BY s.annotated_by_txt) AS annotators
           FROM ( SELECT DISTINCT link.clutch_id,
                    COALESCE(link.annotated_by, ''::text) AS annotated_by_txt
                   FROM link
                  WHERE ((link.annotated_by IS NOT NULL) AND (btrim(link.annotated_by) <> ''::text))) s
          GROUP BY s.clutch_id
        ), agg AS (
         SELECT l.clutch_id,
            (count(*))::integer AS annotations_count,
            max(COALESCE(l.annotated_at, l.created_at)) AS last_annotated_at,
            (sum(
                CASE
                    WHEN l.red_selected THEN 1
                    ELSE 0
                END))::integer AS red_selected_count,
            (sum(
                CASE
                    WHEN l.green_selected THEN 1
                    ELSE 0
                END))::integer AS green_selected_count
           FROM link l
          GROUP BY l.clutch_id
        ), rollup AS (
         SELECT lt.clutch_id,
                CASE
                    WHEN lt.red_selected THEN ('red:'::text || COALESCE(lt.red_intensity, 'selected'::text))
                    ELSE ''::text
                END AS red_part,
                CASE
                    WHEN lt.green_selected THEN ('green:'::text || COALESCE(lt.green_intensity, 'selected'::text))
                    ELSE ''::text
                END AS green_part,
                CASE
                    WHEN (lt.notes IS NOT NULL) THEN ('note:'::text || "left"(lt.notes, 120))
                    ELSE ''::text
                END AS note_part
           FROM latest lt
        ), rollup_fmt AS (
         SELECT r.clutch_id,
            (
                CASE
                    WHEN ((NULLIF(r.red_part, ''::text) IS NOT NULL) OR (NULLIF(r.green_part, ''::text) IS NOT NULL)) THEN array_to_string(ARRAY[NULLIF(r.red_part, ''::text), NULLIF(r.green_part, ''::text)], ' ; '::text)
                    ELSE ''::text
                END ||
                CASE
                    WHEN (NULLIF(r.note_part, ''::text) IS NOT NULL) THEN
                    CASE
                        WHEN ((NULLIF(r.red_part, ''::text) IS NOT NULL) OR (NULLIF(r.green_part, ''::text) IS NOT NULL)) THEN (', '::text || r.note_part)
                        ELSE r.note_part
                    END
                    ELSE ''::text
                END) AS annotation_rollup
           FROM rollup r
        )
 SELECT a.clutch_id,
    COALESCE(a.annotations_count, 0) AS annotations_count,
    a.last_annotated_at,
    COALESCE(n.annotators, ''::text) AS annotators,
    COALESCE(a.red_selected_count, 0) AS red_selected_count,
    COALESCE(a.green_selected_count, 0) AS green_selected_count,
    COALESCE(rf.annotation_rollup, ''::text) AS annotation_rollup
   FROM ((agg a
     LEFT JOIN annotators n ON ((n.clutch_id = a.clutch_id)))
     LEFT JOIN rollup_fmt rf ON ((rf.clutch_id = a.clutch_id)));


--
-- Name: v_clutch_counts; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutch_counts AS
 WITH runs AS (
         SELECT cp_1.id AS clutch_id,
            cp_1.clutch_code,
            count(DISTINCT ci.id) AS runs_count,
            max(ci.cross_date) AS last_run_date,
            max(ci.clutch_birthday) AS last_birthday
           FROM ((public.clutch_plans cp_1
             LEFT JOIN public.planned_crosses pc ON ((pc.clutch_id = cp_1.id)))
             LEFT JOIN public.cross_instances ci ON ((ci.cross_id = pc.cross_id)))
          GROUP BY cp_1.id, cp_1.clutch_code
        ), ann AS (
         SELECT cp_1.id AS clutch_id,
            count(DISTINCT sel.id) AS annotations_count,
            max(sel.annotated_at) AS last_annotated_at
           FROM (((public.clutch_plans cp_1
             LEFT JOIN public.planned_crosses pc ON ((pc.clutch_id = cp_1.id)))
             LEFT JOIN public.cross_instances ci ON ((ci.cross_id = pc.cross_id)))
             LEFT JOIN public.clutch_instances sel ON ((sel.cross_instance_id = ci.id)))
          GROUP BY cp_1.id
        )
 SELECT cp.clutch_code,
    COALESCE(r.runs_count, (0)::bigint) AS runs_count,
    COALESCE(a.annotations_count, (0)::bigint) AS annotations_count,
    r.last_run_date,
    r.last_birthday,
    a.last_annotated_at
   FROM ((public.clutch_plans cp
     LEFT JOIN runs r ON ((r.clutch_id = cp.id)))
     LEFT JOIN ann a ON ((a.clutch_id = cp.id)));


--
-- Name: v_clutch_expected_genotype; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutch_expected_genotype AS
 SELECT cl.id AS clutch_id,
    COALESCE(cl.expected_genotype, public.gen_expected_genotype_label(x.mother_code, x.father_code)) AS expected_genotype
   FROM ((public.clutches cl
     LEFT JOIN public.cross_instances ci ON ((ci.id = cl.cross_instance_id)))
     LEFT JOIN public.crosses x ON ((x.id = ci.cross_id)));


--
-- Name: v_clutch_instance_treatments_effective; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutch_instance_treatments_effective AS
 WITH d AS (
         SELECT t.clutch_instance_id,
            lower(COALESCE(t.material_type, ''::text)) AS mt,
            lower(COALESCE(t.material_code, ''::text)) AS mc,
            max(t.created_at) AS last_at
           FROM public.clutch_instance_treatments t
          GROUP BY t.clutch_instance_id, (lower(COALESCE(t.material_type, ''::text))), (lower(COALESCE(t.material_code, ''::text)))
        )
 SELECT ci.id AS clutch_instance_id,
    (count(d.mc))::integer AS treatments_count_effective,
    COALESCE(string_agg(d.mc, ' + '::text ORDER BY d.last_at DESC), ''::text) AS treatments_pretty_effective
   FROM (public.clutch_instances ci
     LEFT JOIN d ON ((d.clutch_instance_id = ci.id)))
  GROUP BY ci.id;


--
-- Name: v_clutch_instances_annotations; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutch_instances_annotations AS
 SELECT id,
    COALESCE(label, ''::text) AS label,
    COALESCE(phenotype, ''::text) AS phenotype,
    COALESCE(notes, ''::text) AS notes,
    COALESCE(red_selected, false) AS red_selected,
    COALESCE(red_intensity, ''::text) AS red_intensity,
    COALESCE(red_note, ''::text) AS red_note,
    COALESCE(green_selected, false) AS green_selected,
    COALESCE(green_intensity, ''::text) AS green_intensity,
    COALESCE(green_note, ''::text) AS green_note,
    COALESCE(annotated_by, ''::text) AS annotated_by,
    annotated_at,
    created_at
   FROM public.clutch_instances;


--
-- Name: v_clutch_instances_overview; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutch_instances_overview AS
 SELECT ci.id AS cross_instance_id,
    ci.cross_run_code,
    ci.cross_date AS birthday,
    c.clutch_code,
    cl.id AS clutch_instance_id,
    cl.birthday AS clutch_birthday,
    cl.created_by AS clutch_created_by
   FROM ((public.cross_instances ci
     LEFT JOIN public.clutches c ON ((c.cross_instance_id = ci.id)))
     LEFT JOIN public.clutch_instances cl ON ((cl.cross_instance_id = ci.id)));


--
-- Name: v_clutch_treatments_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutch_treatments_summary AS
 WITH base AS (
         SELECT clutch_plan_treatments.clutch_id,
            clutch_plan_treatments.material_type,
            clutch_plan_treatments.material_code,
            COALESCE(NULLIF(btrim(clutch_plan_treatments.material_name), ''::text), clutch_plan_treatments.material_code) AS material_name,
            jsonb_build_object('type', clutch_plan_treatments.material_type, 'code', clutch_plan_treatments.material_code, 'name', COALESCE(NULLIF(btrim(clutch_plan_treatments.material_name), ''::text), clutch_plan_treatments.material_code)) AS obj
           FROM public.clutch_plan_treatments
        )
 SELECT clutch_id,
    (count(*))::integer AS treatments_count,
    string_agg(DISTINCT material_code, ' ; '::text ORDER BY material_code) AS treatments_pretty,
    jsonb_agg(DISTINCT obj ORDER BY obj) AS treatments_json
   FROM base
  GROUP BY clutch_id;


--
-- Name: v_fish_overview_all; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_fish_overview_all AS
 WITH clean0 AS (
         SELECT c.fish_code,
            COALESCE(c.genotype, ''::text) AS genotype,
            COALESCE(c.genetic_background, ''::text) AS genetic_background,
            c.birthday,
            COALESCE(c.transgene_base, ''::text) AS transgene_base,
            c.allele_number,
            COALESCE(c.allele_name, ''::text) AS allele_name,
            COALESCE(c.allele_nickname, ''::text) AS allele_nickname,
            COALESCE(c.transgene_pretty_nickname, ''::text) AS transgene_pretty_nickname,
            COALESCE(c.transgene_pretty_name, ''::text) AS transgene_pretty_name,
            COALESCE(c.genotype_rollup_clean, ''::text) AS genotype_rollup_clean,
            c.created_at,
            COALESCE(c.created_by, ''::text) AS created_by
           FROM public.v_fish_standard_clean c
        ), linked AS (
         SELECT f.fish_code,
            fta.transgene_base_code AS transgene_base,
            fta.allele_number
           FROM (public.fish_transgene_alleles fta
             JOIN public.fish f ON ((f.id = fta.fish_id)))
        ), clean AS (
         SELECT s.fish_code,
            s.genotype,
            s.genetic_background,
            s.birthday,
            s.transgene_base,
            s.allele_number,
            s.allele_name,
            s.allele_nickname,
            s.transgene_pretty_nickname,
            s.transgene_pretty_name,
            s.genotype_rollup_clean,
            s.created_at,
            s.created_by,
            s.rn
           FROM ( SELECT c0.fish_code,
                    c0.genotype,
                    c0.genetic_background,
                    c0.birthday,
                    c0.transgene_base,
                    c0.allele_number,
                    c0.allele_name,
                    c0.allele_nickname,
                    c0.transgene_pretty_nickname,
                    c0.transgene_pretty_name,
                    c0.genotype_rollup_clean,
                    c0.created_at,
                    c0.created_by,
                    row_number() OVER (PARTITION BY c0.fish_code, c0.transgene_base ORDER BY
                        CASE
                            WHEN (EXISTS ( SELECT 1
                               FROM linked l
                              WHERE ((l.fish_code = c0.fish_code) AND (l.transgene_base = c0.transgene_base) AND (l.allele_number = c0.allele_number)))) THEN 0
                            ELSE 1
                        END, (c0.allele_number IS NULL), c0.allele_number, c0.created_at DESC NULLS LAST) AS rn
                   FROM clean0 c0) s
          WHERE (s.rn = 1)
        ), fish_meta AS (
         SELECT f.fish_code,
            COALESCE(NULLIF(lv.name, ''::text), NULLIF(f.name, ''::text), ''::text) AS name,
            COALESCE(NULLIF(lv.nickname, ''::text), NULLIF(f.nickname, ''::text), ''::text) AS nickname,
            COALESCE(((row_to_json(f.*))::jsonb ->> 'line_building_stage'::text), ((row_to_json(f.*))::jsonb ->> 'line_building_stage_print'::text), ''::text) AS line_building_stage,
            COALESCE(((row_to_json(f.*))::jsonb ->> 'description'::text), ''::text) AS description,
            COALESCE(((row_to_json(f.*))::jsonb ->> 'notes'::text), ''::text) AS notes,
            COALESCE(f.created_by, ''::text) AS created_by_fish,
            f.created_at AS created_at_fish
           FROM (public.fish f
             LEFT JOIN public.v_fish_label_fields lv ON ((lv.fish_code = f.fish_code)))
        ), counts AS (
         SELECT v.fish_code,
            v.n_live
           FROM public.v_fish_live_counts v
        ), zyg AS (
         SELECT f.fish_code,
            fta.transgene_base_code AS transgene_base,
            COALESCE(fta.zygosity, ''::text) AS zygosity
           FROM (public.fish_transgene_alleles fta
             JOIN public.fish f ON ((f.id = fta.fish_id)))
        )
 SELECT COALESCE(cl.fish_code, fm.fish_code) AS fish_code,
    COALESCE(fm.name, ''::text) AS name,
    COALESCE(fm.nickname, ''::text) AS nickname,
    COALESCE(cl.genetic_background, ''::text) AS genetic_background,
    COALESCE(fm.line_building_stage, ''::text) AS line_building_stage,
    COALESCE(fm.description, ''::text) AS description,
    COALESCE(fm.notes, ''::text) AS notes,
    cl.birthday,
    COALESCE(cl.created_by, fm.created_by_fish, ''::text) AS created_by,
    COALESCE(cl.created_at, fm.created_at_fish) AS created_at,
    COALESCE(cl.transgene_base, ''::text) AS transgene_base,
    cl.allele_number,
    COALESCE(cl.allele_name, ''::text) AS allele_name,
    COALESCE(cl.allele_nickname, ''::text) AS allele_nickname,
    COALESCE(z.zygosity, ''::text) AS zygosity,
    COALESCE(cl.transgene_pretty_nickname, ''::text) AS transgene_pretty_nickname,
    COALESCE(cl.transgene_pretty_name, ''::text) AS transgene_pretty_name,
    COALESCE(cl.genotype, ''::text) AS genotype,
    COALESCE(cl.genotype_rollup_clean, ''::text) AS genotype_rollup_clean,
    COALESCE(cl.transgene_base, ''::text) AS transgene_base_code,
    COALESCE(cnt.n_live, 0) AS n_living_tanks
   FROM (((clean cl
     FULL JOIN fish_meta fm ON ((fm.fish_code = cl.fish_code)))
     LEFT JOIN counts cnt ON ((cnt.fish_code = COALESCE(cl.fish_code, fm.fish_code))))
     LEFT JOIN zyg z ON (((z.fish_code = COALESCE(cl.fish_code, fm.fish_code)) AND (z.transgene_base = cl.transgene_base))))
  ORDER BY COALESCE(cl.fish_code, fm.fish_code);


--
-- Name: VIEW v_fish_overview_all; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON VIEW public.v_fish_overview_all IS 'One row per fish_code with CSV meta (name/nickname/stage/description/notes/birthday/created_by), clean genetics/pretty/rollup, transgene_base/allele fields, zygosity for displayed base, and n_living_tanks.';


--
-- Name: v_clutches_overview_final; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutches_overview_final AS
 WITH mom AS (
         SELECT v.fish_code,
            string_agg(DISTINCT ((v.transgene_base_code || '-'::text) || v.allele_name), ' ; '::text ORDER BY ((v.transgene_base_code || '-'::text) || v.allele_name)) AS canonical,
            string_agg(DISTINCT COALESCE(v.transgene_pretty_name, v.transgene_pretty_nickname, (v.transgene_base_code || v.allele_name)), ' ; '::text ORDER BY COALESCE(v.transgene_pretty_name, v.transgene_pretty_nickname, (v.transgene_base_code || v.allele_name))) AS pretty,
            max(NULLIF(btrim(v.genetic_background), ''::text)) AS mom_strain
           FROM public.v_fish_overview_all v
          GROUP BY v.fish_code
        ), dad AS (
         SELECT v.fish_code,
            string_agg(DISTINCT ((v.transgene_base_code || '-'::text) || v.allele_name), ' ; '::text ORDER BY ((v.transgene_base_code || '-'::text) || v.allele_name)) AS canonical,
            string_agg(DISTINCT COALESCE(v.transgene_pretty_name, v.transgene_pretty_nickname, (v.transgene_base_code || v.allele_name)), ' ; '::text ORDER BY COALESCE(v.transgene_pretty_name, v.transgene_pretty_nickname, (v.transgene_base_code || v.allele_name))) AS pretty,
            max(NULLIF(btrim(v.genetic_background), ''::text)) AS dad_strain
           FROM public.v_fish_overview_all v
          GROUP BY v.fish_code
        ), core AS (
         SELECT cp.id AS clutch_plan_id,
            cl.id AS clutch_id,
            COALESCE(cl.clutch_instance_code, cl.clutch_code, cp.clutch_code, "left"((cl.id)::text, 8)) AS clutch_code,
            x.cross_code,
            cl.date_birth AS clutch_birthday,
            cp.cross_date AS date_planned,
            cp.created_by AS created_by_plan,
            cp.created_at AS created_at_plan,
            cl.created_by AS created_by_instance,
            cl.created_at AS created_at_instance,
            x.mother_code,
            x.father_code,
            cp.planned_name,
            cp.planned_nickname
           FROM (((public.clutches cl
             JOIN public.cross_instances ci ON ((ci.id = cl.cross_instance_id)))
             JOIN public.crosses x ON ((x.id = ci.cross_id)))
             LEFT JOIN public.clutch_plans cp ON ((cp.id = cl.planned_cross_id)))
        ), joined AS (
         SELECT c.clutch_plan_id,
            c.clutch_id,
            c.clutch_code,
            c.cross_code,
            c.clutch_birthday,
            c.date_planned,
            c.created_by_plan,
            c.created_at_plan,
            c.created_by_instance,
            c.created_at_instance,
            c.mother_code,
            c.father_code,
            c.planned_name,
            c.planned_nickname,
            concat_ws(' × '::text, NULLIF(m.pretty, ''::text), NULLIF(d.pretty, ''::text)) AS cross_name_pretty,
            concat_ws(' × '::text, NULLIF(m.canonical, ''::text), NULLIF(d.canonical, ''::text)) AS cross_name,
            NULLIF(m.pretty, ''::text) AS mom_genotype_raw,
            NULLIF(d.pretty, ''::text) AS dad_genotype_raw,
            COALESCE(m.mom_strain, '(unknown)'::text) AS mom_strain,
            COALESCE(d.dad_strain, '(unknown)'::text) AS dad_strain,
            gu.canonical_union AS clutch_genotype_canonical,
            gu.pretty_union AS clutch_genotype_pretty
           FROM (((core c
             LEFT JOIN mom m ON ((m.fish_code = c.mother_code)))
             LEFT JOIN dad d ON ((d.fish_code = c.father_code)))
             LEFT JOIN LATERAL ( WITH toks AS (
                         SELECT unnest(string_to_array(NULLIF(m.canonical, ''::text), ' ; '::text)) AS can,
                            unnest(string_to_array(NULLIF(m.pretty, ''::text), ' ; '::text)) AS pre
                        UNION ALL
                         SELECT unnest(string_to_array(NULLIF(d.canonical, ''::text), ' ; '::text)) AS unnest,
                            unnest(string_to_array(NULLIF(d.pretty, ''::text), ' ; '::text)) AS unnest
                        )
                 SELECT string_agg(DISTINCT toks.can, ' ; '::text ORDER BY toks.can) AS canonical_union,
                    string_agg(DISTINCT toks.pre, ' ; '::text ORDER BY toks.pre) AS pretty_union
                   FROM toks
                  WHERE ((COALESCE(toks.can, ''::text) <> ''::text) AND (COALESCE(toks.pre, ''::text) <> ''::text))) gu ON (true))
        )
 SELECT j.clutch_plan_id,
    j.clutch_id,
    j.clutch_code,
    j.cross_code,
    j.cross_name_pretty,
    j.cross_name,
    COALESCE(j.planned_name, j.clutch_genotype_pretty) AS clutch_name,
    COALESCE(j.planned_nickname, COALESCE(j.planned_name, j.clutch_genotype_pretty)) AS clutch_nickname,
    j.clutch_genotype_canonical,
    j.clutch_genotype_pretty,
    COALESCE(j.mom_genotype_raw, j.mother_code) AS mom_genotype,
    COALESCE(j.dad_genotype_raw, j.father_code) AS dad_genotype,
    j.mom_strain,
    j.dad_strain,
    public.gen_clutch_strain(j.mother_code, j.father_code) AS clutch_strain,
    concat_ws(' × '::text, NULLIF(j.mom_strain, ''::text), NULLIF(j.dad_strain, ''::text)) AS clutch_strain_pretty,
    COALESCE(t.treatments_count, 0) AS treatments_count,
    COALESCE(t.treatments_pretty, ''::text) AS treatments_pretty,
    COALESCE(t.treatments_json, '[]'::jsonb) AS treatments_json,
    COALESCE(a.annotations_count, 0) AS annotations_count,
    a.last_annotated_at,
    COALESCE(a.annotation_rollup, ''::text) AS annotation_rollup,
    j.clutch_birthday,
    j.date_planned,
    j.created_by_plan,
    j.created_at_plan,
    j.created_by_instance,
    j.created_at_instance
   FROM ((joined j
     LEFT JOIN public.v_clutch_treatments_summary t ON ((t.clutch_id = j.clutch_id)))
     LEFT JOIN public.v_clutch_annotations_summary a ON ((a.clutch_id = j.clutch_id)));


--
-- Name: v_clutches_overview_final_enriched; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutches_overview_final_enriched AS
 SELECT base.clutch_plan_id,
    base.clutch_id,
    base.clutch_code,
    base.cross_code,
    base.cross_name_pretty,
    base.cross_name,
    base.clutch_name,
    base.clutch_nickname,
    base.clutch_genotype_canonical,
    base.clutch_genotype_pretty,
    base.mom_genotype,
    base.dad_genotype,
    base.mom_strain,
    base.dad_strain,
    base.clutch_strain,
    base.clutch_strain_pretty,
    base.treatments_count,
    base.treatments_pretty,
    base.treatments_json,
    base.annotations_count,
    base.last_annotated_at,
    base.annotation_rollup,
    base.clutch_birthday,
    base.date_planned,
    base.created_by_plan,
    base.created_at_plan,
    base.created_by_instance,
    base.created_at_instance,
    COALESCE(cit.treatments_count, base.treatments_count) AS treatments_count_effective,
    COALESCE(cit.treatments_pretty, base.treatments_pretty) AS treatments_pretty_effective,
    TRIM(BOTH ' +'::text FROM ((COALESCE(base.clutch_genotype_pretty, ''::text) ||
        CASE
            WHEN ((COALESCE(cit.treatments_pretty, base.treatments_pretty) IS NOT NULL) AND (COALESCE(cit.treatments_pretty, base.treatments_pretty) <> ''::text)) THEN ' + '::text
            ELSE ''::text
        END) || COALESCE(cit.treatments_pretty, base.treatments_pretty, ''::text))) AS genotype_treatment_rollup_effective
   FROM (public.v_clutches_overview_final base
     LEFT JOIN public.v_cit_rollup cit ON ((cit.clutch_instance_code = base.clutch_code)));


--
-- Name: v_clutches_overview_effective; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutches_overview_effective AS
 WITH base AS (
         SELECT v_clutches_overview_final_enriched.clutch_plan_id,
            v_clutches_overview_final_enriched.clutch_id,
            v_clutches_overview_final_enriched.clutch_code,
            v_clutches_overview_final_enriched.cross_code,
            v_clutches_overview_final_enriched.cross_name_pretty,
            v_clutches_overview_final_enriched.cross_name,
            v_clutches_overview_final_enriched.clutch_name,
            v_clutches_overview_final_enriched.clutch_nickname,
            v_clutches_overview_final_enriched.clutch_genotype_canonical,
            v_clutches_overview_final_enriched.clutch_genotype_pretty,
            v_clutches_overview_final_enriched.mom_genotype,
            v_clutches_overview_final_enriched.dad_genotype,
            v_clutches_overview_final_enriched.mom_strain,
            v_clutches_overview_final_enriched.dad_strain,
            v_clutches_overview_final_enriched.clutch_strain,
            v_clutches_overview_final_enriched.clutch_strain_pretty,
            v_clutches_overview_final_enriched.treatments_count,
            v_clutches_overview_final_enriched.treatments_pretty,
            v_clutches_overview_final_enriched.treatments_json,
            v_clutches_overview_final_enriched.annotations_count,
            v_clutches_overview_final_enriched.last_annotated_at,
            v_clutches_overview_final_enriched.annotation_rollup,
            v_clutches_overview_final_enriched.clutch_birthday,
            v_clutches_overview_final_enriched.date_planned,
            v_clutches_overview_final_enriched.created_by_plan,
            v_clutches_overview_final_enriched.created_at_plan,
            v_clutches_overview_final_enriched.created_by_instance,
            v_clutches_overview_final_enriched.created_at_instance,
            v_clutches_overview_final_enriched.treatments_count_effective,
            v_clutches_overview_final_enriched.treatments_pretty_effective,
            v_clutches_overview_final_enriched.genotype_treatment_rollup_effective
           FROM public.v_clutches_overview_final_enriched
        ), ci_norm AS (
         SELECT ci.id,
                CASE
                    WHEN (ci.clutch_instance_code ~~ 'CI-%'::text) THEN regexp_replace(ci.clutch_instance_code, '-[0-9]{2}$'::text, ''::text)
                    ELSE ('CI-'::text || regexp_replace(ci.clutch_instance_code, '-[0-9]{2}$'::text, ''::text))
                END AS ci_join_code
           FROM public.clutch_instances ci
        )
 SELECT b.clutch_plan_id,
    b.clutch_id,
    b.clutch_code,
    b.cross_code,
    b.cross_name_pretty,
    b.cross_name,
    b.clutch_name,
    b.clutch_nickname,
    b.clutch_genotype_canonical,
    b.clutch_genotype_pretty,
    b.mom_genotype,
    b.dad_genotype,
    b.mom_strain,
    b.dad_strain,
    b.clutch_strain,
    b.clutch_strain_pretty,
    b.treatments_count,
    b.treatments_pretty,
    b.treatments_json,
    b.annotations_count,
    b.last_annotated_at,
    b.annotation_rollup,
    b.clutch_birthday,
    b.date_planned,
    b.created_by_plan,
    b.created_at_plan,
    b.created_by_instance,
    b.created_at_instance,
    b.treatments_count_effective,
    b.treatments_pretty_effective,
    b.genotype_treatment_rollup_effective,
        CASE
            WHEN (v.treatments_count_effective > 0) THEN v.treatments_count_effective
            ELSE b.treatments_count_effective
        END AS treatments_count_effective_eff,
        CASE
            WHEN ((v.treatments_count_effective > 0) AND (COALESCE(v.treatments_pretty_effective, ''::text) <> ''::text)) THEN v.treatments_pretty_effective
            ELSE b.treatments_pretty_effective
        END AS treatments_pretty_effective_eff,
        CASE
            WHEN (v.treatments_count_effective > 0) THEN TRIM(BOTH ' +'::text FROM concat_ws(' + '::text, b.clutch_genotype_pretty, v.treatments_pretty_effective))
            ELSE b.genotype_treatment_rollup_effective
        END AS genotype_treatment_rollup_effective_eff
   FROM ((base b
     LEFT JOIN ci_norm n ON ((b.clutch_code = n.ci_join_code)))
     LEFT JOIN public.v_clutch_instance_treatments_effective v ON ((v.clutch_instance_id = n.id)));


--
-- Name: v_containers_crossing_candidates; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_containers_crossing_candidates AS
 SELECT id,
    container_type,
    label,
    status,
    created_by,
    created_at,
    status_changed_at,
    activated_at,
    deactivated_at,
    last_seen_at,
    note
   FROM public.containers c
  WHERE (container_type = ANY (ARRAY['inventory_tank'::text, 'crossing_tank'::text, 'holding_tank'::text, 'nursery_tank'::text, 'petri_dish'::text]));


--
-- Name: v_containers_live; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_containers_live AS
 SELECT id,
    container_type,
    label,
    status,
    created_by,
    created_at,
    note,
    request_id,
    status_changed_at,
    activated_at,
    deactivated_at,
    last_seen_at,
    last_seen_source,
    tank_volume_l,
    tank_code
   FROM public.containers c
  WHERE (status = ANY (ARRAY['active'::text, 'new_tank'::text]));


--
-- Name: v_containers_overview; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_containers_overview AS
 SELECT id,
    container_type,
    label,
    tank_code,
    status,
    status_changed_at,
    created_at
   FROM public.containers c;


--
-- Name: vw_clutches_concept_overview; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_clutches_concept_overview AS
 WITH base AS (
         SELECT cp.id AS clutch_plan_id,
            pc.id AS planned_cross_id,
            cp.clutch_code,
            cp.planned_name AS clutch_name,
            cp.planned_nickname AS clutch_nickname,
            pc.cross_date AS date_planned,
            COALESCE(cp.note, pc.note) AS note,
            cp.created_by,
            cp.created_at
           FROM (public.clutch_plans cp
             LEFT JOIN public.planned_crosses pc ON ((pc.clutch_id = cp.id)))
        ), inst AS (
         SELECT c.planned_cross_id,
            (count(*))::integer AS n_instances,
            max(c.date_birth) AS latest_date_birth,
            (count(c.cross_id))::integer AS n_crosses
           FROM public.clutches c
          GROUP BY c.planned_cross_id
        ), cont AS (
         SELECT c.planned_cross_id,
            (count(cc.*))::integer AS n_containers
           FROM (public.clutches c
             JOIN public.clutch_containers cc ON ((cc.clutch_id = c.id)))
          GROUP BY c.planned_cross_id
        )
 SELECT b.clutch_plan_id,
    b.planned_cross_id,
    b.clutch_code,
    b.clutch_name,
    b.clutch_nickname,
    b.date_planned,
    b.created_by,
    b.created_at,
    b.note,
    COALESCE(i.n_instances, 0) AS n_instances,
    COALESCE(COALESCE(i.n_crosses, 0), 0) AS n_crosses,
    COALESCE(ct.n_containers, 0) AS n_containers,
    i.latest_date_birth
   FROM ((base b
     LEFT JOIN inst i ON ((i.planned_cross_id = b.planned_cross_id)))
     LEFT JOIN cont ct ON ((ct.planned_cross_id = b.planned_cross_id)))
  ORDER BY COALESCE(((b.date_planned)::timestamp without time zone)::timestamp with time zone, b.created_at) DESC NULLS LAST;


--
-- Name: vw_clutches_overview_human; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_clutches_overview_human AS
 WITH base AS (
         SELECT c.id AS clutch_id,
            c.date_birth,
            c.created_by,
            c.created_at,
            c.note,
            c.batch_label,
            c.seed_batch_id,
            c.planned_cross_id,
            cp.clutch_code,
            cp.planned_name AS clutch_name,
            COALESCE(mt.label, mt.tank_code) AS mom_tank_label,
            COALESCE(ft.label, ft.tank_code) AS dad_tank_label,
            c.cross_id
           FROM ((((public.clutches c
             LEFT JOIN public.planned_crosses pc ON ((pc.id = c.planned_cross_id)))
             LEFT JOIN public.clutch_plans cp ON ((cp.id = pc.clutch_id)))
             LEFT JOIN public.containers mt ON ((mt.id = pc.mother_tank_id)))
             LEFT JOIN public.containers ft ON ((ft.id = pc.father_tank_id)))
        ), instances AS (
         SELECT cc.clutch_id,
            (count(*))::integer AS n_instances
           FROM public.clutch_containers cc
          GROUP BY cc.clutch_id
        ), crosses_via_clutches AS (
         SELECT b1.clutch_id,
            (count(x.id))::integer AS n_crosses
           FROM (base b1
             LEFT JOIN public.crosses x ON ((x.id = b1.cross_id)))
          GROUP BY b1.clutch_id
        )
 SELECT b.clutch_id,
    b.date_birth,
    b.created_by,
    b.created_at,
    b.note,
    b.batch_label,
    b.seed_batch_id,
    b.clutch_code,
    b.clutch_name,
    NULL::text AS clutch_nickname,
    b.mom_tank_label,
    b.dad_tank_label,
    COALESCE(i.n_instances, 0) AS n_instances,
    COALESCE(cx.n_crosses, 0) AS n_crosses
   FROM ((base b
     LEFT JOIN instances i ON ((i.clutch_id = b.clutch_id)))
     LEFT JOIN crosses_via_clutches cx ON ((cx.clutch_id = b.clutch_id)))
  ORDER BY COALESCE((b.date_birth)::timestamp with time zone, b.created_at) DESC NULLS LAST;


--
-- Name: v_cross_concepts_overview; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_cross_concepts_overview AS
 SELECT cp.clutch_code AS conceptual_cross_code,
    cp.clutch_name AS name,
    cp.clutch_nickname AS nickname,
    hum.mom_tank_label AS mom_code,
    hum.dad_tank_label AS dad_code,
    hum.mom_tank_label AS mom_code_tank,
    hum.dad_tank_label AS dad_code_tank,
    cp.created_at
   FROM (public.vw_clutches_concept_overview cp
     LEFT JOIN public.vw_clutches_overview_human hum ON ((hum.clutch_code = cp.clutch_code)));


--
-- Name: v_cross_plan_runs_enriched; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_cross_plan_runs_enriched AS
 SELECT r.id,
    r.plan_id,
    r.seq,
    r.planned_date,
    r.status,
    r.note,
    r.created_by,
    r.created_at,
    p.plan_title,
    p.plan_nickname,
    p.mother_fish_id,
    p.father_fish_id,
    fm.fish_code AS mother_fish_code,
    ff.fish_code AS father_fish_code,
    ca.label AS tank_a_label,
    cb.label AS tank_b_label
   FROM (((((public.cross_plan_runs r
     JOIN public.cross_plans p ON ((p.id = r.plan_id)))
     LEFT JOIN public.fish fm ON ((fm.id = p.mother_fish_id)))
     LEFT JOIN public.fish ff ON ((ff.id = p.father_fish_id)))
     LEFT JOIN public.containers ca ON ((ca.id = r.tank_a_id)))
     LEFT JOIN public.containers cb ON ((cb.id = r.tank_b_id)));


--
-- Name: v_cross_plans_enriched; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_cross_plans_enriched AS
 SELECT p.id,
    p.plan_date,
    p.status,
    p.created_by,
    p.note,
    p.created_at,
    p.mother_fish_id,
    fm.fish_code AS mother_fish_code,
    p.father_fish_id,
    ff.fish_code AS father_fish_code,
    p.tank_a_id,
    ca.label AS tank_a_label,
    p.tank_b_id,
    cb.label AS tank_b_label,
    COALESCE(( SELECT string_agg(format('%s[%s]%s'::text, g.transgene_base_code, g.allele_number, COALESCE((' '::text || g.zygosity_planned), ''::text)), ', '::text ORDER BY g.transgene_base_code, g.allele_number) AS string_agg
           FROM public.cross_plan_genotype_alleles g
          WHERE (g.plan_id = p.id)), ''::text) AS genotype_plan,
    COALESCE(( SELECT string_agg(TRIM(BOTH ' '::text FROM concat(t.treatment_name,
                CASE
                    WHEN (t.amount IS NOT NULL) THEN (' '::text || (t.amount)::text)
                    ELSE ''::text
                END,
                CASE
                    WHEN (t.units IS NOT NULL) THEN (' '::text || t.units)
                    ELSE ''::text
                END,
                CASE
                    WHEN (t.timing_note IS NOT NULL) THEN ((' ['::text || t.timing_note) || ']'::text)
                    ELSE ''::text
                END)), ', '::text ORDER BY t.treatment_name) AS string_agg
           FROM public.cross_plan_treatments t
          WHERE (t.plan_id = p.id)), ''::text) AS treatments_plan
   FROM ((((public.cross_plans p
     LEFT JOIN public.fish fm ON ((fm.id = p.mother_fish_id)))
     LEFT JOIN public.fish ff ON ((ff.id = p.father_fish_id)))
     LEFT JOIN public.containers ca ON ((ca.id = p.tank_a_id)))
     LEFT JOIN public.containers cb ON ((cb.id = p.tank_b_id)));


--
-- Name: v_crosses_status; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_crosses_status AS
 SELECT id,
    mother_code,
    father_code,
    planned_for,
    created_by,
    created_at,
        CASE
            WHEN (EXISTS ( SELECT 1
               FROM public.clutches x
              WHERE (x.cross_id = c.id))) THEN 'realized'::text
            ELSE 'planned'::text
        END AS status
   FROM public.crosses c;


--
-- Name: v_fish_living_tank_counts; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_fish_living_tank_counts AS
 SELECT m.fish_id,
    (count(*))::integer AS n_living_tanks
   FROM (public.fish_tank_memberships m
     JOIN public.containers c ON ((c.id = m.container_id)))
  WHERE ((m.left_at IS NULL) AND (c.status = ANY (ARRAY['active'::text, 'new_tank'::text])))
  GROUP BY m.fish_id;


--
-- Name: v_fish_overview; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_fish_overview AS
 SELECT fish_code,
    name,
    nickname,
    line_building_stage,
    date_birth,
    genetic_background,
    created_at,
    NULLIF(array_to_string(ARRAY( SELECT ((fa2.transgene_base_code || '^'::text) || (fa2.allele_number)::text)
           FROM public.fish_transgene_alleles fa2
          WHERE (fa2.fish_id = f.id)
          ORDER BY fa2.transgene_base_code, fa2.allele_number), '; '::text), ''::text) AS genotype_text,
    (date_part('day'::text, (now() - (date_birth)::timestamp with time zone)))::integer AS age_days
   FROM public.fish f
  ORDER BY created_at DESC;


--
-- Name: v_fish_overview_canonical; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_fish_overview_canonical AS
 SELECT fish_code,
    name,
    nickname,
    line_building_stage,
    date_birth,
    genetic_background,
    created_at,
    NULLIF(array_to_string(ARRAY( SELECT ((fa2.transgene_base_code || '^'::text) || (fa2.allele_number)::text)
           FROM public.fish_transgene_alleles fa2
          WHERE (fa2.fish_id = f.id)
          ORDER BY fa2.transgene_base_code, fa2.allele_number), '; '::text), ''::text) AS genotype_text,
    (date_part('day'::text, (now() - (date_birth)::timestamp with time zone)))::integer AS age_days,
    ( SELECT m.seed_batch_id
           FROM public.fish_seed_batches_map m
          WHERE (m.fish_id = f.id)
          ORDER BY m.logged_at DESC
         LIMIT 1) AS seed_batch_id
   FROM public.fish f
  ORDER BY created_at DESC;


--
-- Name: v_fish_overview_human; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_fish_overview_human AS
 WITH open_memberships AS (
         SELECT m.fish_id,
            c.id AS container_id,
            c.tank_code,
            c.label,
            c.status,
            c.created_at
           FROM (public.fish_tank_memberships m
             JOIN public.containers c ON ((c.id = m.container_id)))
          WHERE ((COALESCE((NULLIF((to_jsonb(m.*) ->> 'left_at'::text), ''::text))::timestamp with time zone, (NULLIF((to_jsonb(m.*) ->> 'ended_at'::text), ''::text))::timestamp with time zone) IS NULL) AND ((c.status = ANY (ARRAY['active'::text, 'new_tank'::text])) OR (c.status IS NULL)))
        ), alleles AS (
         SELECT fta.fish_id,
            fta.transgene_base_code AS base_code,
            fta.allele_number,
            COALESCE(ta.allele_nickname, (fta.allele_number)::text) AS allele_nickname,
            COALESCE(NULLIF((to_jsonb(tg.*) ->> 'transgene_name'::text), ''::text), NULLIF((to_jsonb(tg.*) ->> 'name'::text), ''::text), NULLIF((to_jsonb(tg.*) ->> 'label'::text), ''::text), fta.transgene_base_code) AS transgene_name,
            fta.zygosity
           FROM ((public.fish_transgene_alleles fta
             LEFT JOIN public.transgene_alleles ta ON (((ta.transgene_base_code = fta.transgene_base_code) AND (ta.allele_number = fta.allele_number))))
             LEFT JOIN public.transgenes tg ON ((tg.transgene_base_code = fta.transgene_base_code)))
        ), genotype AS (
         SELECT a.fish_id,
            string_agg(TRIM(BOTH ' '::text FROM ((((a.transgene_name || '('::text) || (a.allele_number)::text) || COALESCE((' '::text || a.zygosity), ''::text)) || ')'::text)), ' + '::text ORDER BY a.transgene_name, a.allele_number) AS genotype_rollup,
            min(a.transgene_name) AS transgene_primary,
            min(a.allele_number) AS allele_number_primary,
            min((((a.transgene_name || '('::text) || (a.allele_number)::text) || ')'::text)) AS allele_code_primary
           FROM alleles a
          GROUP BY a.fish_id
        ), current_tank AS (
         SELECT DISTINCT ON (o.fish_id) o.fish_id,
            o.tank_code,
            o.label AS tank_label,
            o.status AS tank_status,
            o.created_at AS tank_created_at
           FROM open_memberships o
          ORDER BY o.fish_id, o.created_at DESC NULLS LAST
        )
 SELECT f.id AS fish_id,
    f.fish_code,
    f.name AS fish_name,
    f.nickname AS fish_nickname,
    f.genetic_background,
    g.allele_number_primary AS allele_number,
    g.allele_code_primary AS allele_code,
    g.transgene_primary AS transgene,
    g.genotype_rollup,
    ct.tank_code,
    ct.tank_label,
    ct.tank_status,
    NULLIF((to_jsonb(f.*) ->> 'stage'::text), ''::text) AS stage,
    f.date_birth,
    f.created_at,
    f.created_by
   FROM ((public.fish f
     LEFT JOIN genotype g ON ((g.fish_id = f.id)))
     LEFT JOIN current_tank ct ON ((ct.fish_id = f.id)))
  ORDER BY f.created_at DESC NULLS LAST;


--
-- Name: v_label_jobs_recent; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_label_jobs_recent AS
 SELECT id,
    entity_type,
    entity_id,
    template,
    media,
    status,
    requested_by,
    requested_at,
    started_at,
    finished_at,
    num_labels,
    ((file_bytes IS NOT NULL) OR (file_url IS NOT NULL)) AS has_file
   FROM public.label_jobs j
  ORDER BY requested_at DESC;


--
-- Name: v_overview_crosses; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_overview_crosses AS
 WITH latest_planned AS (
         SELECT DISTINCT ON (cp_1.id) cp_1.id AS clutch_id,
            cp_1.clutch_code,
            cp_1.status,
            pc.id AS planned_id,
            pc.created_at AS planned_created_at,
            pc.cross_id,
            pc.mother_tank_id,
            pc.father_tank_id,
            cp_1.created_at
           FROM (public.clutch_plans cp_1
             LEFT JOIN public.planned_crosses pc ON ((pc.clutch_id = cp_1.id)))
          ORDER BY cp_1.id, pc.created_at DESC NULLS LAST
        ), counts AS (
         SELECT planned_crosses.clutch_id,
            (count(*))::integer AS planned_count
           FROM public.planned_crosses
          GROUP BY planned_crosses.clutch_id
        )
 SELECT lp.clutch_code,
    x.cross_name_code AS name,
    x.cross_name_genotype AS nickname,
    (cp.status)::text AS status,
    COALESCE(ct.planned_count, 0) AS planned_count,
    x.mother_code AS mom_code,
    x.father_code AS dad_code,
    cm.tank_code AS mom_code_tank,
    cf.tank_code AS dad_code_tank,
    cp.created_at,
    ((cm.tank_code IS NOT NULL) AND (cf.tank_code IS NOT NULL)) AS runnable
   FROM (((((public.clutch_plans cp
     LEFT JOIN latest_planned lp ON ((lp.clutch_id = cp.id)))
     LEFT JOIN counts ct ON ((ct.clutch_id = cp.id)))
     LEFT JOIN public.crosses x ON ((x.id = lp.cross_id)))
     LEFT JOIN public.containers cm ON ((cm.id = lp.mother_tank_id)))
     LEFT JOIN public.containers cf ON ((cf.id = lp.father_tank_id)));


--
-- Name: v_rna_plasmids; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_rna_plasmids AS
 WITH p AS (
         SELECT p_1.id AS plasmid_id,
            ('RNA-'::text || p_1.code) AS code,
            p_1.name,
            p_1.nickname,
            p_1.created_at,
            p_1.created_by
           FROM public.plasmids p_1
          WHERE (p_1.supports_invitro_rna = true)
        ), pr AS (
         SELECT rr.rna_code AS code,
            NULL::uuid AS plasmid_id,
            rr.rna_nickname AS registry_nickname,
            rr.created_at AS registry_created_at,
            rr.created_by AS registry_created_by
           FROM public.rna_registry rr
        )
 SELECT COALESCE(p.plasmid_id, pr.plasmid_id) AS plasmid_id,
    COALESCE(p.code, pr.code) AS code,
    COALESCE(p.name, pr.code) AS name,
    COALESCE(pr.registry_nickname, p.nickname, ''::text) AS nickname,
    COALESCE(p.created_at, pr.registry_created_at) AS created_at,
    COALESCE(p.created_by, pr.registry_created_by) AS created_by,
        CASE
            WHEN (p.plasmid_id IS NOT NULL) THEN 'plasmids'::text
            ELSE 'rna_registry'::text
        END AS source
   FROM (p
     FULL JOIN pr ON ((pr.code = p.code)));


--
-- Name: v_tank_pairs_overview; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_tank_pairs_overview AS
 SELECT tp.id,
    tp.tank_pair_code,
    tp.concept_id,
    COALESCE(cp.clutch_code, (cp.id)::text) AS clutch_code,
    tp.status,
    tp.created_by,
    tp.created_at,
    fp.id AS fish_pair_id,
    mf.fish_code AS mom_fish_code,
    df.fish_code AS dad_fish_code,
    tp.mother_tank_id,
    mt.tank_code AS mom_tank_code,
    tp.father_tank_id,
    dt.tank_code AS dad_tank_code
   FROM ((((((public.tank_pairs tp
     JOIN public.fish_pairs fp ON ((fp.id = tp.fish_pair_id)))
     JOIN public.fish mf ON ((mf.id = fp.mom_fish_id)))
     JOIN public.fish df ON ((df.id = fp.dad_fish_id)))
     LEFT JOIN public.clutch_plans cp ON ((cp.id = tp.concept_id)))
     JOIN public.containers mt ON ((mt.id = tp.mother_tank_id)))
     JOIN public.containers dt ON ((dt.id = tp.father_tank_id)));


--
-- Name: vw_bruker_mounts_enriched; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_bruker_mounts_enriched AS
 SELECT mount_code,
    COALESCE((selection_id)::text, (id)::text) AS selection_id,
    mount_date,
    NULL::time without time zone AS mount_time,
    NULL::integer AS n_top,
    NULL::integer AS n_bottom,
    NULL::text AS orientation,
    created_at,
    created_by
   FROM public.bruker_mounts bm;


--
-- Name: vw_cross_runs_overview; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_cross_runs_overview AS
 WITH cl AS (
         SELECT clutches.cross_instance_id,
            (count(*))::integer AS n_clutches
           FROM public.clutches
          GROUP BY clutches.cross_instance_id
        ), cnt AS (
         SELECT c.cross_instance_id,
            (count(cc.*))::integer AS n_containers
           FROM (public.clutches c
             JOIN public.clutch_containers cc ON ((cc.clutch_id = c.id)))
          GROUP BY c.cross_instance_id
        )
 SELECT ci.id AS cross_instance_id,
    ci.cross_run_code,
    ci.cross_date,
    x.id AS cross_id,
    COALESCE(x.cross_code, (x.id)::text) AS cross_code,
    x.mother_code AS mom_code,
    x.father_code AS dad_code,
    cm.label AS mother_tank_label,
    cf.label AS father_tank_label,
    ci.note AS run_note,
    ci.created_by AS run_created_by,
    ci.created_at AS run_created_at,
    COALESCE(cl.n_clutches, 0) AS n_clutches,
    COALESCE(cnt.n_containers, 0) AS n_containers
   FROM (((((public.cross_instances ci
     JOIN public.crosses x ON ((x.id = ci.cross_id)))
     LEFT JOIN public.containers cm ON ((cm.id = ci.mother_tank_id)))
     LEFT JOIN public.containers cf ON ((cf.id = ci.father_tank_id)))
     LEFT JOIN cl ON ((cl.cross_instance_id = ci.id)))
     LEFT JOIN cnt ON ((cnt.cross_instance_id = ci.id)))
  ORDER BY ci.cross_date DESC, ci.created_at DESC;


--
-- Name: vw_crosses_concept; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_crosses_concept AS
 WITH runs AS (
         SELECT cross_instances.cross_id,
            (count(*))::integer AS n_runs,
            max(cross_instances.cross_date) AS latest_cross_date
           FROM public.cross_instances
          GROUP BY cross_instances.cross_id
        ), cl AS (
         SELECT clutches.cross_id,
            (count(*))::integer AS n_clutches
           FROM public.clutches
          GROUP BY clutches.cross_id
        ), cnt AS (
         SELECT c.cross_id,
            (count(cc.*))::integer AS n_containers
           FROM (public.clutches c
             JOIN public.clutch_containers cc ON ((cc.clutch_id = c.id)))
          GROUP BY c.cross_id
        )
 SELECT x.id AS cross_id,
    COALESCE(x.cross_code, (x.id)::text) AS cross_code,
    x.mother_code AS mom_code,
    x.father_code AS dad_code,
    x.created_by,
    x.created_at,
    COALESCE(runs.n_runs, 0) AS n_runs,
    runs.latest_cross_date,
    COALESCE(cl.n_clutches, 0) AS n_clutches,
    COALESCE(cnt.n_containers, 0) AS n_containers
   FROM (((public.crosses x
     LEFT JOIN runs ON ((runs.cross_id = x.id)))
     LEFT JOIN cl ON ((cl.cross_id = x.id)))
     LEFT JOIN cnt ON ((cnt.cross_id = x.id)))
  ORDER BY x.created_at DESC;


--
-- Name: vw_label_rows; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_label_rows AS
 WITH base AS (
         SELECT f.id,
            f.fish_code,
            f.name,
            f.nickname,
            f.line_building_stage,
            f.date_birth,
            f.genetic_background,
            f.created_at
           FROM public.fish f
        ), allele AS (
         SELECT DISTINCT ON (f2.fish_code) f2.fish_code,
            l.transgene_base_code,
            l.allele_number,
            ta.allele_nickname
           FROM ((public.fish_transgene_alleles l
             JOIN public.fish f2 ON ((f2.id = l.fish_id)))
             LEFT JOIN public.transgene_alleles ta ON (((ta.transgene_base_code = l.transgene_base_code) AND (ta.allele_number = l.allele_number))))
          ORDER BY f2.fish_code, l.transgene_base_code, l.allele_number
        ), batch AS (
         SELECT DISTINCT ON (f3.fish_code) f3.fish_code,
            m.seed_batch_id
           FROM (public.fish_seed_batches_map m
             JOIN public.fish f3 ON ((f3.id = m.fish_id)))
          ORDER BY f3.fish_code, m.logged_at DESC NULLS LAST, m.created_at DESC NULLS LAST
        )
 SELECT b.id,
    b.created_at,
    b.fish_code,
    b.name,
    a.transgene_base_code AS transgene_base_code_filled,
    (a.allele_number)::text AS allele_code_filled,
    a.allele_nickname AS allele_name_filled,
    batch.seed_batch_id AS batch_label,
    COALESCE(b.nickname, ''::text) AS nickname_print,
    COALESCE(b.genetic_background, ''::text) AS genetic_background_print,
    COALESCE(b.line_building_stage, ''::text) AS line_building_stage_print,
    COALESCE(to_char((b.date_birth)::timestamp with time zone, 'YYYY-MM-DD'::text), ''::text) AS date_birth_print,
        CASE
            WHEN (a.transgene_base_code IS NULL) THEN ''::text
            WHEN (a.allele_number IS NOT NULL) THEN ((a.transgene_base_code || '-'::text) || (a.allele_number)::text)
            WHEN (a.allele_nickname IS NOT NULL) THEN ((a.transgene_base_code || ' '::text) || a.allele_nickname)
            ELSE a.transgene_base_code
        END AS genotype_print
   FROM ((base b
     LEFT JOIN allele a USING (fish_code))
     LEFT JOIN batch USING (fish_code))
  ORDER BY b.fish_code;


--
-- Name: vw_planned_clutches_overview; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_planned_clutches_overview AS
 WITH x AS (
         SELECT cp.id AS clutch_plan_id,
            pc.id AS planned_cross_id,
            cp.clutch_code,
            cp.planned_name AS clutch_name,
            cp.planned_nickname AS clutch_nickname,
            pc.cross_date,
            cp.created_by,
            cp.created_at,
            COALESCE(cp.note, pc.note) AS note
           FROM (public.clutch_plans cp
             LEFT JOIN public.planned_crosses pc ON ((pc.clutch_id = cp.id)))
        ), tx AS (
         SELECT t.clutch_id AS clutch_plan_id,
            (count(*))::integer AS n_treatments
           FROM public.clutch_plan_treatments t
          GROUP BY t.clutch_id
        )
 SELECT x.clutch_plan_id,
    x.planned_cross_id,
    x.clutch_code,
    x.clutch_name,
    x.clutch_nickname,
    x.cross_date,
    x.created_by,
    x.created_at,
    x.note,
    COALESCE(tx.n_treatments, 0) AS n_treatments
   FROM (x
     LEFT JOIN tx ON ((tx.clutch_plan_id = x.clutch_plan_id)))
  ORDER BY COALESCE((x.cross_date)::timestamp with time zone, x.created_at) DESC NULLS LAST;


--
-- Name: vw_plasmids_overview; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_plasmids_overview AS
 SELECT p.id,
    p.code,
    p.name,
    p.nickname,
    p.fluors,
    p.resistance,
    p.supports_invitro_rna,
    p.created_by,
    p.notes,
    p.created_at,
    r.id AS rna_id,
    r.code AS rna_code,
    r.name AS rna_name,
    r.source_plasmid_id
   FROM (public.plasmids p
     LEFT JOIN public.rnas r ON ((r.source_plasmid_id = p.id)))
  ORDER BY p.code;


--
-- Name: fish_code_audit id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_code_audit ALTER COLUMN id SET DEFAULT nextval('public.fish_code_audit_id_seq'::regclass);


--
-- Name: allele_nicknames allele_nicknames_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.allele_nicknames
    ADD CONSTRAINT allele_nicknames_pkey PRIMARY KEY (base_code, allele_code);


--
-- Name: bruker_mount bruker_mount_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bruker_mount
    ADD CONSTRAINT bruker_mount_pkey PRIMARY KEY (mount_code);


--
-- Name: bruker_mounts bruker_mounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bruker_mounts
    ADD CONSTRAINT bruker_mounts_pkey PRIMARY KEY (id);


--
-- Name: clutch_containers clutch_containers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutch_containers
    ADD CONSTRAINT clutch_containers_pkey PRIMARY KEY (container_id);


--
-- Name: clutch_genotype_options clutch_genotype_options_clutch_id_allele_code_transgene_bas_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutch_genotype_options
    ADD CONSTRAINT clutch_genotype_options_clutch_id_allele_code_transgene_bas_key UNIQUE (clutch_id, allele_code, transgene_base_code);


--
-- Name: clutch_genotype_options clutch_genotype_options_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutch_genotype_options
    ADD CONSTRAINT clutch_genotype_options_pkey PRIMARY KEY (id);


--
-- Name: clutch_instance_seq clutch_instance_seq_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutch_instance_seq
    ADD CONSTRAINT clutch_instance_seq_pkey PRIMARY KEY (cross_instance_id);


--
-- Name: clutch_instance_treatments clutch_instance_treatments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutch_instance_treatments
    ADD CONSTRAINT clutch_instance_treatments_pkey PRIMARY KEY (id);


--
-- Name: clutch_instances clutch_instances_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutch_instances
    ADD CONSTRAINT clutch_instances_pkey PRIMARY KEY (id);


--
-- Name: clutch_plan_treatments clutch_plan_treatments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutch_plan_treatments
    ADD CONSTRAINT clutch_plan_treatments_pkey PRIMARY KEY (id);


--
-- Name: clutch_plans clutch_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutch_plans
    ADD CONSTRAINT clutch_plans_pkey PRIMARY KEY (id);


--
-- Name: clutch_treatments clutch_treatments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutch_treatments
    ADD CONSTRAINT clutch_treatments_pkey PRIMARY KEY (id);


--
-- Name: clutches clutches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutches
    ADD CONSTRAINT clutches_pkey PRIMARY KEY (id);


--
-- Name: container_status_history container_status_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.container_status_history
    ADD CONSTRAINT container_status_history_pkey PRIMARY KEY (id);


--
-- Name: containers containers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.containers
    ADD CONSTRAINT containers_pkey PRIMARY KEY (id);


--
-- Name: cross_instances cross_instances_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_instances
    ADD CONSTRAINT cross_instances_pkey PRIMARY KEY (id);


--
-- Name: cross_parent_aliases cross_parent_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_parent_aliases
    ADD CONSTRAINT cross_parent_aliases_pkey PRIMARY KEY (parent_code);


--
-- Name: cross_plan_genotype_alleles cross_plan_genotype_alleles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_plan_genotype_alleles
    ADD CONSTRAINT cross_plan_genotype_alleles_pkey PRIMARY KEY (id);


--
-- Name: cross_plan_genotype_alleles cross_plan_genotype_alleles_plan_id_transgene_base_code_all_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_plan_genotype_alleles
    ADD CONSTRAINT cross_plan_genotype_alleles_plan_id_transgene_base_code_all_key UNIQUE (plan_id, transgene_base_code, allele_number);


--
-- Name: cross_plan_runs cross_plan_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_plan_runs
    ADD CONSTRAINT cross_plan_runs_pkey PRIMARY KEY (id);


--
-- Name: cross_plan_runs cross_plan_runs_plan_id_seq_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_plan_runs
    ADD CONSTRAINT cross_plan_runs_plan_id_seq_key UNIQUE (plan_id, seq);


--
-- Name: cross_plan_treatments cross_plan_treatments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_plan_treatments
    ADD CONSTRAINT cross_plan_treatments_pkey PRIMARY KEY (id);


--
-- Name: cross_plans cross_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_plans
    ADD CONSTRAINT cross_plans_pkey PRIMARY KEY (id);


--
-- Name: crosses crosses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crosses
    ADD CONSTRAINT crosses_pkey PRIMARY KEY (id);


--
-- Name: fish_code_audit fish_code_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_code_audit
    ADD CONSTRAINT fish_code_audit_pkey PRIMARY KEY (id);


--
-- Name: fish fish_fish_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT fish_fish_code_key UNIQUE (fish_code);


--
-- Name: fish_pairs fish_pairs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_pairs
    ADD CONSTRAINT fish_pairs_pkey PRIMARY KEY (id);


--
-- Name: fish fish_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT fish_pkey PRIMARY KEY (id);


--
-- Name: fish_seed_batches_map fish_seed_batches_map_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_seed_batches_map
    ADD CONSTRAINT fish_seed_batches_map_pkey PRIMARY KEY (id);


--
-- Name: fish_seed_batches fish_seed_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_seed_batches
    ADD CONSTRAINT fish_seed_batches_pkey PRIMARY KEY (fish_id);


--
-- Name: fish_tank_memberships fish_tank_memberships_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_tank_memberships
    ADD CONSTRAINT fish_tank_memberships_pkey PRIMARY KEY (id);


--
-- Name: fish_transgene_alleles fish_transgene_alleles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_transgene_alleles
    ADD CONSTRAINT fish_transgene_alleles_pkey PRIMARY KEY (fish_id, transgene_base_code, allele_number);


--
-- Name: fish_year_counters fish_year_counters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_year_counters
    ADD CONSTRAINT fish_year_counters_pkey PRIMARY KEY (year);


--
-- Name: injected_plasmid_treatments injected_plasmid_treatments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.injected_plasmid_treatments
    ADD CONSTRAINT injected_plasmid_treatments_pkey PRIMARY KEY (id);


--
-- Name: injected_rna_treatments injected_rna_treatments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.injected_rna_treatments
    ADD CONSTRAINT injected_rna_treatments_pkey PRIMARY KEY (id);


--
-- Name: label_items label_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.label_items
    ADD CONSTRAINT label_items_pkey PRIMARY KEY (id);


--
-- Name: label_jobs label_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.label_jobs
    ADD CONSTRAINT label_jobs_pkey PRIMARY KEY (id);


--
-- Name: load_log_fish load_log_fish_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.load_log_fish
    ADD CONSTRAINT load_log_fish_pkey PRIMARY KEY (id);


--
-- Name: mount_label_seq_day mount_label_seq_day_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mount_label_seq_day
    ADD CONSTRAINT mount_label_seq_day_pkey PRIMARY KEY (mount_date);


--
-- Name: mount_seq mount_seq_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mount_seq
    ADD CONSTRAINT mount_seq_pkey PRIMARY KEY (cross_instance_id);


--
-- Name: mounts mounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mounts
    ADD CONSTRAINT mounts_pkey PRIMARY KEY (id);


--
-- Name: planned_crosses planned_crosses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planned_crosses
    ADD CONSTRAINT planned_crosses_pkey PRIMARY KEY (id);


--
-- Name: plasmid_registry plasmid_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plasmid_registry
    ADD CONSTRAINT plasmid_registry_pkey PRIMARY KEY (id);


--
-- Name: plasmid_registry plasmid_registry_plasmid_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plasmid_registry
    ADD CONSTRAINT plasmid_registry_plasmid_code_key UNIQUE (plasmid_code);


--
-- Name: plasmids plasmids_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plasmids
    ADD CONSTRAINT plasmids_code_key UNIQUE (code);


--
-- Name: plasmids plasmids_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plasmids
    ADD CONSTRAINT plasmids_pkey PRIMARY KEY (id);


--
-- Name: rna_registry rna_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rna_registry
    ADD CONSTRAINT rna_registry_pkey PRIMARY KEY (id);


--
-- Name: rna_registry rna_registry_rna_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rna_registry
    ADD CONSTRAINT rna_registry_rna_code_key UNIQUE (rna_code);


--
-- Name: rnas rnas_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rnas
    ADD CONSTRAINT rnas_code_key UNIQUE (code);


--
-- Name: rnas rnas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rnas
    ADD CONSTRAINT rnas_pkey PRIMARY KEY (id);


--
-- Name: selection_labels selection_labels_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.selection_labels
    ADD CONSTRAINT selection_labels_code_key UNIQUE (code);


--
-- Name: selection_labels selection_labels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.selection_labels
    ADD CONSTRAINT selection_labels_pkey PRIMARY KEY (id);


--
-- Name: tank_pairs tank_pairs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_pairs
    ADD CONSTRAINT tank_pairs_pkey PRIMARY KEY (id);


--
-- Name: tank_requests tank_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_requests
    ADD CONSTRAINT tank_requests_pkey PRIMARY KEY (id);


--
-- Name: tank_year_counters tank_year_counters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_year_counters
    ADD CONSTRAINT tank_year_counters_pkey PRIMARY KEY (year);


--
-- Name: transgene_allele_counters transgene_allele_counters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgene_allele_counters
    ADD CONSTRAINT transgene_allele_counters_pkey PRIMARY KEY (transgene_base_code);


--
-- Name: transgene_allele_registry transgene_allele_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgene_allele_registry
    ADD CONSTRAINT transgene_allele_registry_pkey PRIMARY KEY (id);


--
-- Name: transgene_allele_registry transgene_allele_registry_transgene_base_code_allele_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgene_allele_registry
    ADD CONSTRAINT transgene_allele_registry_transgene_base_code_allele_number_key UNIQUE (transgene_base_code, allele_number);


--
-- Name: transgene_alleles transgene_alleles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgene_alleles
    ADD CONSTRAINT transgene_alleles_pkey PRIMARY KEY (transgene_base_code, allele_number);


--
-- Name: transgenes transgenes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgenes
    ADD CONSTRAINT transgenes_pkey PRIMARY KEY (transgene_base_code);


--
-- Name: clutch_instances uq_clutch_instances_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutch_instances
    ADD CONSTRAINT uq_clutch_instances_code UNIQUE (clutch_instance_code);


--
-- Name: clutch_instances uq_clutch_instances_run_seq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutch_instances
    ADD CONSTRAINT uq_clutch_instances_run_seq UNIQUE (cross_instance_id, seq);


--
-- Name: crosses uq_cross_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crosses
    ADD CONSTRAINT uq_cross_code UNIQUE (cross_code);


--
-- Name: cross_plans uq_cross_plans_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_plans
    ADD CONSTRAINT uq_cross_plans_unique UNIQUE (plan_date, tank_a_id, tank_b_id);


--
-- Name: fish uq_fish_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT uq_fish_code UNIQUE (fish_code);


--
-- Name: fish uq_fish_fish_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT uq_fish_fish_code UNIQUE (fish_code);


--
-- Name: fish_pairs uq_fish_pair; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_pairs
    ADD CONSTRAINT uq_fish_pair UNIQUE (mom_fish_id, dad_fish_id);


--
-- Name: fish_seed_batches_map uq_fsbm_natural; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_seed_batches_map
    ADD CONSTRAINT uq_fsbm_natural UNIQUE (fish_id, seed_batch_id);


--
-- Name: load_log_fish uq_load_log_fish_batch_row; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.load_log_fish
    ADD CONSTRAINT uq_load_log_fish_batch_row UNIQUE (seed_batch_id, row_key);


--
-- Name: mounts uq_mounts_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mounts
    ADD CONSTRAINT uq_mounts_code UNIQUE (mount_code);


--
-- Name: mounts uq_mounts_label; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mounts
    ADD CONSTRAINT uq_mounts_label UNIQUE (mount_label);


--
-- Name: mounts uq_mounts_run_seq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mounts
    ADD CONSTRAINT uq_mounts_run_seq UNIQUE (cross_instance_id, seq);


--
-- Name: transgene_allele_registry uq_registry_legacy; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgene_allele_registry
    ADD CONSTRAINT uq_registry_legacy UNIQUE (base_code, legacy_label);


--
-- Name: transgene_allele_registry uq_registry_modern; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgene_allele_registry
    ADD CONSTRAINT uq_registry_modern UNIQUE (transgene_base_code, allele_nickname);


--
-- Name: containers uq_tank_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.containers
    ADD CONSTRAINT uq_tank_code UNIQUE (tank_code);


--
-- Name: tank_pairs uq_tank_pair_per_concept; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_pairs
    ADD CONSTRAINT uq_tank_pair_per_concept UNIQUE (concept_id, mother_tank_id, father_tank_id);


--
-- Name: cross_instances ux_cross_instances_tp_date; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_instances
    ADD CONSTRAINT ux_cross_instances_tp_date UNIQUE (tank_pair_id, cross_date);


--
-- Name: cross_instances ux_cross_instances_tp_run; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_instances
    ADD CONSTRAINT ux_cross_instances_tp_run UNIQUE (tank_pair_id, run_number);


--
-- Name: idx_cc_clutch; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cc_clutch ON public.clutch_containers USING btree (clutch_id);


--
-- Name: idx_cc_clutch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cc_clutch_id ON public.clutch_containers USING btree (clutch_id);


--
-- Name: idx_cc_created_desc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cc_created_desc ON public.clutch_containers USING btree (created_at DESC);


--
-- Name: idx_cc_selection; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cc_selection ON public.clutch_containers USING btree (selection_label);


--
-- Name: idx_cgo_clutch; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cgo_clutch ON public.clutch_genotype_options USING btree (clutch_id);


--
-- Name: idx_clutch_containers_container_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clutch_containers_container_id ON public.clutch_containers USING btree (container_id);


--
-- Name: idx_clutch_containers_source_container_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clutch_containers_source_container_id ON public.clutch_containers USING btree (source_container_id);


--
-- Name: idx_clutch_plan_treatments_clutch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clutch_plan_treatments_clutch_id ON public.clutch_plan_treatments USING btree (clutch_id);


--
-- Name: idx_clutches_batch; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clutches_batch ON public.clutches USING btree (batch_label);


--
-- Name: idx_clutches_created_desc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clutches_created_desc ON public.clutches USING btree (created_at DESC);


--
-- Name: idx_clutches_cross_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clutches_cross_id ON public.clutches USING btree (cross_id);


--
-- Name: idx_clutches_cross_instance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clutches_cross_instance_id ON public.clutches USING btree (cross_instance_id);


--
-- Name: idx_clutches_planned_cross_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clutches_planned_cross_id ON public.clutches USING btree (planned_cross_id);


--
-- Name: idx_clutches_run_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clutches_run_id ON public.clutches USING btree (run_id);


--
-- Name: idx_clutches_seed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_clutches_seed ON public.clutches USING btree (seed_batch_id);


--
-- Name: idx_containers_created_desc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_containers_created_desc ON public.containers USING btree (created_at DESC);


--
-- Name: idx_containers_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_containers_request_id ON public.containers USING btree (request_id);


--
-- Name: idx_containers_type_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_containers_type_status ON public.containers USING btree (container_type, status);


--
-- Name: idx_cp_father_fish_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cp_father_fish_id ON public.cross_plans USING btree (father_fish_id);


--
-- Name: idx_cp_mother_fish_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cp_mother_fish_id ON public.cross_plans USING btree (mother_fish_id);


--
-- Name: idx_cp_tank_a_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cp_tank_a_id ON public.cross_plans USING btree (tank_a_id);


--
-- Name: idx_cp_tank_b_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cp_tank_b_id ON public.cross_plans USING btree (tank_b_id);


--
-- Name: idx_cpga_plan; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cpga_plan ON public.cross_plan_genotype_alleles USING btree (plan_id);


--
-- Name: idx_cpr_plan_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cpr_plan_id ON public.cross_plan_runs USING btree (plan_id);


--
-- Name: idx_cpr_tank_a_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cpr_tank_a_id ON public.cross_plan_runs USING btree (tank_a_id);


--
-- Name: idx_cpr_tank_b_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cpr_tank_b_id ON public.cross_plan_runs USING btree (tank_b_id);


--
-- Name: idx_cpt_plan; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cpt_plan ON public.cross_plan_treatments USING btree (plan_id);


--
-- Name: idx_cpt_plan_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cpt_plan_id ON public.cross_plan_treatments USING btree (plan_id);


--
-- Name: idx_cpt_plasmid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cpt_plasmid ON public.cross_plan_treatments USING btree (plasmid_id);


--
-- Name: idx_cpt_plasmid_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cpt_plasmid_id ON public.cross_plan_treatments USING btree (plasmid_id);


--
-- Name: idx_cpt_rna; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cpt_rna ON public.cross_plan_treatments USING btree (rna_id);


--
-- Name: idx_cpt_rna_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cpt_rna_id ON public.cross_plan_treatments USING btree (rna_id);


--
-- Name: idx_cross_instances_cross_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_instances_cross_id ON public.cross_instances USING btree (cross_id);


--
-- Name: idx_cross_instances_father_tank_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_instances_father_tank_id ON public.cross_instances USING btree (father_tank_id);


--
-- Name: idx_cross_instances_mother_tank_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_instances_mother_tank_id ON public.cross_instances USING btree (mother_tank_id);


--
-- Name: idx_cross_plan_genotype_alleles_base_allele; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_plan_genotype_alleles_base_allele ON public.cross_plan_genotype_alleles USING btree (transgene_base_code, allele_number);


--
-- Name: idx_cross_plan_runs_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_plan_runs_date ON public.cross_plan_runs USING btree (planned_date);


--
-- Name: idx_cross_plan_runs_plan; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_plan_runs_plan ON public.cross_plan_runs USING btree (plan_id);


--
-- Name: idx_cross_plan_runs_tank_a_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_plan_runs_tank_a_id ON public.cross_plan_runs USING btree (tank_a_id);


--
-- Name: idx_cross_plan_runs_tank_b_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_plan_runs_tank_b_id ON public.cross_plan_runs USING btree (tank_b_id);


--
-- Name: idx_cross_plans_created_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_plans_created_by ON public.cross_plans USING btree (created_by);


--
-- Name: idx_cross_plans_day_father; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_plans_day_father ON public.cross_plans USING btree (plan_date, father_fish_id);


--
-- Name: idx_cross_plans_day_mother; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_plans_day_mother ON public.cross_plans USING btree (plan_date, mother_fish_id);


--
-- Name: idx_cross_plans_father; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_plans_father ON public.cross_plans USING btree (father_fish_id);


--
-- Name: idx_cross_plans_mother; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_plans_mother ON public.cross_plans USING btree (mother_fish_id);


--
-- Name: idx_cross_plans_nick; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_plans_nick ON public.cross_plans USING btree (plan_nickname);


--
-- Name: idx_cross_plans_plan_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_plans_plan_date ON public.cross_plans USING btree (plan_date);


--
-- Name: idx_cross_plans_tank_a; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_plans_tank_a ON public.cross_plans USING btree (tank_a_id);


--
-- Name: idx_cross_plans_tank_b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_plans_tank_b ON public.cross_plans USING btree (tank_b_id);


--
-- Name: idx_cross_plans_title; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cross_plans_title ON public.cross_plans USING btree (plan_title);


--
-- Name: idx_crosses_created_desc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_crosses_created_desc ON public.crosses USING btree (created_at DESC);


--
-- Name: idx_crosses_parents_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_crosses_parents_code ON public.crosses USING btree (mother_code, father_code);


--
-- Name: idx_csh_changed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_csh_changed_at ON public.container_status_history USING btree (changed_at);


--
-- Name: idx_csh_container; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_csh_container ON public.container_status_history USING btree (container_id);


--
-- Name: idx_ct_clutch; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ct_clutch ON public.clutch_treatments USING btree (clutch_id);


--
-- Name: idx_fish_seed_batches_fish_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fish_seed_batches_fish_id ON public.fish_seed_batches USING btree (fish_id);


--
-- Name: idx_fish_transgene_alleles_base_allele; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fish_transgene_alleles_base_allele ON public.fish_transgene_alleles USING btree (transgene_base_code, allele_number);


--
-- Name: idx_fish_transgene_alles_base_allele; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fish_transgene_alles_base_allele ON public.fish_transgene_alleles USING btree (transgene_base_code, allele_number);


--
-- Name: idx_fsbm_fish_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fsbm_fish_id ON public.fish_seed_batches_map USING btree (fish_id);


--
-- Name: idx_fsbm_logged_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fsbm_logged_at ON public.fish_seed_batches_map USING btree (logged_at DESC);


--
-- Name: idx_fsbm_seed_batch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fsbm_seed_batch_id ON public.fish_seed_batches_map USING btree (seed_batch_id);


--
-- Name: idx_fta_base_allele; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fta_base_allele ON public.fish_transgene_alleles USING btree (transgene_base_code, allele_number);


--
-- Name: idx_fta_fish_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fta_fish_id ON public.fish_transgene_alleles USING btree (fish_id);


--
-- Name: idx_ftm_container; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ftm_container ON public.fish_tank_memberships USING btree (container_id);


--
-- Name: idx_ftm_container_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ftm_container_id ON public.fish_tank_memberships USING btree (container_id);


--
-- Name: idx_ftm_fish; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ftm_fish ON public.fish_tank_memberships USING btree (fish_id);


--
-- Name: idx_ftm_fish_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ftm_fish_id ON public.fish_tank_memberships USING btree (fish_id);


--
-- Name: idx_ipt_fish_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ipt_fish_id ON public.injected_plasmid_treatments USING btree (fish_id);


--
-- Name: idx_irt_fish_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_irt_fish_id ON public.injected_rna_treatments USING btree (fish_id);


--
-- Name: idx_label_items_job_seq; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_label_items_job_seq ON public.label_items USING btree (job_id, seq);


--
-- Name: idx_label_items_request; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_label_items_request ON public.label_items USING btree (request_id);


--
-- Name: idx_label_items_tank; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_label_items_tank ON public.label_items USING btree (tank_id);


--
-- Name: idx_label_jobs_entity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_label_jobs_entity ON public.label_jobs USING btree (entity_type, entity_id);


--
-- Name: idx_label_jobs_requested_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_label_jobs_requested_by ON public.label_jobs USING btree (requested_by, requested_at DESC);


--
-- Name: idx_label_jobs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_label_jobs_status ON public.label_jobs USING btree (status, requested_at DESC);


--
-- Name: idx_li_job_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_li_job_id ON public.label_items USING btree (job_id);


--
-- Name: idx_li_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_li_request_id ON public.label_items USING btree (request_id);


--
-- Name: idx_li_tank_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_li_tank_id ON public.label_items USING btree (tank_id);


--
-- Name: idx_load_log_fish_fish_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_load_log_fish_fish_id ON public.load_log_fish USING btree (fish_id);


--
-- Name: idx_pc_clutch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pc_clutch_id ON public.planned_crosses USING btree (clutch_id);


--
-- Name: idx_pc_cross_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pc_cross_id ON public.planned_crosses USING btree (cross_id);


--
-- Name: idx_pc_cross_instance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pc_cross_instance_id ON public.planned_crosses USING btree (cross_instance_id);


--
-- Name: idx_pc_father_tank_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pc_father_tank_id ON public.planned_crosses USING btree (father_tank_id);


--
-- Name: idx_pc_mother_tank_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pc_mother_tank_id ON public.planned_crosses USING btree (mother_tank_id);


--
-- Name: idx_planned_crosses_clutch; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_planned_crosses_clutch ON public.planned_crosses USING btree (clutch_id);


--
-- Name: idx_planned_crosses_cross_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_planned_crosses_cross_id ON public.planned_crosses USING btree (cross_id);


--
-- Name: idx_planned_crosses_cross_instance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_planned_crosses_cross_instance_id ON public.planned_crosses USING btree (cross_instance_id);


--
-- Name: idx_planned_crosses_father_tank_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_planned_crosses_father_tank_id ON public.planned_crosses USING btree (father_tank_id);


--
-- Name: idx_planned_crosses_mother_tank_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_planned_crosses_mother_tank_id ON public.planned_crosses USING btree (mother_tank_id);


--
-- Name: idx_plasmid_registry_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_plasmid_registry_code ON public.plasmid_registry USING btree (plasmid_code);


--
-- Name: idx_rna_registry_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rna_registry_code ON public.rna_registry USING btree (rna_code);


--
-- Name: idx_rnas_source_plasmid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rnas_source_plasmid ON public.rnas USING btree (source_plasmid_id);


--
-- Name: idx_ta_base_nick_ci; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ta_base_nick_ci ON public.transgene_alleles USING btree (transgene_base_code, lower(allele_nickname));


--
-- Name: idx_tank_requests_fish_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tank_requests_fish_id ON public.tank_requests USING btree (fish_id);


--
-- Name: idx_vfltc_fish; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vfltc_fish ON public.fish_tank_memberships USING btree (fish_id);


--
-- Name: idx_xi_cross_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_xi_cross_id ON public.cross_instances USING btree (cross_id);


--
-- Name: idx_xi_father_tank_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_xi_father_tank_id ON public.cross_instances USING btree (father_tank_id);


--
-- Name: idx_xi_mother_tank_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_xi_mother_tank_id ON public.cross_instances USING btree (mother_tank_id);


--
-- Name: ix_bm_mount_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bm_mount_date ON public.bruker_mounts USING btree (mount_date);


--
-- Name: ix_bm_selection_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bm_selection_id ON public.bruker_mounts USING btree (selection_id);


--
-- Name: ix_bruker_mount_ci_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bruker_mount_ci_time ON public.bruker_mount USING btree (clutch_instance_id, time_mounted DESC);


--
-- Name: ix_bruker_mounts_selection_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bruker_mounts_selection_date ON public.bruker_mounts USING btree (selection_id, mount_date);


--
-- Name: ix_ci_cross_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ci_cross_id ON public.cross_instances USING btree (cross_id);


--
-- Name: ix_ci_cross_instance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ci_cross_instance_id ON public.clutch_instances USING btree (cross_instance_id);


--
-- Name: ix_cit_clutch_instance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cit_clutch_instance_id ON public.clutch_instance_treatments USING btree (clutch_instance_id);


--
-- Name: ix_clutch_instances_annotated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clutch_instances_annotated_at ON public.clutch_instances USING btree (annotated_at);


--
-- Name: ix_clutch_instances_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clutch_instances_code ON public.clutch_instances USING btree (clutch_instance_code);


--
-- Name: ix_clutch_instances_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clutch_instances_created_at ON public.clutch_instances USING btree (created_at);


--
-- Name: ix_clutch_instances_cross_instance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clutch_instances_cross_instance_id ON public.clutch_instances USING btree (cross_instance_id);


--
-- Name: ix_clutch_plans_clutch_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clutch_plans_clutch_code ON public.clutch_plans USING btree (clutch_code);


--
-- Name: ix_clutch_plans_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clutch_plans_id ON public.clutch_plans USING btree (id);


--
-- Name: ix_clutches_clutch_instance_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clutches_clutch_instance_code ON public.clutches USING btree (clutch_instance_code);


--
-- Name: ix_containers_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_containers_id ON public.containers USING btree (id);


--
-- Name: ix_cp_id_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cp_id_code ON public.clutch_plans USING btree (id, clutch_code);


--
-- Name: ix_cross_instances_clutch_birthday; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cross_instances_clutch_birthday ON public.cross_instances USING btree (clutch_birthday);


--
-- Name: ix_cross_instances_cross_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cross_instances_cross_id ON public.cross_instances USING btree (cross_id);


--
-- Name: ix_cross_instances_cross_run_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cross_instances_cross_run_code ON public.cross_instances USING btree (cross_run_code);


--
-- Name: ix_cross_instances_father_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cross_instances_father_id ON public.cross_instances USING btree (father_tank_id);


--
-- Name: ix_cross_instances_mother_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cross_instances_mother_id ON public.cross_instances USING btree (mother_tank_id);


--
-- Name: ix_cross_instances_tank_pair; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cross_instances_tank_pair ON public.cross_instances USING btree (tank_pair_id);


--
-- Name: ix_crosses_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crosses_id ON public.crosses USING btree (id);


--
-- Name: ix_fish_pairs_dad; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fish_pairs_dad ON public.fish_pairs USING btree (dad_fish_id);


--
-- Name: ix_fish_pairs_mom; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fish_pairs_mom ON public.fish_pairs USING btree (mom_fish_id);


--
-- Name: ix_ftm_container; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ftm_container ON public.fish_tank_memberships USING btree (container_id);


--
-- Name: ix_ftm_fish; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ftm_fish ON public.fish_tank_memberships USING btree (fish_id);


--
-- Name: ix_ftm_left_null; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ftm_left_null ON public.fish_tank_memberships USING btree (left_at);


--
-- Name: ix_injected_rna_treatments_rna; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_injected_rna_treatments_rna ON public.injected_rna_treatments USING btree (rna_id);


--
-- Name: ix_mounts_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mounts_code ON public.mounts USING btree (mount_code);


--
-- Name: ix_mounts_cross_instance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mounts_cross_instance_id ON public.mounts USING btree (cross_instance_id);


--
-- Name: ix_mounts_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mounts_date ON public.mounts USING btree (mount_date);


--
-- Name: ix_mounts_mount_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mounts_mount_date ON public.mounts USING btree (mount_date DESC);


--
-- Name: ix_mounts_run; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mounts_run ON public.mounts USING btree (cross_instance_id);


--
-- Name: ix_mounts_time_mounted; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mounts_time_mounted ON public.mounts USING btree (time_mounted DESC);


--
-- Name: ix_mv_overview_mounts_daily_lasttime; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mv_overview_mounts_daily_lasttime ON public.mv_overview_mounts_daily USING btree (last_time_mounted DESC);


--
-- Name: ix_mv_overview_tanks_daily_lastseen; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mv_overview_tanks_daily_lastseen ON public.mv_overview_tanks_daily USING btree (last_seen_at DESC);


--
-- Name: ix_pc_clutch_cross; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pc_clutch_cross ON public.planned_crosses USING btree (clutch_id, cross_id);


--
-- Name: ix_planned_crosses_clutch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_planned_crosses_clutch_id ON public.planned_crosses USING btree (clutch_id);


--
-- Name: ix_planned_crosses_cross_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_planned_crosses_cross_id ON public.planned_crosses USING btree (cross_id);


--
-- Name: ix_registry_base_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_registry_base_code ON public.transgene_allele_registry USING btree (base_code);


--
-- Name: ix_tank_pairs_concept; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tank_pairs_concept ON public.tank_pairs USING btree (concept_id);


--
-- Name: ix_tank_pairs_father; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tank_pairs_father ON public.tank_pairs USING btree (father_tank_id);


--
-- Name: ix_tank_pairs_mother; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tank_pairs_mother ON public.tank_pairs USING btree (mother_tank_id);


--
-- Name: uniq_registry_base_legacy; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uniq_registry_base_legacy ON public.transgene_allele_registry USING btree (base_code, legacy_label) WHERE ((base_code IS NOT NULL) AND (legacy_label IS NOT NULL));


--
-- Name: uniq_registry_modern_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uniq_registry_modern_key ON public.transgene_allele_registry USING btree (transgene_base_code, allele_nickname) WHERE ((transgene_base_code IS NOT NULL) AND (allele_nickname IS NOT NULL));


--
-- Name: uq_cit_instance_material; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_cit_instance_material ON public.clutch_instance_treatments USING btree (clutch_instance_id, lower(COALESCE(material_type, ''::text)), lower(COALESCE(material_code, ''::text)));


--
-- Name: uq_clutch_instances_cross_instance; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_clutch_instances_cross_instance ON public.clutch_instances USING btree (cross_instance_id);


--
-- Name: uq_clutch_plans_clutch_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_clutch_plans_clutch_code ON public.clutch_plans USING btree (clutch_code);


--
-- Name: uq_clutches_instance_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_clutches_instance_code ON public.clutches USING btree (clutch_instance_code) WHERE (clutch_instance_code IS NOT NULL);


--
-- Name: uq_clutches_planned_by_date; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_clutches_planned_by_date ON public.clutches USING btree (planned_cross_id, date_birth);


--
-- Name: uq_clutches_run_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_clutches_run_code ON public.clutches USING btree (cross_instance_id, COALESCE(clutch_code, ''::text));


--
-- Name: uq_containers_tank_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_containers_tank_code ON public.containers USING btree (tank_code) WHERE (tank_code IS NOT NULL);


--
-- Name: uq_cross_instances_by_pair_date; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_cross_instances_by_pair_date ON public.cross_instances USING btree (tank_pair_id, cross_date) WHERE (tank_pair_id IS NOT NULL);


--
-- Name: uq_crosses_concept_pair; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_crosses_concept_pair ON public.crosses USING btree (upper(TRIM(BOTH FROM mother_code)), upper(TRIM(BOTH FROM father_code)));


--
-- Name: uq_crosses_cross_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_crosses_cross_code ON public.crosses USING btree (cross_code) WHERE (cross_code IS NOT NULL);


--
-- Name: uq_fsbm_batch_fish; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_fsbm_batch_fish ON public.fish_seed_batches_map USING btree (seed_batch_id, fish_id);


--
-- Name: uq_fta_fish_base; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_fta_fish_base ON public.fish_transgene_alleles USING btree (fish_id, transgene_base_code);


--
-- Name: uq_ftm_fish_open; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_ftm_fish_open ON public.fish_tank_memberships USING btree (fish_id) WHERE (left_at IS NULL);


--
-- Name: uq_ipt_natural; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_ipt_natural ON public.injected_plasmid_treatments USING btree (fish_id, plasmid_id, at_time, amount, units, note);


--
-- Name: uq_irt_natural; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_irt_natural ON public.injected_rna_treatments USING btree (fish_id, rna_id, at_time, amount, units, note);


--
-- Name: uq_label_jobs_dedupe; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_label_jobs_dedupe ON public.label_jobs USING btree (dedupe_hash) WHERE (dedupe_hash IS NOT NULL);


--
-- Name: uq_planned_crosses_clutch_parents_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_planned_crosses_clutch_parents_canonical ON public.planned_crosses USING btree (clutch_id, mother_tank_id, father_tank_id) WHERE ((is_canonical = true) AND (mother_tank_id IS NOT NULL) AND (father_tank_id IS NOT NULL));


--
-- Name: uq_planned_crosses_cross_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_planned_crosses_cross_code ON public.planned_crosses USING btree (cross_code) WHERE (cross_code IS NOT NULL);


--
-- Name: uq_plasmids_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_plasmids_code ON public.plasmids USING btree (code);


--
-- Name: uq_rna_txn_dedupe; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_rna_txn_dedupe ON public.injected_rna_treatments USING btree (fish_id, rna_id, COALESCE(at_time, '1970-01-01 00:00:00+00'::timestamp with time zone), COALESCE(amount, (0)::numeric), COALESCE(units, ''::text), COALESCE(note, ''::text));


--
-- Name: uq_rnas_one_per_plasmid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_rnas_one_per_plasmid ON public.rnas USING btree (source_plasmid_id) WHERE (source_plasmid_id IS NOT NULL);


--
-- Name: uq_tank_pairs_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_tank_pairs_code ON public.tank_pairs USING btree (tank_pair_code);


--
-- Name: uq_tar_base_number; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_tar_base_number ON public.transgene_allele_registry USING btree (transgene_base_code, allele_number);


--
-- Name: ux_mv_fish_search_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_mv_fish_search_code ON public.mv_fish_search USING btree (fish_code);


--
-- Name: ux_mv_overview_clutches_daily_day; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_mv_overview_clutches_daily_day ON public.mv_overview_clutches_daily USING btree (annot_day);


--
-- Name: ux_mv_overview_crosses_daily_day; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_mv_overview_crosses_daily_day ON public.mv_overview_crosses_daily USING btree (run_day);


--
-- Name: ux_mv_overview_fish_daily_day; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_mv_overview_fish_daily_day ON public.mv_overview_fish_daily USING btree (fish_day);


--
-- Name: ux_mv_overview_mounts_daily_day; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_mv_overview_mounts_daily_day ON public.mv_overview_mounts_daily USING btree (mount_day);


--
-- Name: ux_mv_overview_plasmids_daily_day; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_mv_overview_plasmids_daily_day ON public.mv_overview_plasmids_daily USING btree (plasmid_day);


--
-- Name: ux_mv_overview_tanks_daily_day; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_mv_overview_tanks_daily_day ON public.mv_overview_tanks_daily USING btree (tank_day);


--
-- Name: ux_planned_crosses_cross_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_planned_crosses_cross_code ON public.planned_crosses USING btree (cross_code);


--
-- Name: ux_transgene_alleles_number; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_transgene_alleles_number ON public.transgene_alleles USING btree (NULLIF((allele_number)::text, ''::text));


--
-- Name: ux_transgene_alleles_number_int; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_transgene_alleles_number_int ON public.transgene_alleles USING btree (allele_number);


--
-- Name: fish_csv fish_csv_insert; Type: RULE; Schema: public; Owner: -
--

CREATE RULE fish_csv_insert AS
    ON INSERT TO public.fish_csv DO INSTEAD  INSERT INTO public.fish (fish_code, name, nickname, genetic_background, birthday, created_by)
  VALUES (COALESCE(new.fish_code, ''::text), COALESCE(new.name, ''::text), COALESCE(new.nickname, ''::text), COALESCE(new.genetic_background, ''::text), new.birthday, COALESCE(new.created_by, ''::text)) ON CONFLICT(fish_code) DO UPDATE SET name = excluded.name, nickname = excluded.nickname, genetic_background = excluded.genetic_background, birthday = excluded.birthday, created_by = excluded.created_by;


--
-- Name: fish_csv fish_csv_update; Type: RULE; Schema: public; Owner: -
--

CREATE RULE fish_csv_update AS
    ON UPDATE TO public.fish_csv DO INSTEAD  UPDATE public.fish SET name = COALESCE(new.name, fish.name), nickname = COALESCE(new.nickname, fish.nickname), genetic_background = COALESCE(new.genetic_background, fish.genetic_background), birthday = COALESCE(new.birthday, fish.birthday), created_by = COALESCE(new.created_by, fish.created_by)
  WHERE (fish.fish_code = new.fish_code);


--
-- Name: fish bi_set_fish_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER bi_set_fish_code BEFORE INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.fish_bi_set_fish_code();


--
-- Name: clutch_instances clutch_instances_alloc_seq; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER clutch_instances_alloc_seq BEFORE INSERT ON public.clutch_instances FOR EACH ROW EXECUTE FUNCTION public.trg_clutch_instances_alloc_seq();


--
-- Name: clutch_plans cp_require_planned_crosses; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER cp_require_planned_crosses BEFORE UPDATE ON public.clutch_plans FOR EACH ROW EXECUTE FUNCTION public.trg_cp_require_planned_crosses();


--
-- Name: crosses crosses_set_code_and_genotype; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER crosses_set_code_and_genotype BEFORE INSERT OR UPDATE OF mother_code, father_code, cross_name_genotype ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_crosses_set_code_and_genotype();


--
-- Name: mounts mounts_alloc_seq; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER mounts_alloc_seq BEFORE INSERT ON public.mounts FOR EACH ROW EXECUTE FUNCTION public.trg_mounts_alloc_seq();


--
-- Name: containers trg_audit_del; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_del AFTER DELETE ON public.containers FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: fish trg_audit_del; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_del AFTER DELETE ON public.fish FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: fish_tank_memberships trg_audit_del; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_del AFTER DELETE ON public.fish_tank_memberships FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: fish_transgene_alleles trg_audit_del; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_del AFTER DELETE ON public.fish_transgene_alleles FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: transgene_alleles trg_audit_del; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_del AFTER DELETE ON public.transgene_alleles FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: containers trg_audit_ins; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_ins AFTER INSERT ON public.containers FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: fish trg_audit_ins; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_ins AFTER INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: fish_tank_memberships trg_audit_ins; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_ins AFTER INSERT ON public.fish_tank_memberships FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: fish_transgene_alleles trg_audit_ins; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_ins AFTER INSERT ON public.fish_transgene_alleles FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: transgene_alleles trg_audit_ins; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_ins AFTER INSERT ON public.transgene_alleles FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: containers trg_audit_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_upd AFTER UPDATE ON public.containers FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: fish trg_audit_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_upd AFTER UPDATE ON public.fish FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: fish_tank_memberships trg_audit_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_upd AFTER UPDATE ON public.fish_tank_memberships FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: fish_transgene_alleles trg_audit_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_upd AFTER UPDATE ON public.fish_transgene_alleles FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: transgene_alleles trg_audit_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_upd AFTER UPDATE ON public.transgene_alleles FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: clutch_instances trg_cit_copy_template; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cit_copy_template AFTER INSERT ON public.clutch_instances FOR EACH ROW EXECUTE FUNCTION public.trg_cit_on_insert_copy_template();


--
-- Name: clutch_plans trg_clutch_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_clutch_code BEFORE INSERT ON public.clutch_plans FOR EACH ROW EXECUTE FUNCTION public.trg_clutch_code();


--
-- Name: clutches trg_clutch_instance_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_clutch_instance_code BEFORE INSERT ON public.clutches FOR EACH ROW EXECUTE FUNCTION public.trg_clutch_instance_code();


--
-- Name: clutches trg_clutch_instance_code_fill; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_clutch_instance_code_fill BEFORE INSERT ON public.clutches FOR EACH ROW EXECUTE FUNCTION public.trg_clutch_instance_code_fill();


--
-- Name: clutch_plans trg_clutch_plans_set_expected; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_clutch_plans_set_expected BEFORE INSERT OR UPDATE ON public.clutch_plans FOR EACH ROW EXECUTE FUNCTION public.trg_clutch_plans_set_expected();


--
-- Name: clutches trg_clutches_set_birthday; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_clutches_set_birthday BEFORE INSERT ON public.clutches FOR EACH ROW EXECUTE FUNCTION public.trg_clutches_set_birthday();


--
-- Name: clutches trg_clutches_set_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_clutches_set_code BEFORE INSERT OR UPDATE ON public.clutches FOR EACH ROW EXECUTE FUNCTION public.trg_clutches_set_code();


--
-- Name: clutches trg_clutches_set_expected; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_clutches_set_expected BEFORE INSERT OR UPDATE ON public.clutches FOR EACH ROW EXECUTE FUNCTION public.trg_clutches_set_expected();


--
-- Name: containers trg_containers_activate_on_label; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_containers_activate_on_label BEFORE UPDATE OF label ON public.containers FOR EACH ROW EXECUTE FUNCTION public.trg_containers_activate_on_label();


--
-- Name: containers trg_containers_status_history; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_containers_status_history AFTER UPDATE OF status ON public.containers FOR EACH ROW EXECUTE FUNCTION public.trg_log_container_status();


--
-- Name: crosses trg_cross_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cross_code BEFORE INSERT ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_cross_code();


--
-- Name: crosses trg_cross_code_fill; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cross_code_fill BEFORE INSERT OR UPDATE ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_cross_code_fill();


--
-- Name: cross_instances trg_cross_instance_auto_clutch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cross_instance_auto_clutch AFTER INSERT ON public.cross_instances FOR EACH ROW EXECUTE FUNCTION public.ensure_clutch_for_cross_instance();


--
-- Name: cross_instances trg_cross_instances_set_codes; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cross_instances_set_codes BEFORE INSERT ON public.cross_instances FOR EACH ROW EXECUTE FUNCTION public.trg_cross_instances_set_codes();


--
-- Name: crosses trg_cross_name_fill; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cross_name_fill BEFORE INSERT OR UPDATE ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_cross_name_fill();


--
-- Name: cross_instances trg_cross_run_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cross_run_code BEFORE INSERT ON public.cross_instances FOR EACH ROW EXECUTE FUNCTION public.trg_cross_run_code();


--
-- Name: fish trg_fish_autotank; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_fish_autotank AFTER INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.trg_fish_autotank();


--
-- Name: fish trg_fish_before_insert_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_fish_before_insert_code BEFORE INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.fish_before_insert_code();


--
-- Name: fish trg_fish_birthday_sync; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_fish_birthday_sync BEFORE INSERT OR UPDATE ON public.fish FOR EACH ROW EXECUTE FUNCTION public.fish_birthday_sync();


--
-- Name: plasmids trg_plasmids_auto_ensure_rna; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_plasmids_auto_ensure_rna AFTER INSERT OR UPDATE OF supports_invitro_rna, code ON public.plasmids FOR EACH ROW EXECUTE FUNCTION public.trg_plasmid_auto_ensure_rna();


--
-- Name: clutch_instances trg_refresh_mv_overview_clutches_daily_d; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_clutches_daily_d AFTER DELETE ON public.clutch_instances FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_clutches_daily();


--
-- Name: clutch_instances trg_refresh_mv_overview_clutches_daily_i; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_clutches_daily_i AFTER INSERT ON public.clutch_instances FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_clutches_daily();


--
-- Name: clutch_instances trg_refresh_mv_overview_clutches_daily_u; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_clutches_daily_u AFTER UPDATE ON public.clutch_instances FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_clutches_daily();


--
-- Name: cross_instances trg_refresh_mv_overview_crosses_daily_d; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_crosses_daily_d AFTER DELETE ON public.cross_instances FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_crosses_daily();


--
-- Name: cross_instances trg_refresh_mv_overview_crosses_daily_i; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_crosses_daily_i AFTER INSERT ON public.cross_instances FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_crosses_daily();


--
-- Name: cross_instances trg_refresh_mv_overview_crosses_daily_u; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_crosses_daily_u AFTER UPDATE ON public.cross_instances FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_crosses_daily();


--
-- Name: fish trg_refresh_mv_overview_fish_daily_d; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_fish_daily_d AFTER DELETE ON public.fish FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_fish_daily();


--
-- Name: fish trg_refresh_mv_overview_fish_daily_i; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_fish_daily_i AFTER INSERT ON public.fish FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_fish_daily();


--
-- Name: fish trg_refresh_mv_overview_fish_daily_u; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_fish_daily_u AFTER UPDATE ON public.fish FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_fish_daily();


--
-- Name: mounts trg_refresh_mv_overview_mounts_daily_del; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_mounts_daily_del AFTER DELETE ON public.mounts FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_mounts_daily();


--
-- Name: mounts trg_refresh_mv_overview_mounts_daily_ins; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_mounts_daily_ins AFTER INSERT ON public.mounts FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_mounts_daily();


--
-- Name: mounts trg_refresh_mv_overview_mounts_daily_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_mounts_daily_upd AFTER UPDATE ON public.mounts FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_mounts_daily();


--
-- Name: plasmids trg_refresh_mv_overview_plasmids_daily_d; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_plasmids_daily_d AFTER DELETE ON public.plasmids FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_plasmids_daily();


--
-- Name: plasmids trg_refresh_mv_overview_plasmids_daily_i; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_plasmids_daily_i AFTER INSERT ON public.plasmids FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_plasmids_daily();


--
-- Name: plasmids trg_refresh_mv_overview_plasmids_daily_u; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_plasmids_daily_u AFTER UPDATE ON public.plasmids FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_plasmids_daily();


--
-- Name: containers trg_refresh_mv_overview_tanks_daily_d; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_tanks_daily_d AFTER DELETE ON public.containers FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_tanks_daily();


--
-- Name: containers trg_refresh_mv_overview_tanks_daily_i; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_tanks_daily_i AFTER INSERT ON public.containers FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_tanks_daily();


--
-- Name: containers trg_refresh_mv_overview_tanks_daily_u; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_tanks_daily_u AFTER UPDATE ON public.containers FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_tanks_daily();


--
-- Name: transgene_allele_registry trg_registry_fill_modern; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_registry_fill_modern BEFORE INSERT OR UPDATE ON public.transgene_allele_registry FOR EACH ROW EXECUTE FUNCTION public.trg_registry_fill_modern();


--
-- Name: allele_nicknames trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.allele_nicknames FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: bruker_mounts trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.bruker_mounts FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: clutch_containers trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.clutch_containers FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: clutch_genotype_options trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.clutch_genotype_options FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: clutch_instances trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.clutch_instances FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: clutch_plan_treatments trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.clutch_plan_treatments FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: clutch_plans trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.clutch_plans FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: clutch_treatments trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.clutch_treatments FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: clutches trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.clutches FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: container_status_history trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.container_status_history FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: containers trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.containers FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: cross_instances trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.cross_instances FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: cross_plan_genotype_alleles trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.cross_plan_genotype_alleles FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: cross_plan_runs trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.cross_plan_runs FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: cross_plan_treatments trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.cross_plan_treatments FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: cross_plans trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.cross_plans FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: crosses trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: fish trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.fish FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: fish_code_audit trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.fish_code_audit FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: fish_seed_batches trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.fish_seed_batches FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: fish_seed_batches_map trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.fish_seed_batches_map FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: fish_tank_memberships trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.fish_tank_memberships FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: fish_transgene_alleles trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.fish_transgene_alleles FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: fish_year_counters trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.fish_year_counters FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: injected_plasmid_treatments trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.injected_plasmid_treatments FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: injected_rna_treatments trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.injected_rna_treatments FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: label_items trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.label_items FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: label_jobs trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.label_jobs FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: load_log_fish trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.load_log_fish FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: planned_crosses trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.planned_crosses FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: plasmid_registry trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.plasmid_registry FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: plasmids trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.plasmids FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: rna_registry trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.rna_registry FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: rnas trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.rnas FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: selection_labels trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.selection_labels FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: tank_requests trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.tank_requests FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: tank_year_counters trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.tank_year_counters FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: transgene_allele_counters trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.transgene_allele_counters FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: transgene_allele_registry trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.transgene_allele_registry FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: transgene_alleles trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.transgene_alleles FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: transgenes trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.transgenes FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: tank_pairs trg_tank_pairs_immutable_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_tank_pairs_immutable_code BEFORE UPDATE ON public.tank_pairs FOR EACH ROW EXECUTE FUNCTION public.trg_tank_pairs_immutable_code();


--
-- Name: tank_pairs trg_tank_pairs_set_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_tank_pairs_set_code BEFORE INSERT ON public.tank_pairs FOR EACH ROW EXECUTE FUNCTION public.trg_tank_pairs_set_code();


--
-- Name: transgene_alleles trg_transgene_alleles_autofill; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_transgene_alleles_autofill BEFORE INSERT OR UPDATE ON public.transgene_alleles FOR EACH ROW EXECUTE FUNCTION public.transgene_alleles_autofill();


--
-- Name: crosses zz_bi_normalize_cross_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER zz_bi_normalize_cross_code BEFORE INSERT OR UPDATE ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_cross_code_normalize();


--
-- Name: bruker_mounts bruker_mounts_selection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bruker_mounts
    ADD CONSTRAINT bruker_mounts_selection_id_fkey FOREIGN KEY (selection_id) REFERENCES public.clutch_instances(id) ON DELETE CASCADE;


--
-- Name: clutch_instance_treatments clutch_instance_treatments_clutch_instance_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutch_instance_treatments
    ADD CONSTRAINT clutch_instance_treatments_clutch_instance_id_fkey FOREIGN KEY (clutch_instance_id) REFERENCES public.clutch_instances(id) ON DELETE CASCADE;


--
-- Name: clutches clutches_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutches
    ADD CONSTRAINT clutches_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.cross_plan_runs(id) ON DELETE SET NULL;


--
-- Name: cross_instances cross_instances_tank_pair_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_instances
    ADD CONSTRAINT cross_instances_tank_pair_id_fkey FOREIGN KEY (tank_pair_id) REFERENCES public.tank_pairs(id);


--
-- Name: cross_plan_genotype_alleles cross_plan_genotype_alleles_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_plan_genotype_alleles
    ADD CONSTRAINT cross_plan_genotype_alleles_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES public.cross_plans(id) ON DELETE CASCADE;


--
-- Name: cross_plan_runs cross_plan_runs_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_plan_runs
    ADD CONSTRAINT cross_plan_runs_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES public.cross_plans(id) ON DELETE CASCADE;


--
-- Name: cross_plan_treatments cross_plan_treatments_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_plan_treatments
    ADD CONSTRAINT cross_plan_treatments_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES public.cross_plans(id) ON DELETE CASCADE;


--
-- Name: cross_plan_treatments cross_plan_treatments_plasmid_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_plan_treatments
    ADD CONSTRAINT cross_plan_treatments_plasmid_id_fkey FOREIGN KEY (plasmid_id) REFERENCES public.plasmid_registry(id) ON DELETE RESTRICT;


--
-- Name: cross_plan_treatments cross_plan_treatments_rna_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_plan_treatments
    ADD CONSTRAINT cross_plan_treatments_rna_id_fkey FOREIGN KEY (rna_id) REFERENCES public.rna_registry(id) ON DELETE RESTRICT;


--
-- Name: fish_pairs fish_pairs_dad_fish_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_pairs
    ADD CONSTRAINT fish_pairs_dad_fish_id_fkey FOREIGN KEY (dad_fish_id) REFERENCES public.fish(id) ON DELETE RESTRICT;


--
-- Name: fish_pairs fish_pairs_mom_fish_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_pairs
    ADD CONSTRAINT fish_pairs_mom_fish_id_fkey FOREIGN KEY (mom_fish_id) REFERENCES public.fish(id) ON DELETE RESTRICT;


--
-- Name: fish_transgene_alleles fish_transgene_alleles_transgene_base_code_allele_number_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_transgene_alleles
    ADD CONSTRAINT fish_transgene_alleles_transgene_base_code_allele_number_fkey FOREIGN KEY (transgene_base_code, allele_number) REFERENCES public.transgene_alleles(transgene_base_code, allele_number) ON DELETE CASCADE;


--
-- Name: clutch_instances fk_clutch_instances_cross_instance; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutch_instances
    ADD CONSTRAINT fk_clutch_instances_cross_instance FOREIGN KEY (cross_instance_id) REFERENCES public.cross_instances(id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;


--
-- Name: cross_plan_genotype_alleles fk_cpga_transgene_allele; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_plan_genotype_alleles
    ADD CONSTRAINT fk_cpga_transgene_allele FOREIGN KEY (transgene_base_code, allele_number) REFERENCES public.transgene_alleles(transgene_base_code, allele_number) ON DELETE RESTRICT;


--
-- Name: cross_instances fk_cross_instances_cross; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_instances
    ADD CONSTRAINT fk_cross_instances_cross FOREIGN KEY (cross_id) REFERENCES public.crosses(id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;


--
-- Name: fish_seed_batches_map fk_fsbm_fish; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_seed_batches_map
    ADD CONSTRAINT fk_fsbm_fish FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;


--
-- Name: planned_crosses fk_planned_crosses_cross; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planned_crosses
    ADD CONSTRAINT fk_planned_crosses_cross FOREIGN KEY (cross_id) REFERENCES public.crosses(id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;


--
-- Name: transgene_alleles fk_transgene_alleles_base; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgene_alleles
    ADD CONSTRAINT fk_transgene_alleles_base FOREIGN KEY (transgene_base_code) REFERENCES public.transgenes(transgene_base_code) ON DELETE CASCADE;


--
-- Name: mounts mounts_cross_instance_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mounts
    ADD CONSTRAINT mounts_cross_instance_id_fkey FOREIGN KEY (cross_instance_id) REFERENCES public.cross_instances(id) ON DELETE CASCADE;


--
-- Name: tank_pairs tank_pairs_concept_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_pairs
    ADD CONSTRAINT tank_pairs_concept_id_fkey FOREIGN KEY (concept_id) REFERENCES public.clutch_plans(id) ON DELETE SET NULL;


--
-- Name: tank_pairs tank_pairs_father_tank_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_pairs
    ADD CONSTRAINT tank_pairs_father_tank_id_fkey FOREIGN KEY (father_tank_id) REFERENCES public.containers(id) ON DELETE RESTRICT;


--
-- Name: tank_pairs tank_pairs_fish_pair_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_pairs
    ADD CONSTRAINT tank_pairs_fish_pair_id_fkey FOREIGN KEY (fish_pair_id) REFERENCES public.fish_pairs(id) ON DELETE CASCADE;


--
-- Name: tank_pairs tank_pairs_mother_tank_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_pairs
    ADD CONSTRAINT tank_pairs_mother_tank_id_fkey FOREIGN KEY (mother_tank_id) REFERENCES public.containers(id) ON DELETE RESTRICT;


--
-- Name: allele_nicknames; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.allele_nicknames ENABLE ROW LEVEL SECURITY;

--
-- Name: allele_nicknames allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.allele_nicknames FOR SELECT TO authenticated USING (true);


--
-- Name: bruker_mounts allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.bruker_mounts FOR SELECT TO authenticated USING (true);


--
-- Name: clutch_containers allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.clutch_containers FOR SELECT TO authenticated USING (true);


--
-- Name: clutch_genotype_options allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.clutch_genotype_options FOR SELECT TO authenticated USING (true);


--
-- Name: clutch_instances allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.clutch_instances FOR SELECT TO authenticated USING (true);


--
-- Name: clutch_plan_treatments allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.clutch_plan_treatments FOR SELECT TO authenticated USING (true);


--
-- Name: clutch_plans allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.clutch_plans FOR SELECT TO authenticated USING (true);


--
-- Name: clutch_treatments allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.clutch_treatments FOR SELECT TO authenticated USING (true);


--
-- Name: clutches allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.clutches FOR SELECT TO authenticated USING (true);


--
-- Name: container_status_history allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.container_status_history FOR SELECT TO authenticated USING (true);


--
-- Name: containers allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.containers FOR SELECT TO authenticated USING (true);


--
-- Name: cross_instances allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.cross_instances FOR SELECT TO authenticated USING (true);


--
-- Name: cross_plan_genotype_alleles allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.cross_plan_genotype_alleles FOR SELECT TO authenticated USING (true);


--
-- Name: cross_plan_runs allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.cross_plan_runs FOR SELECT TO authenticated USING (true);


--
-- Name: cross_plan_treatments allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.cross_plan_treatments FOR SELECT TO authenticated USING (true);


--
-- Name: cross_plans allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.cross_plans FOR SELECT TO authenticated USING (true);


--
-- Name: crosses allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.crosses FOR SELECT TO authenticated USING (true);


--
-- Name: fish allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.fish FOR SELECT TO authenticated USING (true);


--
-- Name: fish_code_audit allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.fish_code_audit FOR SELECT TO authenticated USING (true);


--
-- Name: fish_seed_batches allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.fish_seed_batches FOR SELECT TO authenticated USING (true);


--
-- Name: fish_seed_batches_map allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.fish_seed_batches_map FOR SELECT TO authenticated USING (true);


--
-- Name: fish_tank_memberships allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.fish_tank_memberships FOR SELECT TO authenticated USING (true);


--
-- Name: fish_transgene_alleles allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.fish_transgene_alleles FOR SELECT TO authenticated USING (true);


--
-- Name: fish_year_counters allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.fish_year_counters FOR SELECT TO authenticated USING (true);


--
-- Name: injected_plasmid_treatments allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.injected_plasmid_treatments FOR SELECT TO authenticated USING (true);


--
-- Name: injected_rna_treatments allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.injected_rna_treatments FOR SELECT TO authenticated USING (true);


--
-- Name: label_items allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.label_items FOR SELECT TO authenticated USING (true);


--
-- Name: label_jobs allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.label_jobs FOR SELECT TO authenticated USING (true);


--
-- Name: load_log_fish allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.load_log_fish FOR SELECT TO authenticated USING (true);


--
-- Name: planned_crosses allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.planned_crosses FOR SELECT TO authenticated USING (true);


--
-- Name: plasmid_registry allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.plasmid_registry FOR SELECT TO authenticated USING (true);


--
-- Name: plasmids allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.plasmids FOR SELECT TO authenticated USING (true);


--
-- Name: rna_registry allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.rna_registry FOR SELECT TO authenticated USING (true);


--
-- Name: rnas allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.rnas FOR SELECT TO authenticated USING (true);


--
-- Name: selection_labels allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.selection_labels FOR SELECT TO authenticated USING (true);


--
-- Name: tank_requests allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.tank_requests FOR SELECT TO authenticated USING (true);


--
-- Name: tank_year_counters allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.tank_year_counters FOR SELECT TO authenticated USING (true);


--
-- Name: transgene_allele_counters allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.transgene_allele_counters FOR SELECT TO authenticated USING (true);


--
-- Name: transgene_allele_registry allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.transgene_allele_registry FOR SELECT TO authenticated USING (true);


--
-- Name: transgene_alleles allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.transgene_alleles FOR SELECT TO authenticated USING (true);


--
-- Name: transgenes allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.transgenes FOR SELECT TO authenticated USING (true);


--
-- Name: bruker_mounts app_rw_insert_bm; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_insert_bm ON public.bruker_mounts FOR INSERT TO app_rw WITH CHECK (true);


--
-- Name: cross_instances app_rw_insert_ci; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_insert_ci ON public.cross_instances FOR INSERT TO app_rw WITH CHECK (true);


--
-- Name: clutch_instances app_rw_insert_ci_annot; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_insert_ci_annot ON public.clutch_instances FOR INSERT TO app_rw WITH CHECK (true);


--
-- Name: fish app_rw_insert_fish; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_insert_fish ON public.fish FOR INSERT TO app_rw WITH CHECK (true);


--
-- Name: fish_transgene_alleles app_rw_insert_fta; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_insert_fta ON public.fish_transgene_alleles FOR INSERT TO app_rw WITH CHECK (true);


--
-- Name: planned_crosses app_rw_insert_planned_crosses; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_insert_planned_crosses ON public.planned_crosses FOR INSERT TO app_rw WITH CHECK (true);


--
-- Name: transgene_alleles app_rw_insert_tga; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_insert_tga ON public.transgene_alleles FOR INSERT TO app_rw WITH CHECK (true);


--
-- Name: bruker_mounts app_rw_select_bm; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_select_bm ON public.bruker_mounts FOR SELECT TO app_rw USING (true);


--
-- Name: cross_instances app_rw_select_ci; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_select_ci ON public.cross_instances FOR SELECT TO app_rw USING (true);


--
-- Name: clutch_instances app_rw_select_ci_annot; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_select_ci_annot ON public.clutch_instances FOR SELECT TO app_rw USING (true);


--
-- Name: fish app_rw_select_fish; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_select_fish ON public.fish FOR SELECT TO app_rw USING (true);


--
-- Name: fish_transgene_alleles app_rw_select_fta; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_select_fta ON public.fish_transgene_alleles FOR SELECT TO app_rw USING (true);


--
-- Name: planned_crosses app_rw_select_planned_crosses; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_select_planned_crosses ON public.planned_crosses FOR SELECT TO app_rw USING (true);


--
-- Name: transgene_alleles app_rw_select_tga; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_select_tga ON public.transgene_alleles FOR SELECT TO app_rw USING (true);


--
-- Name: bruker_mounts app_rw_update_bm; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_update_bm ON public.bruker_mounts FOR UPDATE TO app_rw USING (true) WITH CHECK (true);


--
-- Name: cross_instances app_rw_update_ci; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_update_ci ON public.cross_instances FOR UPDATE TO app_rw USING (true) WITH CHECK (true);


--
-- Name: clutch_instances app_rw_update_ci_annot; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_update_ci_annot ON public.clutch_instances FOR UPDATE TO app_rw USING (true) WITH CHECK (true);


--
-- Name: fish app_rw_update_fish; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_update_fish ON public.fish FOR UPDATE TO app_rw USING (true) WITH CHECK (true);


--
-- Name: fish_transgene_alleles app_rw_update_fta; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_update_fta ON public.fish_transgene_alleles FOR UPDATE TO app_rw USING (true) WITH CHECK (true);


--
-- Name: planned_crosses app_rw_update_planned_crosses; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_update_planned_crosses ON public.planned_crosses FOR UPDATE TO app_rw USING (true) WITH CHECK (true);


--
-- Name: transgene_alleles app_rw_update_tga; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_update_tga ON public.transgene_alleles FOR UPDATE TO app_rw USING (true) WITH CHECK (true);


--
-- Name: bruker_mounts; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.bruker_mounts ENABLE ROW LEVEL SECURITY;

--
-- Name: clutch_containers; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.clutch_containers ENABLE ROW LEVEL SECURITY;

--
-- Name: clutch_genotype_options; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.clutch_genotype_options ENABLE ROW LEVEL SECURITY;

--
-- Name: clutch_instances; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.clutch_instances ENABLE ROW LEVEL SECURITY;

--
-- Name: clutch_plan_treatments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.clutch_plan_treatments ENABLE ROW LEVEL SECURITY;

--
-- Name: clutch_plans; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.clutch_plans ENABLE ROW LEVEL SECURITY;

--
-- Name: clutch_treatments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.clutch_treatments ENABLE ROW LEVEL SECURITY;

--
-- Name: clutches; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.clutches ENABLE ROW LEVEL SECURITY;

--
-- Name: container_status_history; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.container_status_history ENABLE ROW LEVEL SECURITY;

--
-- Name: containers; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.containers ENABLE ROW LEVEL SECURITY;

--
-- Name: cross_instances; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.cross_instances ENABLE ROW LEVEL SECURITY;

--
-- Name: cross_plan_genotype_alleles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.cross_plan_genotype_alleles ENABLE ROW LEVEL SECURITY;

--
-- Name: cross_plan_runs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.cross_plan_runs ENABLE ROW LEVEL SECURITY;

--
-- Name: cross_plan_treatments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.cross_plan_treatments ENABLE ROW LEVEL SECURITY;

--
-- Name: cross_plans; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.cross_plans ENABLE ROW LEVEL SECURITY;

--
-- Name: crosses; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.crosses ENABLE ROW LEVEL SECURITY;

--
-- Name: fish; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.fish ENABLE ROW LEVEL SECURITY;

--
-- Name: fish_code_audit; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.fish_code_audit ENABLE ROW LEVEL SECURITY;

--
-- Name: fish_seed_batches; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.fish_seed_batches ENABLE ROW LEVEL SECURITY;

--
-- Name: fish_seed_batches_map; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.fish_seed_batches_map ENABLE ROW LEVEL SECURITY;

--
-- Name: fish_tank_memberships; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.fish_tank_memberships ENABLE ROW LEVEL SECURITY;

--
-- Name: fish_transgene_alleles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.fish_transgene_alleles ENABLE ROW LEVEL SECURITY;

--
-- Name: fish_year_counters; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.fish_year_counters ENABLE ROW LEVEL SECURITY;

--
-- Name: injected_plasmid_treatments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.injected_plasmid_treatments ENABLE ROW LEVEL SECURITY;

--
-- Name: injected_rna_treatments; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.injected_rna_treatments ENABLE ROW LEVEL SECURITY;

--
-- Name: label_items; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.label_items ENABLE ROW LEVEL SECURITY;

--
-- Name: label_jobs; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.label_jobs ENABLE ROW LEVEL SECURITY;

--
-- Name: load_log_fish; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.load_log_fish ENABLE ROW LEVEL SECURITY;

--
-- Name: planned_crosses; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.planned_crosses ENABLE ROW LEVEL SECURITY;

--
-- Name: plasmid_registry; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.plasmid_registry ENABLE ROW LEVEL SECURITY;

--
-- Name: plasmids; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.plasmids ENABLE ROW LEVEL SECURITY;

--
-- Name: rna_registry; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.rna_registry ENABLE ROW LEVEL SECURITY;

--
-- Name: rnas; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.rnas ENABLE ROW LEVEL SECURITY;

--
-- Name: selection_labels; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.selection_labels ENABLE ROW LEVEL SECURITY;

--
-- Name: tank_requests; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tank_requests ENABLE ROW LEVEL SECURITY;

--
-- Name: tank_year_counters; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tank_year_counters ENABLE ROW LEVEL SECURITY;

--
-- Name: transgene_allele_counters; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.transgene_allele_counters ENABLE ROW LEVEL SECURITY;

--
-- Name: transgene_allele_registry; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.transgene_allele_registry ENABLE ROW LEVEL SECURITY;

--
-- Name: transgene_alleles; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.transgene_alleles ENABLE ROW LEVEL SECURITY;

--
-- Name: transgenes; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.transgenes ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

\unrestrict 4CeWM2n2bBZdqonbufYNdVzh3XYMgcbmGhwqwOaB9f0GNlfH8DxS1H3qNDAPrWE

