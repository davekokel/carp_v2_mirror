--
-- PostgreSQL database dump
--

\restrict ZD7VfvKodnsDgJx6chwm6tJGq94DoabYLMFRsrvoCbSrta83imBRmAGCnetDGUL

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
-- Name: ensure_active_tank_for_fish(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ensure_active_tank_for_fish(p_fish_code text) RETURNS void
    LANGUAGE plpgsql
    SET search_path TO 'public'
    AS $$
DECLARE
  v_fish_uuid uuid;
  v_tank_uuid uuid;
  v_num int;
  v_tank_code text;
BEGIN
  -- Find fish
  SELECT fish_uuid INTO v_fish_uuid
  FROM public.fish
  WHERE fish_code = p_fish_code
  LIMIT 1;

  IF v_fish_uuid IS NULL THEN
    RAISE EXCEPTION 'ensure_active_tank_for_fish(): fish_code % not found', p_fish_code;
  END IF;

  -- Try to find an existing active tank for this fish code
  SELECT t.tank_uuid
    INTO v_tank_uuid
  FROM public.tanks t
  WHERE t.status = 'active'
    AND t.tank_code LIKE ('TANK(' || p_fish_code || ')#%')
  ORDER BY t.created_at ASC
  LIMIT 1;

  -- If none, create one deterministically as next #N
  IF v_tank_uuid IS NULL THEN
    SELECT COALESCE(MAX(NULLIF(split_part(tank_code, '#', 2), '')::int), 0) + 1
      INTO v_num
    FROM public.tanks
    WHERE tank_code LIKE ('TANK(' || p_fish_code || ')#%');

    v_tank_code := 'TANK(' || p_fish_code || ')#' || v_num::text;

    INSERT INTO public.tanks (tank_uuid, tank_code, status, created_at)
    VALUES (gen_random_uuid(), v_tank_code, 'active', now())
    RETURNING tank_uuid INTO v_tank_uuid;
  END IF;

  -- Close any other open memberships for this fish
  UPDATE public.fish_tank_memberships m
  SET left_at = now()
  WHERE m.fish_uuid = v_fish_uuid
    AND m.left_at IS NULL
    AND m.tank_uuid <> v_tank_uuid;

  -- Ensure an open membership exists for (fish, v_tank_uuid)
  IF NOT EXISTS (
    SELECT 1 FROM public.fish_tank_memberships m
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
-- Name: fish_before_insert_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fish_before_insert_code() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
declare
  y int := extract(year from coalesce(new.date_birth, now()))::int;
  seq int;
begin
  insert into public.fish_year_counters(year, n) values (y, 0)
  on conflict (year) do nothing;

  update public.fish_year_counters
     set n = n + 1
   where year = y
  returning n into seq;

  new.fish_code := make_fish_code_yy_seq36(clock_timestamp(), y, seq);
  return new;
end
$$;


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
-- Name: link_fish_to_transgene_allele(uuid, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.link_fish_to_transgene_allele(p_fish_uuid uuid, p_base text, p_nickname text) RETURNS TABLE(fish_uuid uuid, transgene_base_code text, allele_number integer)
    LANGUAGE plpgsql
    AS $$
declare
  r record;
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
-- Name: clutch_instance_treatments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clutch_instance_treatments (
    dummy integer
);


--
-- Name: cross_instances; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cross_instances (
    dummy integer
);


--
-- Name: fish; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish (
    dummy integer,
    fish_name text,
    fish_nickname text,
    genetic_background text,
    line_building_stage text,
    date_birth date,
    seed_batch_id text
);


--
-- Name: fish_code_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fish_code_seq
    START WITH 0
    INCREMENT BY 1
    MINVALUE 0
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
-- Name: fish_tank_memberships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish_tank_memberships (
    dummy integer,
    joined_at timestamp with time zone,
    left_at timestamp with time zone
);


--
-- Name: fish_year_counters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish_year_counters (
    year integer NOT NULL,
    next_num integer DEFAULT 1 NOT NULL,
    n integer DEFAULT 0 NOT NULL
);


--
-- Name: tanks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tanks (
    dummy integer
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
-- Name: transgene_alleles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transgene_alleles (
    transgene_base_code text NOT NULL,
    allele_number integer NOT NULL,
    allele_name text NOT NULL,
    allele_nickname text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: v_clutch_instances_display; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_clutch_instances_display AS
 SELECT 1 AS dummy
  WHERE false;


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
         SELECT 'tanks_pk_is_tank_uuid'::text AS text,
            ( SELECT pk_tanks.ok
                   FROM pk_tanks) AS ok,
            'PK(tanks.tank_uuid)'::text AS text
        UNION ALL
         SELECT 'ftm_required_columns'::text AS text,
            ( SELECT ftm_cols.ok
                   FROM ftm_cols) AS ok,
            'fish_uuid,tank_uuid,started_at,ended_at'::text AS text
        UNION ALL
         SELECT 'ftm_one_active_fish_per_tank'::text AS text,
            ( SELECT idx_active.ok
                   FROM idx_active) AS ok,
            'uq_tank_active with predicate ended_at IS NULL'::text AS text
        UNION ALL
         SELECT 'ftm_updated_at_trigger'::text AS text,
            ( SELECT trg_updated.ok
                   FROM trg_updated) AS ok,
            'trigger trg_fish_tank_memberships_updated_at'::text AS text) s;


--
-- Name: v_tanks; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_tanks AS
 SELECT 1 AS dummy
  WHERE false;


--
-- Name: _schema_version _schema_version_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public._schema_version
    ADD CONSTRAINT _schema_version_pkey PRIMARY KEY (key);


--
-- Name: fish_year_counters fish_year_counters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_year_counters
    ADD CONSTRAINT fish_year_counters_pkey PRIMARY KEY (year);


--
-- Name: transgene_alleles transgene_alleles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgene_alleles
    ADD CONSTRAINT transgene_alleles_pkey PRIMARY KEY (transgene_base_code, allele_number);


--
-- Name: uq_transgene_alleles_global_number; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_transgene_alleles_global_number ON public.transgene_alleles USING btree (allele_number);


--
-- Name: uq_transgene_alleles_nickname_per_base; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_transgene_alleles_nickname_per_base ON public.transgene_alleles USING btree (transgene_base_code, allele_nickname) WHERE (allele_nickname IS NOT NULL);


--
-- Name: fish bi_set_fish_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER bi_set_fish_code BEFORE INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.fish_bi_set_fish_code();


--
-- PostgreSQL database dump complete
--

\unrestrict ZD7VfvKodnsDgJx6chwm6tJGq94DoabYLMFRsrvoCbSrta83imBRmAGCnetDGUL

