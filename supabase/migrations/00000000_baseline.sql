--
-- PostgreSQL database dump
--

\restrict GHUdXR8rPjLsCUAGN1KOb22W97gNjlXTEi8Anla91LPFbCxBoNoX2i0hAEkaPYZ

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
-- Name: util_mig; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA IF NOT EXISTS util_mig;


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
-- Name: tank_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.tank_status AS ENUM (
    'vacant',
    'occupied',
    'quarantine',
    'maintenance',
    'retired',
    'decommissioned'
);


--
-- Name: _ci_resolve_tp_code(uuid, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public._ci_resolve_tp_code(p_ciid uuid, p_tp text) RETURNS text
    LANGUAGE sql
    AS $$
  select coalesce(
    nullif(p_tp, ''),
    (select ci.tank_pair_code from public.cross_instances ci where ci.id = p_ciid)
  )
$$;


--
-- Name: _sync_tank_status_after_assignment(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public._sync_tank_status_after_assignment() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_tank_id bigint;
  v_open int;
  v_cur_status public.tank_status;
  v_new_status public.tank_status;
BEGIN
  v_tank_id := COALESCE(NEW.tank_id, OLD.tank_id);

  SELECT count(*)::int
  INTO v_open
  FROM public.fish_tank_assignments
  WHERE tank_id = v_tank_id
    AND end_at IS NULL;

  SELECT status
  INTO v_cur_status
  FROM public.v_tanks_current_status
  WHERE tank_id = v_tank_id;

  IF v_open > 0 THEN
    v_new_status := 'occupied';
  ELSE
    v_new_status := 'vacant';
  END IF;

  IF v_cur_status IS DISTINCT FROM v_new_status THEN
    PERFORM public._tank_set_status(v_tank_id, v_new_status, CASE WHEN v_open > 0 THEN 'auto: fish assigned' ELSE 'auto: all fish removed' END);
  END IF;

  RETURN NULL;
END
$$;


--
-- Name: _tank_set_status(bigint, public.tank_status, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public._tank_set_status(p_tank_id bigint, p_status public.tank_status, p_reason text) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  INSERT INTO public.tank_status_history (tank_id, status, reason, changed_at)
  VALUES (p_tank_id, p_status, p_reason, clock_timestamp());
END
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
-- Name: base36(bigint); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.base36(n bigint) RETURNS text
    LANGUAGE plpgsql IMMUTABLE STRICT
    AS $$
DECLARE
  digits text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  q bigint := n;
  r int;
  out text := '';
BEGIN
  IF q IS NULL OR q < 0 THEN
    RAISE EXCEPTION 'base36(): n must be >= 0';
  END IF;
  IF q = 0 THEN
    RETURN '0';
  END IF;
  WHILE q > 0 LOOP
    r := (q % 36);
    out := substr(digits, r+1, 1) || out;
    q := q / 36;
  END LOOP;
  RETURN out;
END $$;


--
-- Name: clutch_default_genotype_from_pair(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.clutch_default_genotype_from_pair() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_tp   text;
  v_gen  text;
  v_has_elems boolean;
BEGIN
  -- If caller already provided a genotype, keep it
  IF NULLIF(trim(NEW.clutch_genotype_pretty), '') IS NOT NULL THEN
    RETURN NEW;
  END IF;

  v_tp := public._ci_resolve_tp_code(NEW.cross_instance_id, NEW.tank_pair_code);

  IF v_tp IS NULL THEN
    RETURN NEW; -- nothing we can do
  END IF;

  -- Only attempt if fish_pairs has genotype_elems
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish_pairs' AND column_name='genotype_elems'
  ) INTO v_has_elems;

  IF v_has_elems THEN
    SELECT
      NULLIF(array_to_string(fp.genotype_elems, '; '), '')
    INTO v_gen
    FROM public.tank_pairs tp
    JOIN public.fish_pairs fp ON fp.fish_pair_code = tp.fish_pair_code
    WHERE tp.tank_pair_code = v_tp
    LIMIT 1;

    IF v_gen IS NOT NULL THEN
      NEW.clutch_genotype_pretty := v_gen;
    END IF;
  END IF;

  RETURN NEW;
END
$$;


--
-- Name: clutch_rollup_recompute(uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.clutch_rollup_recompute(p_ci uuid) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_gen   text;
  v_treat text;
BEGIN
  SELECT NULLIF(trim(ci.clutch_genotype_pretty),'') INTO v_gen
  FROM public.clutch_instances ci WHERE ci.id = p_ci;

  SELECT string_agg(s.material_code, ' + ' ORDER BY s.max_created_at DESC)
    INTO v_treat
  FROM (
    SELECT material_code, max(created_at) AS max_created_at
    FROM public.clutch_instance_treatments
    WHERE clutch_instance_id = p_ci
    GROUP BY material_code
  ) s;

  UPDATE public.clutch_instances
  SET treatments_genotype_rollup =
        CASE WHEN v_gen IS NOT NULL AND v_treat IS NOT NULL
             THEN v_treat || ' > ' || v_gen
             ELSE NULL
        END,
      updated_at = COALESCE(updated_at, now())
  WHERE id = p_ci;
END
$$;


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
-- Name: ensure_active_tank_for_fish(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ensure_active_tank_for_fish(p_fish_code text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
DECLARE
  v_fish_uuid  uuid;
  v_tank_uuid  uuid;
  v_next_num   int;
  v_tank_code  text;
BEGIN
  SELECT fish_uuid INTO v_fish_uuid
  FROM public.fish
  WHERE fish_code = p_fish_code
  LIMIT 1;

  IF v_fish_uuid IS NULL THEN
    RAISE EXCEPTION 'ensure_active_tank_for_fish(): fish_code % not found', p_fish_code;
  END IF;

  SELECT t.tank_uuid
    INTO v_tank_uuid
  FROM public.tanks t
  WHERE t.status = 'active'
    AND t.tank_code LIKE ('TANK(' || p_fish_code || ')#%')
  ORDER BY t.created_at ASC
  LIMIT 1;

  IF v_tank_uuid IS NULL THEN
    SELECT COALESCE(MAX(NULLIF(split_part(tank_code, '#', 2), '')::int), 0) + 1
      INTO v_next_num
    FROM public.tanks
    WHERE tank_code LIKE ('TANK(' || p_fish_code || ')#%');

    v_tank_code := 'TANK(' || p_fish_code || ')#' || v_next_num::text;

    INSERT INTO public.tanks (tank_uuid, tank_code, status, created_at)
    VALUES (gen_random_uuid(), v_tank_code, 'active', now())
    RETURNING tank_uuid INTO v_tank_uuid;
  END IF;

  UPDATE public.fish_tank_memberships
     SET left_at = now()
   WHERE fish_uuid = v_fish_uuid
     AND left_at IS NULL
     AND tank_uuid <> v_tank_uuid;

  IF NOT EXISTS (
    SELECT 1
      FROM public.fish_tank_memberships m
     WHERE m.fish_uuid = v_fish_uuid
       AND m.tank_uuid = v_tank_uuid
       AND m.left_at IS NULL
  ) THEN
    INSERT INTO public.fish_tank_memberships (fish_uuid, tank_uuid, joined_at)
    VALUES (v_fish_uuid, v_tank_uuid, now());
  END IF;
END
$$;


--
-- Name: ensure_allele_from_csv(text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ensure_allele_from_csv(p_base text, p_nick text) RETURNS TABLE(allele_number integer, allele_name text, allele_nickname text)
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_base text := trim(p_base);
  v_nick text := nullif(trim(p_nick), '');
  v_next int;
BEGIN
  -- Ensure base exists (dynamic version already installed)
  PERFORM public.ensure_transgene_base(v_base);

  -- REUSE: same base + same nickname
  SELECT t.allele_number, t.allele_name, t.allele_nickname
    INTO allele_number, allele_name, allele_nickname
  FROM public.transgene_alleles t
  WHERE t.transgene_base_code = v_base
    AND t.allele_nickname     = v_nick
  LIMIT 1;

  IF FOUND THEN
    RETURN NEXT;
    RETURN;
  END IF;

  -- MINT: next number for this base
  SELECT COALESCE(MAX(t.allele_number), 0) + 1
    INTO v_next
  FROM public.transgene_alleles t
  WHERE t.transgene_base_code = v_base;

  INSERT INTO public.transgene_alleles
    (transgene_base_code, allele_number, allele_name, allele_nickname)
  VALUES
    (v_base, v_next, 'gu'||v_next::text, COALESCE(v_nick, 'gu'||v_next::text))
  ON CONFLICT ON CONSTRAINT uq_transgene_alleles_base_num
    DO UPDATE
      SET allele_nickname = COALESCE(EXCLUDED.allele_nickname, public.transgene_alleles.allele_nickname)
  RETURNING
    public.transgene_alleles.allele_number,
    public.transgene_alleles.allele_name,
    public.transgene_alleles.allele_nickname
  INTO allele_number, allele_name, allele_nickname;

  RETURN NEXT;
END;
$$;


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

CREATE FUNCTION public.ensure_rna_for_plasmid(p_plasmid_code text, p_suffix text DEFAULT '-RNA'::text, p_name text DEFAULT NULL::text, p_created_by text DEFAULT NULL::text, p_notes text DEFAULT NULL::text) RETURNS TABLE(rna_id uuid, rna_code text)
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_plasmid_id uuid;
  v_code text;
BEGIN
  SELECT id INTO v_plasmid_id
  FROM public.plasmids WHERE code = p_plasmid_code LIMIT 1;
  IF v_plasmid_id IS NULL THEN
    RAISE EXCEPTION 'ensure_rna_for_plasmid: plasmid code % not found', p_plasmid_code;
  END IF;

  v_code := p_plasmid_code || COALESCE(p_suffix,'-RNA');

  INSERT INTO public.rnas(code, name, source_plasmid_id, created_by, notes)
  VALUES (v_code, COALESCE(p_name, v_code), v_plasmid_id, p_created_by, p_notes)
  ON CONFLICT (code) DO UPDATE
    SET name              = COALESCE(EXCLUDED.name, public.rnas.name),
        source_plasmid_id = COALESCE(EXCLUDED.source_plasmid_id, public.rnas.source_plasmid_id),
        created_by        = COALESCE(EXCLUDED.created_by, public.rnas.created_by),
        notes             = COALESCE(EXCLUDED.notes, public.rnas.notes)
  RETURNING id, code INTO rna_id, rna_code;

  RETURN NEXT;
END;
$$;


--
-- Name: ensure_transgene_allele(text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ensure_transgene_allele(p_base text, p_nickname text) RETURNS TABLE(ret_allele_number integer, ret_allele_nickname text)
    LANGUAGE plpgsql
    AS $_$
DECLARE
  v_digits   text;
  v_num      int;
  v_pref     text;
  v_nick     text;
BEGIN
  -- Extract trailing digits from nickname (if any)
  v_digits := (regexp_match(coalesce(p_nickname,''), '(\d+)$'))[1];

  -- Honor explicit number in nickname, else allocate next
  IF v_digits ~ '^\d+$' THEN
    v_num := v_digits::int;
  ELSE
    SELECT COALESCE(MAX(ta.allele_number), 0) + 1
      INTO v_num
      FROM public.transgene_alleles ta
     WHERE ta.transgene_base_code = p_base;
  END IF;

  -- Build a nickname if one isn't provided; default prefix 'allele'
  v_pref := (regexp_match(coalesce(p_nickname,''), '^([A-Za-z]+)'))[1];
  IF v_pref IS NULL OR v_pref = '' THEN
    v_pref := 'allele';
  END IF;

  v_nick := NULLIF(trim(p_nickname), '');
  IF v_nick IS NULL OR v_digits IS NULL THEN
    v_nick := v_pref || v_num::text;
  END IF;

  -- Ensure base exists
  INSERT INTO public.transgenes(transgene_base_code)
  VALUES (p_base)
  ON CONFLICT DO NOTHING;

  -- Upsert allele row and capture the actual number/nickname returned by the table
  INSERT INTO public.transgene_alleles(transgene_base_code, allele_number, allele_nickname)
  VALUES (p_base, v_num, v_nick)
  ON CONFLICT (transgene_base_code, allele_number) DO UPDATE
    SET allele_nickname = COALESCE(EXCLUDED.allele_nickname, public.transgene_alleles.allele_nickname)
  RETURNING allele_number, allele_nickname
  INTO ret_allele_number, ret_allele_nickname;

  -- EXPLICITLY emit a row (this is what the importer expects)
  RETURN QUERY SELECT ret_allele_number, ret_allele_nickname;
END;
$_$;


--
-- Name: ensure_transgene_base(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ensure_transgene_base(p_base text) RETURNS void
    LANGUAGE plpgsql
    AS $_$
DECLARE
  v_col text;
  v_sql text;
BEGIN
  -- Detect which base-code column exists.
  SELECT CASE
           WHEN EXISTS (
             SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='transgenes'
               AND column_name='transgene_base_code'
           ) THEN 'transgene_base_code'
           WHEN EXISTS (
             SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='transgenes'
               AND column_name='base_code'
           ) THEN 'base_code'
           ELSE NULL
         END
    INTO v_col;

  IF v_col IS NULL THEN
    RAISE EXCEPTION 'transgenes table missing base-code column (expected transgene_base_code or base_code)';
  END IF;

  -- Insert base row if missing; conflict on the discovered column.
  v_sql := format(
    'INSERT INTO public.transgenes (%I) VALUES ($1)
     ON CONFLICT (%I) DO NOTHING',
    v_col, v_col
  );
  EXECUTE v_sql USING p_base;
END
$_$;


--
-- Name: fish_auto_tank(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fish_auto_tank() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
declare v_code text;
begin
  v_code := public.make_tank_code_for_fish(new.fish_code);
  -- purged: insert into public.tanks(status, tank_code) values ('active', v_code);
  return new;
end
$$;


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
    AS $$
BEGIN
  IF NEW.fish_code IS NULL OR trim(NEW.fish_code) = '' THEN
    NEW.fish_code := public.gen_fish_code_base36(now());
  END IF;
  RETURN NEW;
END $$;


--
-- Name: fish_pairs_code_autogen(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fish_pairs_code_autogen() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
declare
  candidate text;
begin
  if coalesce(new.fish_pair_code, '') = '' then
    candidate := public.make_fp_code(nextval('public.fish_pairs_code_seq'));
    new.fish_pair_code := candidate;
  end if;
  return new;
end
$$;


--
-- Name: fn_add_active_tank_for_fish(uuid, integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_add_active_tank_for_fish(p_fish_id uuid, p_capacity integer DEFAULT NULL::integer) RETURNS text
    LANGUAGE plpgsql
    AS $$
declare
  v_code text;
begin
  v_code := format('TANK-%s-#%s',
                   (select fish_code from public.fish where id=p_fish_id),
                   public.fn_next_tank_suffix(p_fish_id));

  insert into public.tanks (fish_id, tank_code, status, capacity)
  values (p_fish_id, v_code, 'active', p_capacity);

  return v_code;
end
$$;


--
-- Name: fn_insert_autotank_v2(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_insert_autotank_v2() RETURNS trigger
    LANGUAGE plpgsql
    AS $_$
begin
  insert into public.tanks (tank_id, tank_code, fish_code, rack, position, created_at, created_by)
  values (
    gen_random_uuid(),
    'TANK-' || NEW.fish_code || '-#1',
    NEW.fish_code,
    null,
    null,
    now(),
    case
      when NEW.created_by is null or NEW.created_by = '' then null
      when NEW.created_by ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$' then NEW.created_by::uuid
      else null
    end
  );
  return NEW;
end
$_$;


--
-- Name: fn_next_tank_suffix_by_code(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_next_tank_suffix_by_code(p_fish_code text) RETURNS integer
    LANGUAGE sql STABLE
    AS $$
  select coalesce(max((regexp_replace(tank_code, '.*-#', ''))::int), 0) + 1
  from public.tanks
  where fish_code = p_fish_code
$$;


--
-- Name: fn_set_tank_status(uuid, public.tank_status); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_set_tank_status(p_tank_id uuid, p_status public.tank_status) RETURNS text
    LANGUAGE plpgsql
    AS $$
declare
  v_code text;
begin
  update public.tanks
     set status=p_status, updated_at=now()
   where id=p_tank_id
   returning tank_code into v_code;

  if v_code is null then
    raise exception 'tank % not found', p_tank_id;
  end if;

  return v_code;
end
$$;


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

CREATE FUNCTION public.gen_clutch_instance_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $_$
declare
  _tp  text;
  _seq int;
begin
  if coalesce(new.tank_pair_code,'') = '' then
    raise exception 'tank_pair_code required for clutch code';
  end if;

  if coalesce(new.clutch_instance_code,'') <> '' then
    return new;
  end if;

  select ci.tank_pair_code,
         (regexp_match(ci.cross_run_code, '\((\d+)\)$'))[1]::int
    into _tp, _seq
  from public.cross_instances ci
  where ci.id = new.cross_instance_id;

  if _tp is null or _seq is null then
    raise exception 'linked cross not found or cross_run_code missing';
  end if;

  new.clutch_instance_code := format('CL(%s)(%s)', _tp, lpad(_seq::text, 2, '0'));
  return new;
end$_$;


--
-- Name: gen_cross_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_cross_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE y text := to_char(current_date,'YY'); n bigint;
BEGIN SELECT nextval('public.cross_code_seq') INTO n; RETURN format('CR-%s%05s', y, n); END;
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
-- Name: gen_fish_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_fish_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
  try int := 0;
  suffix text;
  code text;
BEGIN
  LOOP
    try := try + 1;
    suffix := upper(to_hex(nextval('public.fish_code_seq')));
    code := 'FSH-' || suffix;

    -- ensure uniqueness
    IF NOT EXISTS (SELECT 1 FROM public.fish WHERE fish_code = code) THEN
      RETURN code;
    END IF;

    IF try > 100 THEN
      RAISE EXCEPTION 'gen_fish_code(): could not allocate unique code after % attempts', try;
    END IF;
  END LOOP;
END
$$;


--
-- Name: gen_fish_code(timestamp with time zone); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_fish_code(p_when timestamp with time zone DEFAULT now()) RETURNS text
    LANGUAGE plpgsql
    SET search_path TO 'public'
    AS $$
DECLARE
  y  int  := EXTRACT(YEAR FROM p_when)::int;
  yy text := to_char(p_when, 'YY');
  n  int;
BEGIN
  INSERT INTO public.fish_year_counters(year, next_num)
  VALUES (y, 1)
  ON CONFLICT (year) DO NOTHING;

  UPDATE public.fish_year_counters
     SET next_num = next_num + 1
   WHERE year = y
   RETURNING next_num - 1 INTO n;

  RETURN 'FSH-' || yy || to_char(n, 'FM00000');
END
$$;


--
-- Name: gen_fish_code_base36(timestamp with time zone); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_fish_code_base36(p_when timestamp with time zone DEFAULT now()) RETURNS text
    LANGUAGE sql STABLE
    AS $_$
  SELECT 'FSH-' || to_char($1, 'YY') || public.base36(nextval('public.fish_code_seq36'))
$_$;


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
-- Name: gen_tank_pair_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_tank_pair_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $_$
declare
  yy text;
  nxt int;
begin
  if new.tank_pair_code is not null then
    return new;
  end if;
  perform pg_advisory_xact_lock(88123456);
  yy := to_char(current_date, 'YY');
  select coalesce(max((regexp_match(tp.tank_pair_code, '^TP-'||yy||'(\d{5})$'))[1]::int), 0) + 1
    into nxt
  from public.tank_pairs tp
  where tp.tank_pair_code like 'TP-'||yy||'%';
  new.tank_pair_code := 'TP-'||yy||lpad(nxt::text, 5, '0');
  return new;
end
$_$;


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
-- Name: link_fish_to_transgene_allele(uuid, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.link_fish_to_transgene_allele(p_fish_uuid uuid, p_base text, p_nickname text) RETURNS TABLE(fish_uuid uuid, transgene_base_code text, allele_number integer)
    LANGUAGE plpgsql
    AS $$
declare r record;
begin
  select * into r from public.upsert_transgene_allele(p_base, p_nickname);
  insert into public.fish_transgene_alleles(fish_uuid, transgene_base_code, allele_number)
  values (p_fish_uuid, r.transgene_base_code, r.allele_number)
  on conflict do nothing;
  fish_uuid := p_fish_uuid;
  transgene_base_code := r.transgene_base_code;
  allele_number := r.allele_number;
  return next;
end
$$;


--
-- Name: make_cl_code(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.make_cl_code(p_tank_pair_code text) RETURNS text
    LANGUAGE sql STABLE
    AS $$
  select 'CL(' || p_tank_pair_code || ')(' || public.next_run_nn(p_tank_pair_code) || ')'
$$;


--
-- Name: make_cr_code(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.make_cr_code(p_tank_pair_code text) RETURNS text
    LANGUAGE sql STABLE
    AS $$
  select 'CR(' || p_tank_pair_code || ')(' || public.next_run_nn(p_tank_pair_code) || ')'
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
-- Name: make_fp_code(bigint); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.make_fp_code(v bigint) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$
  select 'FP-' || lpad(public.to_base36(v), 5, '0')
$$;


--
-- Name: make_tank_code_compact(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.make_tank_code_compact() RETURNS text
    LANGUAGE sql
    AS $$
  select 'TANK-' || to_char(current_date,'YY') || util_mig._to_base36(nextval('public.tank_code_seq'), 4)
$$;


--
-- Name: make_tank_code_for_fish(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.make_tank_code_for_fish(p_fish_code text) RETURNS text
    LANGUAGE plpgsql
    AS $$
declare n int;
begin
  n := public.next_tank_num_for_fish(p_fish_code);
  return 'TANK('||p_fish_code||')#'||n::text;
end
$$;


--
-- Name: make_tp_code(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.make_tp_code(p_fish_pair_code text) RETURNS text
    LANGUAGE sql STABLE
    AS $$
  select 'TP(' || p_fish_pair_code || ')-' || public.next_tp_suffix(p_fish_pair_code)
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
-- Name: next_clutch_code_b36(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.next_clutch_code_b36() RETURNS text
    LANGUAGE plpgsql
    AS $$
declare
  v bigint := nextval('public.clutch_b36_seq');
  b text;
begin
  b := public.to_base36(v);
  if length(b) < 5 then b := lpad(b, 5, '0'); end if;
  return 'CL-' || b;
end
$$;


--
-- Name: next_fish_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.next_fish_code() RETURNS text
    LANGUAGE sql
    AS $$
  SELECT 'FSH-' || to_char(nextval('public.fish_code_seq'), 'FM000000');
$$;


--
-- Name: next_run_nn(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.next_run_nn(p_tank_pair_code text) RETURNS text
    LANGUAGE plpgsql
    AS $$
declare v int;
begin
  with up as (
    insert into public.tp_run_counters(tank_pair_code, next_nn)
    values (p_tank_pair_code, 2)
    on conflict (tank_pair_code) do update set next_nn = tp_run_counters.next_nn + 1
    returning next_nn
  )
  select next_nn - 1 into v from up;
  return lpad(v::text, 2, '0');
end $$;


--
-- Name: next_tank_num_for_fish(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.next_tank_num_for_fish(p_fish_code text) RETURNS integer
    LANGUAGE sql
    AS $$
  select coalesce(max((regexp_replace(t.tank_code, '.*#', '')::int)),0)+1
  from public.tanks t
  where t.tank_code like ('TANK('||p_fish_code||')#%')
$$;


--
-- Name: next_tp_suffix(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.next_tp_suffix(p_fish_pair_code text) RETURNS text
    LANGUAGE plpgsql
    AS $$
declare v bigint; b text;
begin
  with up as (
    insert into public.tank_pair_counters(fish_pair_code, next_nn)
    values (p_fish_pair_code, 2)
    on conflict (fish_pair_code) do update set next_nn = tank_pair_counters.next_nn + 1
    returning next_nn
  )
  select next_nn - 1 into v from up;
  b := public.to_base36(v);
  return b;
end $$;


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
-- Name: raise_exception(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.raise_exception(msg text) RETURNS integer
    LANGUAGE plpgsql
    AS $$
begin
  raise exception '%', msg;
  return 0;
end;
$$;


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
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
  new.updated_at = now();
  return new;
end;
$$;


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
-- Name: to_base36(bigint); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.to_base36(n bigint) RETURNS text
    LANGUAGE plpgsql IMMUTABLE
    AS $$
declare
  v bigint := n;
  s text := '';
  a constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  pos integer;
begin
  if v < 0 then
    raise exception 'to_base36 expects nonnegative';
  end if;
  if v = 0 then
    return '0';
  end if;
  while v > 0 loop
    pos := (v % 36)::int + 1;
    s := substr(a, pos, 1) || s;
    v := v / 36;
  end loop;
  return s;
end
$$;


--
-- Name: trg_ci_rollup_after_ci(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_ci_rollup_after_ci() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.clutch_genotype_pretty IS DISTINCT FROM OLD.clutch_genotype_pretty THEN
    PERFORM public.clutch_rollup_recompute(NEW.id);
  END IF;
  RETURN NEW;
END $$;


--
-- Name: trg_ci_rollup_after_treatment(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_ci_rollup_after_treatment() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  PERFORM public.clutch_rollup_recompute(
    COALESCE(NEW.clutch_instance_id, OLD.clutch_instance_id)
  );
  RETURN COALESCE(NEW, OLD);
END $$;


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
-- Name: trg_clutch_instances_set_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_clutch_instances_set_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
  if new.clutch_instance_code is null or new.clutch_instance_code = '' then
    if new.tank_pair_code is null or new.tank_pair_code = '' then
      raise exception 'clutch_instances.tank_pair_code required to generate CL code';
    end if;
    new.clutch_instance_code := public.make_cl_code(new.tank_pair_code);
  end if;
  return new;
end $$;


--
-- Name: trg_clutches_set_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_clutches_set_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
  if new.clutch_code is null or new.clutch_code = '' then
    new.clutch_code := public.next_clutch_code_b36();
  end if;
  return new;
end
$$;


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
-- Name: trg_cross_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_cross_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN IF NEW.cross_code IS NULL OR btrim(NEW.cross_code)='' THEN NEW.cross_code:=public.gen_cross_code(); END IF; RETURN NEW; END;
$$;


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
-- Name: trg_cross_instances_set_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_cross_instances_set_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
  if new.cross_run_code is null or new.cross_run_code = '' then
    if new.tank_pair_code is null or new.tank_pair_code = '' then
      raise exception 'cross_instances.tank_pair_code required to generate CR code';
    end if;
    new.cross_run_code := public.make_cr_code(new.tank_pair_code);
  end if;
  return new;
end $$;


--
-- Name: trg_cross_name_fill(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_cross_name_fill() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.cross_name IS NULL OR btrim(NEW.cross_name)='' THEN NEW.cross_name:=public.gen_cross_name(NEW.mother_code,NEW.father_code); END IF;
  IF NEW.cross_nickname IS NULL OR btrim(NEW.cross_nickname)='' THEN NEW.cross_nickname:=NEW.cross_name; END IF;
  RETURN NEW;
END
$$;


--
-- Name: trg_cross_run_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_cross_run_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN IF NEW.cross_run_code IS NULL OR btrim(NEW.cross_run_code)='' THEN NEW.cross_run_code:=public.gen_cross_run_code(); END IF; RETURN NEW; END;
$$;


--
-- Name: trg_fish_autotank(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_fish_autotank() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_container_id uuid;
  v_label text;
BEGIN
  v_label := CASE
               WHEN NEW.fish_code IS NOT NULL THEN format('TANK %s #1', NEW.fish_code)
               ELSE NULL
             END;

  INSERT INTO public.containers (container_type, status, label, created_by)
  VALUES ('holding_tank', 'new_tank', v_label, COALESCE(NEW.created_by, 'system'))
  RETURNING id_uuid INTO v_container_id;

  BEGIN
    INSERT INTO public.fish_tank_memberships (fish_id, container_id, started_at)
    VALUES (NEW.id_uuid, v_container_id, now());
  EXCEPTION WHEN undefined_column THEN
    INSERT INTO public.fish_tank_memberships (fish_id, container_id, joined_at)
    VALUES (NEW.id_uuid, v_container_id, now());
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
-- Name: trg_tank_pairs_require_fp(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_tank_pairs_require_fp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.fish_pair_code IS NULL THEN
    RAISE EXCEPTION 'tank_pairs.fish_pair_code must not be NULL';
  END IF;
  RETURN NEW;
END $$;


--
-- Name: trg_tank_pairs_set_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_tank_pairs_set_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
declare fp text;
begin
  fp := coalesce(new.fish_pair_code, null);
  if (new.tank_pair_code is null or new.tank_pair_code = '') and fp is not null then
    new.tank_pair_code := public.make_tp_code(fp);
  end if;
  return new;
end $$;


--
-- Name: upsert_fish_allele_from_csv(uuid, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.upsert_fish_allele_from_csv(p_fish_uuid uuid, p_base_code text, p_allele_nickname text) RETURNS TABLE(fish_uuid uuid, transgene_base_code text, allele_number integer)
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_allele_number int;
  v_fu uuid;
  v_base text;
  v_anum int;
BEGIN
  SELECT ta.allele_number
    INTO v_allele_number
  FROM public.transgene_alleles ta
  WHERE ta.transgene_base_code = p_base_code
    AND ta.allele_nickname = NULLIF(btrim(p_allele_nickname), '')
  LIMIT 1;

  IF v_allele_number IS NULL THEN
    SELECT u.out_num
      INTO v_allele_number
    FROM public.upsert_transgene_allele(p_base_code, p_allele_nickname) AS u;
  END IF;

  INSERT INTO public.fish_transgene_alleles (fish_uuid, transgene_base_code, allele_number)
  VALUES (p_fish_uuid, p_base_code, v_allele_number)
  ON CONFLICT ON CONSTRAINT con_fta_fish_uuid_base
  DO UPDATE SET allele_number = EXCLUDED.allele_number
  RETURNING public.fish_transgene_alleles.fish_uuid,
            public.fish_transgene_alleles.transgene_base_code,
            public.fish_transgene_alleles.allele_number
  INTO v_fu, v_base, v_anum;

  fish_uuid := v_fu;
  transgene_base_code := v_base;
  allele_number := v_anum;
  RETURN NEXT;
END
$$;


--
-- Name: upsert_fish_by_batch_name_dob(text, date, text, text, text, text, text, text, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.upsert_fish_by_batch_name_dob(p_batch text, p_dob date, p_seed_batch_id text, p_name text, p_bg text, p_nick text, p_stage text, p_desc text, p_notes text, p_by text) RETURNS TABLE(fish_uuid uuid, fish_code text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public'
    AS $$
BEGIN
  -- Let the BEFORE INSERT trigger mint fish_code (base36); we do NOT set it here
  RETURN QUERY
  INSERT INTO public.fish AS f (
    seed_batch_id, fish_name, fish_nickname, genetic_background, line_building_stage,
    date_birth, description, notes, created_by
  )
  VALUES (
    COALESCE(trim(p_seed_batch_id), ''),
    NULLIF(trim(p_name), ''),
    NULLIF(trim(p_nick), ''),
    NULLIF(trim(p_bg), ''),
    NULLIF(trim(p_stage), ''),
    p_dob,
    NULLIF(trim(p_desc), ''),
    NULLIF(trim(p_notes), ''),
    NULLIF(trim(p_by), '')
  )
  ON CONFLICT (seed_batch_id, name, date_birth)  -- legacy name still in natural key …
  DO UPDATE SET
    fish_nickname       = COALESCE(EXCLUDED.fish_nickname,       f.fish_nickname),
    genetic_background  = COALESCE(EXCLUDED.genetic_background,  f.genetic_background),
    line_building_stage = COALESCE(EXCLUDED.line_building_stage, f.line_building_stage),
    date_birth          = COALESCE(EXCLUDED.date_birth,          f.date_birth),
    description         = COALESCE(EXCLUDED.description,         f.description),
    notes               = COALESCE(EXCLUDED.notes,               f.notes),
    updated_at          = now()
  RETURNING f.fish_uuid, f.fish_code;
END
$$;


--
-- Name: upsert_transgene_allele(text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.upsert_transgene_allele(p_base text, p_nickname_in text) RETURNS TABLE(out_base text, out_num integer, out_name text, out_nick text)
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_nickname text := NULLIF(btrim(p_nickname_in), '');
  v_num int;
  v_name text;
  v_base text;
  v_anum int;
  v_aname text;
  v_anick text;
BEGIN
  INSERT INTO public.transgenes(transgene_base_code)
  VALUES (p_base)
  ON CONFLICT ON CONSTRAINT transgenes_pkey DO NOTHING;

  IF v_nickname IS NOT NULL THEN
    SELECT ta.transgene_base_code, ta.allele_number, ta.allele_name, ta.allele_nickname
      INTO v_base, v_anum, v_aname, v_anick
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = p_base
      AND ta.allele_nickname = v_nickname
    LIMIT 1;

    IF v_base IS NOT NULL THEN
      out_base := v_base;
      out_num  := v_anum;
      out_name := v_aname;
      out_nick := v_anick;
      RETURN NEXT;
      RETURN;
    END IF;
  END IF;

  LOOP
    BEGIN
      v_num  := nextval('public.transgene_allele_number_seq')::int;
      v_name := 'gu' || v_num::text;

      INSERT INTO public.transgene_alleles(
        transgene_base_code, allele_number, allele_name, allele_nickname
      )
      VALUES (p_base, v_num, v_name, COALESCE(v_nickname, v_name))
      RETURNING
        public.transgene_alleles.transgene_base_code,
        public.transgene_alleles.allele_number,
        public.transgene_alleles.allele_name,
        public.transgene_alleles.allele_nickname
      INTO v_base, v_anum, v_aname, v_anick;

      out_base := v_base;
      out_num  := v_anum;
      out_name := v_aname;
      out_nick := v_anick;
      RETURN NEXT;
      RETURN;

    EXCEPTION WHEN unique_violation THEN
      CONTINUE;
    END;
  END LOOP;
END
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


--
-- Name: _to_base36(bigint, integer); Type: FUNCTION; Schema: util_mig; Owner: -
--

CREATE OR REPLACE FUNCTION util_mig._to_base36(n bigint, width integer DEFAULT 4) RETURNS text
    LANGUAGE plpgsql IMMUTABLE
    AS $$
DECLARE
    digits TEXT := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    result TEXT := '';
    v BIGINT := n;
    r INT;
BEGIN
    IF n IS NULL OR n < 0 THEN
        RETURN NULL;
    END IF;

    IF v = 0 THEN
        result := '0';
    ELSE
        WHILE v > 0 LOOP
            r := (v % 36)::INT;
            result := substr(digits, r + 1, 1) || result;
            v := v / 36;
        END LOOP;
    END IF;

    WHILE length(result) < width LOOP
        result := '0' || result;
    END LOOP;

    RETURN result;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: _schema_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public._schema_version (
    key text NOT NULL,
    version text NOT NULL,
    details jsonb DEFAULT '{}'::jsonb,
    applied_at timestamp with time zone DEFAULT now() NOT NULL
);


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
-- Name: clutch_b36_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.clutch_b36_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


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
    created_at timestamp with time zone DEFAULT now()
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
    cross_instance_id uuid,
    updated_at timestamp with time zone DEFAULT now(),
    tank_pair_code text,
    clutch_instance_code text,
    clutch_genotype_pretty text,
    treatments_genotype_rollup text
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
    id uuid DEFAULT gen_random_uuid() NOT NULL
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
    clutch_instance_code text,
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clutch_code text,
    CONSTRAINT clutch_code_format_chk CHECK (((clutch_code ~ '^CL-[0-9A-Z]{5,}$'::text) OR (clutch_code ~ '^CL-[0-9]{2}-?[0-9]{3}$'::text)))
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
    CONSTRAINT chk_tank_code_shape CHECK (((tank_code IS NULL) OR (tank_code ~ '^TANK-[0-9A-Z]{2}[0-9A-Z]{4,}$'::text))),
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
    tank_pair_code text
);


--
-- Name: COLUMN cross_instances.mother_tank_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.cross_instances.mother_tank_id IS 'FK → containers.id (mom tank)';


--
-- Name: COLUMN cross_instances.father_tank_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.cross_instances.father_tank_id IS 'FK → containers.id (dad tank)';


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
    cross_name text,
    cross_nickname text,
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    CONSTRAINT chk_cross_code_shape CHECK (((cross_code IS NULL) OR (cross_code ~ '^CROSS-[0-9A-Z]{2}[0-9A-Z]{4,}$'::text)))
);


--
-- Name: fish; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish (
    fish_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    fish_code text NOT NULL,
    name text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    date_birth date,
    nickname text,
    line_building_stage text,
    genetic_background text,
    description text,
    notes text,
    updated_at timestamp with time zone DEFAULT now(),
    fish_name text,
    fish_nickname text,
    seed_batch_id text DEFAULT ''::text NOT NULL,
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
-- Name: fish_code_seq36; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fish_code_seq36
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fish_pairs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish_pairs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    mom_fish_id uuid NOT NULL,
    dad_fish_id uuid NOT NULL,
    created_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    fish_pair_code text,
    genotype_elems text[]
);


--
-- Name: fish_pairs_code_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fish_pairs_code_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


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
    link_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    fish_uuid uuid NOT NULL,
    tank_uuid uuid NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    ended_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    joined_at timestamp with time zone,
    left_at timestamp with time zone
);


--
-- Name: fish_transgene_alleles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish_transgene_alleles (
    fish_uuid uuid NOT NULL,
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
    updated_at timestamp with time zone DEFAULT now(),
    next_num integer DEFAULT 1 NOT NULL
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
-- Name: mounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mounts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    clutch_instance_id uuid NOT NULL,
    mount_code text NOT NULL,
    time_mounted timestamp with time zone DEFAULT now() NOT NULL,
    mounting_orientation text NOT NULL,
    n_top integer DEFAULT 0,
    n_bottom integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    notes text
);


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
    cross_id uuid,
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
-- Name: tank_code_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tank_code_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tank_pair_counters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tank_pair_counters (
    fish_pair_code text NOT NULL,
    next_nn bigint DEFAULT 1 NOT NULL
);


--
-- Name: tank_pairs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tank_pairs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    fish_pair_id uuid,
    mother_tank_id uuid,
    father_tank_id uuid,
    tank_pair_code text,
    concept_id uuid,
    status text DEFAULT 'selected'::text,
    created_by text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    fish_pair_code text NOT NULL,
    note text
);


--
-- Name: TABLE tank_pairs; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.tank_pairs IS 'tank-centric pairing table; joins mom/dad tanks';


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
-- Name: tank_status_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tank_status_history (
    status public.tank_status NOT NULL,
    reason text,
    changed_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    changed_by uuid DEFAULT auth.uid(),
    tsh_id bigint NOT NULL,
    tank_uuid uuid
);


--
-- Name: tank_status_history_tsh_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tank_status_history_tsh_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tank_status_history_tsh_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tank_status_history_tsh_id_seq OWNED BY public.tank_status_history.tsh_id;


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
-- Name: tanks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tanks (
    tank_id bigint NOT NULL,
    tank_code text NOT NULL,
    rack text,
    "position" text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by uuid DEFAULT auth.uid(),
    fish_code text,
    tank_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    CONSTRAINT chk_tanks_status CHECK ((status = ANY (ARRAY['active'::text, 'new'::text, 'retired'::text, 'archived'::text])))
);


--
-- Name: tanks_tank_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tanks_tank_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tanks_tank_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tanks_tank_id_seq OWNED BY public.tanks.tank_id;


--
-- Name: tp_run_counters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tp_run_counters (
    tank_pair_code text NOT NULL,
    next_nn integer DEFAULT 1 NOT NULL
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
-- Name: transgene_alleles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transgene_alleles (
    transgene_base_code text NOT NULL,
    allele_number integer NOT NULL,
    allele_nickname text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    allele_name text NOT NULL
);


--
-- Name: transgene_global_allele_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transgene_global_allele_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


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
-- Name: v_clutch_annotations; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutch_annotations AS
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
-- Name: v_clutch_instances; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutch_instances AS
 WITH t AS (
         SELECT cit.clutch_instance_id AS ci_id,
            (count(*))::integer AS treatments_count_effective,
            COALESCE(string_agg(DISTINCT cit.material_code, ' + '::text), ''::text) AS treatments_pretty_effective
           FROM public.clutch_instance_treatments cit
          GROUP BY cit.clutch_instance_id
        ), base AS (
         SELECT COALESCE(ci.clutch_instance_code, ('CI-'::text || substr((ci.id)::text, 1, 8))) AS clutch_code,
            ((COALESCE(x.cross_date, (x.created_at)::date, (ci.created_at)::date) + '1 day'::interval))::date AS clutch_birthday,
            COALESCE(x.cross_run_code, ''::text) AS cross_name_pretty,
            ''::text AS clutch_name,
            ''::text AS clutch_genotype_pretty,
            ''::text AS clutch_strain_pretty,
            COALESCE(t.treatments_count_effective, 0) AS treatments_count_effective,
            COALESCE(t.treatments_pretty_effective, ''::text) AS treatments_pretty_effective,
            NULLIF(TRIM(BOTH ' '::text FROM COALESCE(t.treatments_pretty_effective, ''::text)), ''::text) AS genotype_treatment_rollup_effective,
            COALESCE(x.created_by, ''::text) AS created_by_instance,
            ci.created_at AS created_at_instance
           FROM ((public.clutch_instances ci
             LEFT JOIN public.cross_instances x ON ((x.id = ci.cross_instance_id)))
             LEFT JOIN t ON ((t.ci_id = ci.id)))
        )
 SELECT clutch_code,
    clutch_birthday,
    cross_name_pretty,
    clutch_name,
    clutch_genotype_pretty,
    clutch_strain_pretty,
    treatments_count_effective,
    treatments_pretty_effective,
    genotype_treatment_rollup_effective,
    created_by_instance,
    created_at_instance
   FROM base
  ORDER BY created_at_instance DESC NULLS LAST, clutch_code;


--
-- Name: v_clutch_instances_display; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutch_instances_display AS
 SELECT clutch_code,
    clutch_birthday,
    COALESCE(cross_name_pretty, ''::text) AS cross_name_pretty,
    COALESCE(clutch_name, ''::text) AS clutch_name,
    COALESCE(clutch_genotype_pretty, ''::text) AS clutch_genotype_pretty,
    COALESCE(clutch_strain_pretty, ''::text) AS clutch_strain_pretty,
    COALESCE(treatments_count_effective, 0) AS treatments_count_effective,
    COALESCE(treatments_pretty_effective, ''::text) AS treatments_pretty_effective,
    COALESCE(genotype_treatment_rollup_effective,
        CASE
            WHEN ((COALESCE(treatments_pretty_effective, ''::text) <> ''::text) AND (COALESCE(clutch_genotype_pretty, ''::text) <> ''::text)) THEN ((treatments_pretty_effective || ' > '::text) || clutch_genotype_pretty)
            WHEN (COALESCE(treatments_pretty_effective, ''::text) <> ''::text) THEN treatments_pretty_effective
            ELSE COALESCE(clutch_genotype_pretty, ''::text)
        END) AS genotype_treatment_rollup_effective,
    COALESCE(created_by_instance, ''::text) AS created_by_instance,
    created_at_instance,
    COALESCE(NULLIF(clutch_name, ''::text), clutch_code) AS clutch_label,
    COALESCE(NULLIF(clutch_genotype_pretty, ''::text), treatments_pretty_effective, ''::text) AS genotype_label,
    ''::text AS parent_genotype_pretty
   FROM public.v_clutch_instances vci
  ORDER BY clutch_code;


--
-- Name: v_clutch_instances_effective; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutch_instances_effective AS
 SELECT v.clutch_code,
    v.clutch_birthday,
    v.cross_name_pretty,
    COALESCE(NULLIF(v.clutch_name, ''::text), v.clutch_code) AS clutch_name_effective,
    COALESCE(NULLIF(ci.clutch_genotype_pretty, ''::text), NULLIF(v.clutch_genotype_pretty, ''::text), ''::text) AS clutch_genotype_effective,
    COALESCE(v.treatments_count_effective, 0) AS treatments_count_effective,
    COALESCE(v.treatments_pretty_effective, ''::text) AS treatments_pretty_effective,
    COALESCE(NULLIF(ci.treatments_genotype_rollup, ''::text), NULLIF(v.genotype_treatment_rollup_effective, ''::text),
        CASE
            WHEN ((COALESCE(v.treatments_pretty_effective, ''::text) <> ''::text) AND (COALESCE(v.clutch_genotype_pretty, ''::text) <> ''::text)) THEN ((v.treatments_pretty_effective || ' > '::text) || v.clutch_genotype_pretty)
            WHEN (COALESCE(v.treatments_pretty_effective, ''::text) <> ''::text) THEN v.treatments_pretty_effective
            ELSE COALESCE(v.clutch_genotype_pretty, ''::text)
        END) AS treatments_genotype_effective,
    v.created_by_instance,
    v.created_at_instance
   FROM (public.v_clutch_instances_display v
     JOIN public.clutch_instances ci ON ((ci.clutch_instance_code = v.clutch_code)))
  ORDER BY v.created_at_instance DESC NULLS LAST, v.clutch_code;


--
-- Name: v_clutch_treatments; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutch_treatments AS
 SELECT clutch_instance_id,
    (count(*))::integer AS treatments_count,
    string_agg(COALESCE(material_code, ''::text), ' + '::text ORDER BY created_at DESC NULLS LAST) AS treatments_pretty,
    max(created_at) AS last_treatment_at
   FROM public.clutch_instance_treatments cit
  GROUP BY clutch_instance_id;


--
-- Name: v_clutches; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutches AS
 SELECT clutch_code,
    clutch_birthday,
    cross_name_pretty,
    clutch_name,
    clutch_genotype_pretty,
    clutch_strain_pretty,
    treatments_count_effective,
    treatments_pretty_effective,
    genotype_treatment_rollup_effective,
    created_by_instance,
    created_at_instance
   FROM public.v_clutch_instances;


--
-- Name: v_clutches_for_entry; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutches_for_entry AS
 SELECT clutch_code,
    clutch_birthday,
    cross_name_pretty,
    clutch_name,
    clutch_genotype_pretty,
    clutch_strain_pretty,
    treatments_count_effective,
    treatments_pretty_effective,
    genotype_treatment_rollup_effective,
    created_by_instance,
    created_at_instance
   FROM public.v_clutch_instances
  ORDER BY clutch_code;


--
-- Name: v_clutches_overview; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutches_overview AS
 WITH tcounts AS (
         SELECT ct.clutch_id,
            (count(*))::integer AS treatments_count,
            max(ct.at_time) AS last_treatment_at,
            string_agg(COALESCE(((ct.type || ':'::text) || ct.note), ct.type), '; '::text ORDER BY ct.at_time DESC NULLS LAST) AS treatments_pretty
           FROM public.clutch_treatments ct
          GROUP BY ct.clutch_id
        )
 SELECT ci.id AS clutch_instance_id,
    ci.clutch_instance_code,
    ci.label AS clutch_label,
    ci.phenotype,
    ci.notes,
    ci.red_selected,
    ci.green_selected,
    ci.cross_instance_id,
    ci.created_at,
    ci.updated_at,
    ci.tank_pair_code,
    tc.treatments_count,
    tc.treatments_pretty,
    tc.last_treatment_at
   FROM (public.clutch_instances ci
     LEFT JOIN tcounts tc ON ((tc.clutch_id = ci.id)));


--
-- Name: v_conventions_checks; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_conventions_checks AS
 WITH pk_fish AS (
         SELECT (EXISTS ( SELECT 1
                   FROM (information_schema.table_constraints tc
                     JOIN information_schema.key_column_usage k ON ((((tc.constraint_name)::name = (k.constraint_name)::name) AND ((tc.table_schema)::name = (k.table_schema)::name) AND ((tc.table_name)::name = (k.table_name)::name))))
                  WHERE (((tc.table_schema)::name = 'public'::name) AND ((tc.table_name)::name = 'fish'::name) AND ((tc.constraint_type)::text = 'PRIMARY KEY'::text) AND ((k.column_name)::name = 'fish_uuid'::name)))) AS ok
        ), pk_tanks AS (
         SELECT (EXISTS ( SELECT 1
                   FROM (information_schema.table_constraints tc
                     JOIN information_schema.key_column_usage k ON ((((tc.constraint_name)::name = (k.constraint_name)::name) AND ((tc.table_schema)::name = (k.table_schema)::name) AND ((tc.table_name)::name = (k.table_name)::name))))
                  WHERE (((tc.table_schema)::name = 'public'::name) AND ((tc.table_name)::name = 'tanks'::name) AND ((tc.constraint_type)::text = 'PRIMARY KEY'::text) AND ((k.column_name)::name = 'tank_uuid'::name)))) AS ok
        ), ftm_cols AS (
         SELECT ((EXISTS ( SELECT 1
                   FROM information_schema.tables
                  WHERE (((tables.table_schema)::name = 'public'::name) AND ((tables.table_name)::name = 'fish_tank_memberships'::name)))) AND (EXISTS ( SELECT 1
                   FROM information_schema.columns
                  WHERE (((columns.table_schema)::name = 'public'::name) AND ((columns.table_name)::name = 'fish_tank_memberships'::name) AND ((columns.column_name)::name = 'fish_uuid'::name)))) AND (EXISTS ( SELECT 1
                   FROM information_schema.columns
                  WHERE (((columns.table_schema)::name = 'public'::name) AND ((columns.table_name)::name = 'fish_tank_memberships'::name) AND ((columns.column_name)::name = 'tank_uuid'::name)))) AND (EXISTS ( SELECT 1
                   FROM information_schema.columns
                  WHERE (((columns.table_schema)::name = 'public'::name) AND ((columns.table_name)::name = 'fish_tank_memberships'::name) AND ((columns.column_name)::name = 'started_at'::name)))) AND (EXISTS ( SELECT 1
                   FROM information_schema.columns
                  WHERE (((columns.table_schema)::name = 'public'::name) AND ((columns.table_name)::name = 'fish_tank_memberships'::name) AND ((columns.column_name)::name = 'ended_at'::name))))) AS ok
        ), idx_active AS (
         SELECT (EXISTS ( SELECT 1
                   FROM ((pg_class c
                     JOIN pg_index i ON ((i.indexrelid = c.oid)))
                     JOIN pg_class t ON ((t.oid = i.indrelid)))
                  WHERE ((c.relname = 'uq_tank_active'::name) AND (t.relname = 'fish_tank_memberships'::name) AND (pg_get_expr(i.indpred, i.indrelid) ~~* '%ended_at IS NULL%'::text)))) AS ok
        ), trg_updated AS (
         SELECT (EXISTS ( SELECT 1
                   FROM pg_trigger
                  WHERE (pg_trigger.tgname = 'trg_fish_tank_memberships_updated_at'::name))) AS ok
        )
 SELECT check_name,
    ok,
    details
   FROM ( SELECT 'fish_pk_is_fish_uuid'::text AS check_name,
            ( SELECT pk_fish.ok
                   FROM pk_fish) AS ok,
            'PK(fish.fish_uuid)'::text AS details
        UNION ALL
         SELECT 'tanks_pk_is_tank_uuid'::text,
            ( SELECT pk_tanks.ok
                   FROM pk_tanks) AS ok,
            'PK(tanks.tank_uuid)'::text
        UNION ALL
         SELECT 'ftm_required_columns'::text,
            ( SELECT ftm_cols.ok
                   FROM ftm_cols) AS ok,
            'fish_uuid,tank_uuid,started_at,ended_at'::text
        UNION ALL
         SELECT 'ftm_one_active_fish_per_tank'::text,
            ( SELECT idx_active.ok
                   FROM idx_active) AS ok,
            'uq_tank_active with predicate ended_at IS NULL'::text
        UNION ALL
         SELECT 'ftm_updated_at_trigger'::text,
            ( SELECT trg_updated.ok
                   FROM trg_updated) AS ok,
            'trigger trg_fish_tank_memberships_updated_at'::text) s;


--
-- Name: v_tanks; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_tanks AS
 SELECT t.tank_uuid,
    t.tank_code,
    t.status,
    t.created_at,
    m.joined_at,
    f.fish_uuid,
    f.fish_code
   FROM ((public.fish_tank_memberships m
     JOIN public.tanks t ON (((t.tank_uuid = m.tank_uuid) AND (t.status = 'active'::text))))
     JOIN public.fish f ON ((f.fish_uuid = m.fish_uuid)))
  WHERE (m.left_at IS NULL);


--
-- Name: v_fish_rich; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_fish_rich AS
 WITH tcounts AS (
         SELECT v.fish_code,
            (count(*))::integer AS n_active_tanks
           FROM public.v_tanks v
          GROUP BY v.fish_code
        ), alleles AS (
         SELECT f_1.fish_uuid,
            f_1.fish_code,
            fta.transgene_base_code,
            fta.allele_number,
            ta.allele_nickname,
            ('gu'::text || (fta.allele_number)::text) AS allele_code,
            ((('Tg('::text || fta.transgene_base_code) || ')'::text) || ('gu'::text || (fta.allele_number)::text)) AS transgene_pretty
           FROM ((public.fish f_1
             LEFT JOIN public.fish_transgene_alleles fta ON ((fta.fish_uuid = f_1.fish_uuid)))
             LEFT JOIN public.transgene_alleles ta ON (((ta.transgene_base_code = fta.transgene_base_code) AND (ta.allele_number = fta.allele_number))))
        ), geno AS (
         SELECT a_1.fish_uuid,
            string_agg(a_1.transgene_pretty, '; '::text ORDER BY a_1.transgene_pretty) AS genotype_rollup
           FROM alleles a_1
          GROUP BY a_1.fish_uuid
        )
 SELECT f.fish_uuid,
    f.fish_code,
    COALESCE(f.fish_name, f.name, ''::text) AS fish_name,
    COALESCE(f.fish_nickname, f.nickname, ''::text) AS fish_nickname,
    f.genetic_background,
    f.line_building_stage,
    f.date_birth,
    COALESCE(a.allele_number, 0) AS allele_number,
    COALESCE(a.allele_code, ''::text) AS allele_code,
    COALESCE(tc.n_active_tanks, 0) AS n_active_tanks,
    COALESCE(a.transgene_pretty, ''::text) AS transgene_pretty,
    COALESCE(g.genotype_rollup, ''::text) AS genotype_rollup,
    f.created_at
   FROM (((public.fish f
     LEFT JOIN alleles a ON ((a.fish_uuid = f.fish_uuid)))
     LEFT JOIN tcounts tc ON ((tc.fish_code = f.fish_code)))
     LEFT JOIN geno g ON ((g.fish_uuid = f.fish_uuid)))
  ORDER BY f.fish_code, a.transgene_pretty;


--
-- Name: v_tank_pairs; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_tank_pairs AS
 SELECT tp.tank_pair_code,
    fp.fish_pair_code,
    fm.fish_code AS mom_fish_code,
    fd.fish_code AS dad_fish_code,
    tm.tank_code AS mother_tank_code,
    tf.tank_code AS father_tank_code
   FROM (((((public.tank_pairs tp
     LEFT JOIN public.fish_pairs fp ON ((fp.fish_pair_code = tp.fish_pair_code)))
     LEFT JOIN public.fish fm ON ((fm.fish_uuid = fp.mom_fish_id)))
     LEFT JOIN public.fish fd ON ((fd.fish_uuid = fp.dad_fish_id)))
     LEFT JOIN public.tanks tm ON ((tm.tank_uuid = tp.mother_tank_id)))
     LEFT JOIN public.tanks tf ON ((tf.tank_uuid = tp.father_tank_id)));


--
-- Name: v_cross_clutch_instances; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_cross_clutch_instances AS
 WITH mom AS (
         SELECT r.fish_code,
            r.genotype_rollup AS mom_genotype
           FROM public.v_fish_rich r
        ), dad AS (
         SELECT r.fish_code,
            r.genotype_rollup AS dad_genotype
           FROM public.v_fish_rich r
        )
 SELECT x.id AS cross_instance_id,
    x.cross_run_code AS cross_code,
    x.tank_pair_code,
    tp.fish_pair_code,
    tp.mom_fish_code,
    tp.dad_fish_code,
    tp.mother_tank_code AS mom_tank_code,
    tp.father_tank_code AS dad_tank_code,
    COALESCE(m.mom_genotype, ''::text) AS mom_genotype,
    COALESCE(d.dad_genotype, ''::text) AS dad_genotype,
    NULL::text AS clutch_genotype,
    x.cross_date,
    x.created_at AS cross_created_at,
    ci.id AS clutch_instance_id,
    ci.clutch_instance_code AS clutch_code,
    ci.created_at AS clutch_created_at
   FROM ((((public.cross_instances x
     LEFT JOIN public.v_tank_pairs tp ON ((tp.tank_pair_code = x.tank_pair_code)))
     LEFT JOIN mom m ON ((m.fish_code = tp.mom_fish_code)))
     LEFT JOIN dad d ON ((d.fish_code = tp.dad_fish_code)))
     LEFT JOIN public.clutch_instances ci ON ((ci.cross_instance_id = x.id)));


--
-- Name: v_crosses; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_crosses AS
 SELECT ci.cross_run_code AS cr_code,
    ci.cross_run_code AS cross_code,
    ci.tank_pair_code AS tp_code,
    tp.fish_pair_code AS fp_code,
    c.id AS cross_id,
    c.created_at,
    c.created_by,
    c.mother_code,
    c.father_code
   FROM ((public.cross_instances ci
     LEFT JOIN public.tank_pairs tp ON ((tp.tank_pair_code = ci.tank_pair_code)))
     LEFT JOIN public.crosses c ON ((c.id = ci.cross_id)));


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
-- Name: v_fish; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_fish AS
 WITH first_tank AS (
         SELECT DISTINCT ON (t.fish_code) t.fish_code,
            t.tank_code AS first_tank_code,
            t.created_at AS first_tank_at
           FROM public.tanks t
          WHERE ((t.fish_code IS NOT NULL) AND (t.fish_code <> ''::text))
          ORDER BY t.fish_code, t.created_at, t.tank_code
        ), tank_counts AS (
         SELECT tanks.fish_code,
            (count(*))::integer AS n_tanks
           FROM public.tanks
          WHERE ((tanks.fish_code IS NOT NULL) AND (tanks.fish_code <> ''::text))
          GROUP BY tanks.fish_code
        )
 SELECT f.fish_uuid AS fish_id,
    f.fish_code,
    f.created_at,
    f.created_by,
    ft.first_tank_code,
    ft.first_tank_at,
    COALESCE(tc.n_tanks, 0) AS n_tanks
   FROM ((public.fish f
     LEFT JOIN first_tank ft ON ((ft.fish_code = f.fish_code)))
     LEFT JOIN tank_counts tc ON ((tc.fish_code = f.fish_code)));


--
-- Name: v_fish_current_tank_counts; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_fish_current_tank_counts AS
 SELECT f.fish_uuid,
    (count(t.tank_uuid))::integer AS current_tanks
   FROM ((public.fish f
     LEFT JOIN public.fish_tank_memberships m ON (((m.fish_uuid = f.fish_uuid) AND (m.ended_at IS NULL))))
     LEFT JOIN public.tanks t ON ((t.tank_uuid = m.tank_uuid)))
  WHERE (COALESCE(t.status, 'active'::text) = ANY (ARRAY['active'::text, 'living'::text]))
  GROUP BY f.fish_uuid;


--
-- Name: v_fish_genotypes; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_fish_genotypes AS
 SELECT fish_uuid,
    NULL::text AS transgene_pretty,
    NULL::text AS genotype_rollup
   FROM public.fish f;


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
-- Name: v_overview_mounts; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_overview_mounts AS
 SELECT mount_code,
    time_mounted,
    mounting_orientation,
    clutch_instance_id,
    NULL::integer AS treatments_count_effective,
    NULL::text AS treatments_pretty_effective,
    NULL::text AS genotype_treatment_rollup_effective,
    NULL::text AS parent_genotype_pretty
   FROM public.mounts m
  ORDER BY time_mounted DESC NULLS LAST;


--
-- Name: v_plasmids; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_plasmids AS
 SELECT p.id AS vid,
    p.code AS v_code,
    p.name AS v_name,
    p.nickname AS v_nickname,
    p.fluors AS v_fluors,
    p.resistance AS v_resistance,
    p.supports_invitro_rna AS v_supports_invitro_rna,
    NULLIF(p.created_by, ''::text) AS v_created_by,
    p.notes AS v_notes,
    p.created_at AS v_created_at,
    NULL::uuid AS v_rna_id,
    NULL::text AS v_rna_code,
    NULL::text AS v_rna_name
   FROM (public.plasmids p
     LEFT JOIN public.plasmid_registry r ON ((r.plasmid_code = p.code)));


--
-- Name: v_rna_plasmids; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_rna_plasmids AS
 SELECT code,
    name,
    nickname,
    created_at,
    created_by
   FROM public.plasmids
  WHERE (COALESCE(supports_invitro_rna, false) = true);


--
-- Name: v_tank_pairs_canonical; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_tank_pairs_canonical AS
 WITH fp AS (
         SELECT fp_1.fish_pair_code,
            fp_1.mom_fish_id,
            fp_1.dad_fish_id,
            fp_1.created_at AS pair_created_at,
            fm.fish_code AS mom_fish_code,
            fd.fish_code AS dad_fish_code
           FROM ((public.fish_pairs fp_1
             LEFT JOIN public.fish fm ON ((fm.fish_uuid = fp_1.mom_fish_id)))
             LEFT JOIN public.fish fd ON ((fd.fish_uuid = fp_1.dad_fish_id)))
        )
 SELECT tp.tank_pair_code,
    tp.fish_pair_code,
    fp.mom_fish_id,
    fp.dad_fish_id,
    fp.mom_fish_code,
    fp.dad_fish_code,
    mom_t.tank_code AS mother_tank_code,
    dad_t.tank_code AS father_tank_code,
    tp.created_at AS tank_pair_created_at,
    fp.pair_created_at
   FROM (((public.tank_pairs tp
     LEFT JOIN fp ON ((fp.fish_pair_code = tp.fish_pair_code)))
     LEFT JOIN LATERAL ( SELECT t.tank_code
           FROM public.tanks t
          WHERE (t.fish_code = fp.mom_fish_code)
          ORDER BY t.created_at, t.tank_code
         LIMIT 1) mom_t ON (true))
     LEFT JOIN LATERAL ( SELECT t.tank_code
           FROM public.tanks t
          WHERE (t.fish_code = fp.dad_fish_code)
          ORDER BY t.created_at, t.tank_code
         LIMIT 1) dad_t ON (true));


--
-- Name: v_transgene_alleles; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_transgene_alleles AS
 SELECT fish_uuid,
    0 AS allele_number,
    NULL::text AS allele_code
   FROM public.fish f;


--
-- Name: fish_code_audit id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_code_audit ALTER COLUMN id SET DEFAULT nextval('public.fish_code_audit_id_seq'::regclass);


--
-- Name: tank_status_history tsh_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_status_history ALTER COLUMN tsh_id SET DEFAULT nextval('public.tank_status_history_tsh_id_seq'::regclass);


--
-- Name: tanks tank_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tanks ALTER COLUMN tank_id SET DEFAULT nextval('public.tanks_tank_id_seq'::regclass);


--
-- Name: _schema_version _schema_version_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public._schema_version
    ADD CONSTRAINT _schema_version_pkey PRIMARY KEY (key);


--
-- Name: allele_nicknames allele_nicknames_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.allele_nicknames
    ADD CONSTRAINT allele_nicknames_pkey PRIMARY KEY (base_code, allele_code);


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
-- Name: fish_transgene_alleles con_fta_fish_uuid_base; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_transgene_alleles
    ADD CONSTRAINT con_fta_fish_uuid_base UNIQUE (fish_uuid, transgene_base_code);


--
-- Name: fish_pairs con_uq_fish_pairs_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_pairs
    ADD CONSTRAINT con_uq_fish_pairs_code UNIQUE (fish_pair_code);


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
    ADD CONSTRAINT fish_pkey PRIMARY KEY (fish_uuid);


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
    ADD CONSTRAINT fish_tank_memberships_pkey PRIMARY KEY (link_uuid);


--
-- Name: fish_transgene_alleles fish_transgene_alleles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_transgene_alleles
    ADD CONSTRAINT fish_transgene_alleles_pkey PRIMARY KEY (fish_uuid, transgene_base_code, allele_number);


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
-- Name: mounts mounts_mount_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mounts
    ADD CONSTRAINT mounts_mount_code_key UNIQUE (mount_code);


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
-- Name: tank_pair_counters tank_pair_counters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_pair_counters
    ADD CONSTRAINT tank_pair_counters_pkey PRIMARY KEY (fish_pair_code);


--
-- Name: tank_pairs tank_pairs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_pairs
    ADD CONSTRAINT tank_pairs_pkey PRIMARY KEY (id);


--
-- Name: tank_pairs tank_pairs_tank_pair_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_pairs
    ADD CONSTRAINT tank_pairs_tank_pair_code_key UNIQUE (tank_pair_code);


--
-- Name: tank_requests tank_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_requests
    ADD CONSTRAINT tank_requests_pkey PRIMARY KEY (id);


--
-- Name: tank_status_history tank_status_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_status_history
    ADD CONSTRAINT tank_status_history_pkey PRIMARY KEY (tsh_id);


--
-- Name: tank_year_counters tank_year_counters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_year_counters
    ADD CONSTRAINT tank_year_counters_pkey PRIMARY KEY (year);


--
-- Name: tanks tanks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tanks
    ADD CONSTRAINT tanks_pkey PRIMARY KEY (tank_uuid);


--
-- Name: tanks tanks_tank_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tanks
    ADD CONSTRAINT tanks_tank_code_key UNIQUE (tank_code);


--
-- Name: tp_run_counters tp_run_counters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tp_run_counters
    ADD CONSTRAINT tp_run_counters_pkey PRIMARY KEY (tank_pair_code);


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
-- Name: fish uq_fish_seed_name_dob; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT uq_fish_seed_name_dob UNIQUE (seed_batch_id, name, date_birth);


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
-- Name: transgene_alleles uq_transgene_alleles_base_num; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgene_alleles
    ADD CONSTRAINT uq_transgene_alleles_base_num UNIQUE (transgene_base_code, allele_number);


--
-- Name: cit_clutch_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX cit_clutch_idx ON public.clutch_instance_treatments USING btree (clutch_instance_id);


--
-- Name: fish_pairs_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX fish_pairs_created_idx ON public.fish_pairs USING btree (created_at DESC);


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

CREATE INDEX idx_fta_fish_id ON public.fish_transgene_alleles USING btree (fish_uuid);


--
-- Name: idx_ftm_fish_open; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ftm_fish_open ON public.fish_tank_memberships USING btree (fish_uuid) WHERE (left_at IS NULL);


--
-- Name: idx_ftm_tank_open; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ftm_tank_open ON public.fish_tank_memberships USING btree (tank_uuid) WHERE (left_at IS NULL);


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
-- Name: ix_bruker_mounts_selection_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bruker_mounts_selection_date ON public.bruker_mounts USING btree (selection_id, mount_date);


--
-- Name: ix_ci_cross_instance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ci_cross_instance_id ON public.clutch_instances USING btree (cross_instance_id);


--
-- Name: ix_clutch_instances_annotated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clutch_instances_annotated_at ON public.clutch_instances USING btree (annotated_at);


--
-- Name: ix_clutch_instances_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clutch_instances_created_at ON public.clutch_instances USING btree (created_at);


--
-- Name: ix_cross_instances_cross_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cross_instances_cross_id ON public.cross_instances USING btree (cross_id);


--
-- Name: ix_cross_instances_father_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cross_instances_father_id ON public.cross_instances USING btree (father_tank_id);


--
-- Name: ix_cross_instances_mother_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cross_instances_mother_id ON public.cross_instances USING btree (mother_tank_id);


--
-- Name: ix_injected_rna_treatments_rna; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_injected_rna_treatments_rna ON public.injected_rna_treatments USING btree (rna_id);


--
-- Name: ix_mounts_clutch_instance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mounts_clutch_instance_id ON public.mounts USING btree (clutch_instance_id);


--
-- Name: ix_mounts_time_mounted; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mounts_time_mounted ON public.mounts USING btree (time_mounted DESC);


--
-- Name: ix_plasmids_v_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_plasmids_v_code ON public.plasmids USING btree (code);


--
-- Name: ix_registry_base_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_registry_base_code ON public.transgene_allele_registry USING btree (base_code);


--
-- Name: uniq_registry_base_legacy; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uniq_registry_base_legacy ON public.transgene_allele_registry USING btree (base_code, legacy_label) WHERE ((base_code IS NOT NULL) AND (legacy_label IS NOT NULL));


--
-- Name: uniq_registry_modern_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uniq_registry_modern_key ON public.transgene_allele_registry USING btree (transgene_base_code, allele_nickname) WHERE ((transgene_base_code IS NOT NULL) AND (allele_nickname IS NOT NULL));


--
-- Name: uq_clutch_instance_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_clutch_instance_code ON public.clutch_instances USING btree (clutch_instance_code) WHERE (clutch_instance_code IS NOT NULL);


--
-- Name: uq_clutch_instance_treatments_dedup; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_clutch_instance_treatments_dedup ON public.clutch_instance_treatments USING btree (clutch_instance_id, lower(COALESCE(material_type, ''::text)), lower(COALESCE(material_code, ''::text)));


--
-- Name: uq_clutch_plans_clutch_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_clutch_plans_clutch_code ON public.clutch_plans USING btree (clutch_code);


--
-- Name: uq_clutches_clutch_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_clutches_clutch_code ON public.clutches USING btree (clutch_code) WHERE (clutch_code IS NOT NULL);


--
-- Name: uq_clutches_instance_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_clutches_instance_code ON public.clutches USING btree (clutch_instance_code) WHERE (clutch_instance_code IS NOT NULL);


--
-- Name: uq_clutches_planned_by_date; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_clutches_planned_by_date ON public.clutches USING btree (planned_cross_id, date_birth);


--
-- Name: uq_containers_tank_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_containers_tank_code ON public.containers USING btree (tank_code) WHERE (tank_code IS NOT NULL);


--
-- Name: uq_cross_run_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_cross_run_code ON public.cross_instances USING btree (cross_run_code) WHERE (cross_run_code IS NOT NULL);


--
-- Name: uq_crosses_concept_pair; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_crosses_concept_pair ON public.crosses USING btree (upper(TRIM(BOTH FROM mother_code)), upper(TRIM(BOTH FROM father_code)));


--
-- Name: uq_crosses_cross_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_crosses_cross_code ON public.crosses USING btree (cross_code) WHERE (cross_code IS NOT NULL);


--
-- Name: uq_fish_pairs_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_fish_pairs_code ON public.fish_pairs USING btree (fish_pair_code);


--
-- Name: uq_fish_tank_started; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_fish_tank_started ON public.fish_tank_memberships USING btree (fish_uuid, tank_uuid, started_at);


--
-- Name: uq_fsbm_batch_fish; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_fsbm_batch_fish ON public.fish_seed_batches_map USING btree (seed_batch_id, fish_id);


--
-- Name: uq_fta_fish_base; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_fta_fish_base ON public.fish_transgene_alleles USING btree (fish_uuid, transgene_base_code);


--
-- Name: uq_fta_fish_uuid_base; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_fta_fish_uuid_base ON public.fish_transgene_alleles USING btree (fish_uuid, transgene_base_code);


--
-- Name: uq_ftm_one_open_per_fish; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_ftm_one_open_per_fish ON public.fish_tank_memberships USING btree (fish_uuid) WHERE (left_at IS NULL);


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
-- Name: uq_tank_active; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_tank_active ON public.fish_tank_memberships USING btree (tank_uuid) WHERE (ended_at IS NULL);


--
-- Name: uq_tank_pairs_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_tank_pairs_code ON public.tank_pairs USING btree (tank_pair_code) WHERE (tank_pair_code IS NOT NULL);


--
-- Name: uq_tanks_tank_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_tanks_tank_code ON public.tanks USING btree (tank_code) WHERE (tank_code IS NOT NULL);


--
-- Name: uq_tar_base_number; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_tar_base_number ON public.transgene_allele_registry USING btree (transgene_base_code, allele_number);


--
-- Name: uq_transgene_alleles_global_number; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_transgene_alleles_global_number ON public.transgene_alleles USING btree (allele_number);


--
-- Name: uq_transgene_alleles_nickname_per_base; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_transgene_alleles_nickname_per_base ON public.transgene_alleles USING btree (transgene_base_code, allele_nickname) WHERE (allele_nickname IS NOT NULL);


--
-- Name: ux_clutch_instance_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_clutch_instance_code ON public.clutch_instances USING btree (clutch_instance_code);


--
-- Name: ux_fish_pairs_mom_dad; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_fish_pairs_mom_dad ON public.fish_pairs USING btree (mom_fish_id, dad_fish_id);


--
-- Name: ux_fta_fish_base; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_fta_fish_base ON public.fish_transgene_alleles USING btree (fish_uuid, transgene_base_code);


--
-- Name: ux_planned_crosses_cross_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_planned_crosses_cross_code ON public.planned_crosses USING btree (cross_code);


--
-- Name: ux_tanks_tank_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_tanks_tank_code ON public.tanks USING btree (tank_code);


--
-- Name: ux_tanks_tank_uuid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_tanks_tank_uuid ON public.tanks USING btree (tank_uuid);


--
-- Name: ux_transgene_alleles_base_nick; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_transgene_alleles_base_nick ON public.transgene_alleles USING btree (transgene_base_code, allele_nickname) WHERE (allele_nickname IS NOT NULL);


--
-- Name: ux_transgene_alleles_base_num; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_transgene_alleles_base_num ON public.transgene_alleles USING btree (transgene_base_code, allele_number);


--
-- Name: fish bi_set_fish_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER bi_set_fish_code BEFORE INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.fish_bi_set_fish_code();


--
-- Name: tank_pairs tank_pairs_require_fp; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tank_pairs_require_fp BEFORE INSERT OR UPDATE ON public.tank_pairs FOR EACH ROW EXECUTE FUNCTION public.trg_tank_pairs_require_fp();


--
-- Name: containers trg_audit_del; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_del AFTER DELETE ON public.containers FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: fish trg_audit_del; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_del AFTER DELETE ON public.fish FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


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
-- Name: fish_transgene_alleles trg_audit_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_upd AFTER UPDATE ON public.fish_transgene_alleles FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: transgene_alleles trg_audit_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_upd AFTER UPDATE ON public.transgene_alleles FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: clutch_instances trg_ci_default_genotype; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_ci_default_genotype BEFORE INSERT ON public.clutch_instances FOR EACH ROW EXECUTE FUNCTION public.clutch_default_genotype_from_pair();


--
-- Name: clutch_instances trg_ci_rollup_after_ci; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_ci_rollup_after_ci AFTER INSERT OR UPDATE OF clutch_genotype_pretty ON public.clutch_instances FOR EACH ROW EXECUTE FUNCTION public.trg_ci_rollup_after_ci();


--
-- Name: clutch_instance_treatments trg_ci_rollup_after_treatment_d; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_ci_rollup_after_treatment_d AFTER DELETE ON public.clutch_instance_treatments FOR EACH ROW EXECUTE FUNCTION public.trg_ci_rollup_after_treatment();


--
-- Name: clutch_instance_treatments trg_ci_rollup_after_treatment_i; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_ci_rollup_after_treatment_i AFTER INSERT ON public.clutch_instance_treatments FOR EACH ROW EXECUTE FUNCTION public.trg_ci_rollup_after_treatment();


--
-- Name: clutch_instance_treatments trg_ci_rollup_after_treatment_u; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_ci_rollup_after_treatment_u AFTER UPDATE OF material_type, material_code, material_name ON public.clutch_instance_treatments FOR EACH ROW EXECUTE FUNCTION public.trg_ci_rollup_after_treatment();


--
-- Name: clutch_plans trg_clutch_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_clutch_code BEFORE INSERT ON public.clutch_plans FOR EACH ROW EXECUTE FUNCTION public.trg_clutch_code();


--
-- Name: clutches trg_clutch_instance_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_clutch_instance_code BEFORE INSERT ON public.clutches FOR EACH ROW EXECUTE FUNCTION public.trg_clutch_instance_code();


--
-- Name: clutch_instances trg_clutch_instances_set_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_clutch_instances_set_code BEFORE INSERT ON public.clutch_instances FOR EACH ROW EXECUTE FUNCTION public.gen_clutch_instance_code();


--
-- Name: clutches trg_clutches_set_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_clutches_set_code BEFORE INSERT ON public.clutches FOR EACH ROW EXECUTE FUNCTION public.trg_clutches_set_code();


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
-- Name: cross_instances trg_cross_instances_set_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cross_instances_set_code BEFORE INSERT ON public.cross_instances FOR EACH ROW EXECUTE FUNCTION public.trg_cross_instances_set_code();


--
-- Name: crosses trg_cross_name_fill; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cross_name_fill BEFORE INSERT ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_cross_name_fill();


--
-- Name: cross_instances trg_cross_run_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cross_run_code BEFORE INSERT ON public.cross_instances FOR EACH ROW EXECUTE FUNCTION public.trg_cross_run_code();


--
-- Name: fish trg_fish_before_insert_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_fish_before_insert_code BEFORE INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.fish_before_insert_code();


--
-- Name: fish_pairs trg_fish_pairs_code_autogen; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_fish_pairs_code_autogen BEFORE INSERT ON public.fish_pairs FOR EACH ROW EXECUTE FUNCTION public.fish_pairs_code_autogen();


--
-- Name: fish_tank_memberships trg_fish_tank_memberships_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_fish_tank_memberships_updated_at BEFORE UPDATE ON public.fish_tank_memberships FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: plasmids trg_plasmids_auto_ensure_rna; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_plasmids_auto_ensure_rna AFTER INSERT OR UPDATE OF supports_invitro_rna, code ON public.plasmids FOR EACH ROW EXECUTE FUNCTION public.trg_plasmid_auto_ensure_rna();


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
-- Name: tank_pairs trg_tank_pairs_set_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_tank_pairs_set_code BEFORE INSERT ON public.tank_pairs FOR EACH ROW EXECUTE FUNCTION public.gen_tank_pair_code();


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
-- Name: fish_tank_memberships fish_tank_memberships_fish_uuid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_tank_memberships
    ADD CONSTRAINT fish_tank_memberships_fish_uuid_fkey FOREIGN KEY (fish_uuid) REFERENCES public.fish(fish_uuid) ON DELETE CASCADE;


--
-- Name: fish_tank_memberships fish_tank_memberships_tank_uuid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_tank_memberships
    ADD CONSTRAINT fish_tank_memberships_tank_uuid_fkey FOREIGN KEY (tank_uuid) REFERENCES public.tanks(tank_uuid) ON DELETE CASCADE;


--
-- Name: fish_transgene_alleles fish_transgene_alleles_transgene_base_code_allele_number_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_transgene_alleles
    ADD CONSTRAINT fish_transgene_alleles_transgene_base_code_allele_number_fkey FOREIGN KEY (transgene_base_code, allele_number) REFERENCES public.transgene_alleles(transgene_base_code, allele_number) ON DELETE CASCADE;


--
-- Name: cross_plan_genotype_alleles fk_cpga_transgene_allele; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_plan_genotype_alleles
    ADD CONSTRAINT fk_cpga_transgene_allele FOREIGN KEY (transgene_base_code, allele_number) REFERENCES public.transgene_alleles(transgene_base_code, allele_number) ON DELETE RESTRICT;


--
-- Name: tank_pairs fk_tank_pairs_fish_pair_code; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_pairs
    ADD CONSTRAINT fk_tank_pairs_fish_pair_code FOREIGN KEY (fish_pair_code) REFERENCES public.fish_pairs(fish_pair_code) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;


--
-- Name: tanks fk_tanks_fish_code; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tanks
    ADD CONSTRAINT fk_tanks_fish_code FOREIGN KEY (fish_code) REFERENCES public.fish(fish_code);


--
-- Name: transgene_alleles fk_transgene_alleles_base; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgene_alleles
    ADD CONSTRAINT fk_transgene_alleles_base FOREIGN KEY (transgene_base_code) REFERENCES public.transgenes(transgene_base_code) ON DELETE CASCADE;


--
-- Name: mounts mounts_clutch_instance_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mounts
    ADD CONSTRAINT mounts_clutch_instance_id_fkey FOREIGN KEY (clutch_instance_id) REFERENCES public.clutch_instances(id) ON DELETE CASCADE;


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
-- Name: tanks; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.tanks ENABLE ROW LEVEL SECURITY;

--
-- Name: tanks tanks_insert_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tanks_insert_all ON public.tanks FOR INSERT WITH CHECK (true);


--
-- Name: tanks tanks_select_all; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY tanks_select_all ON public.tanks FOR SELECT USING (true);


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

\unrestrict GHUdXR8rPjLsCUAGN1KOb22W97gNjlXTEi8Anla91LPFbCxBoNoX2i0hAEkaPYZ

