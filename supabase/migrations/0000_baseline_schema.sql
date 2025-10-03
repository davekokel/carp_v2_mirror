--
-- PostgreSQL database dump
--

\restrict 7fmKaip6q2zYQjOQMYEhNMt3Z7IYUcvqEEEMwgx6r01bJnmJ3Bxo4alyOQLBKcl

-- Dumped from database version 16.10 (Homebrew)
-- Dumped by pg_dump version 18.0

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;

ALTER TABLE IF EXISTS ONLY public.treatments DROP CONSTRAINT IF EXISTS treatments_protocol_code_fkey;
ALTER TABLE IF EXISTS ONLY public.injected_rna_treatments DROP CONSTRAINT IF EXISTS irt_fish_fk;
ALTER TABLE IF EXISTS ONLY public.injected_rna_treatments DROP CONSTRAINT IF EXISTS injected_rna_treatments_rna_id_fkey;
ALTER TABLE IF EXISTS ONLY public.injected_rna_treatments DROP CONSTRAINT IF EXISTS injected_rna_treatments_fish_id_fkey;
ALTER TABLE IF EXISTS ONLY public.fish_rnas DROP CONSTRAINT IF EXISTS fish_rnas_rna_id_fkey;
ALTER TABLE IF EXISTS ONLY public.fish_rnas DROP CONSTRAINT IF EXISTS fish_rnas_fish_id_fkey;
DROP INDEX IF EXISTS public.ux_transgene_alleles_base_name_norm;
DROP INDEX IF EXISTS public.ux_transgene_alleles_base_code_norm;
DROP INDEX IF EXISTS public.uq_rnas_name_ci;
DROP INDEX IF EXISTS public.uq_rna_txn_dedupe;
DROP INDEX IF EXISTS public.uq_irt_natural;
DROP INDEX IF EXISTS public.uniq_registry_base_legacy;
DROP INDEX IF EXISTS public.ix_registry_base_code;
DROP INDEX IF EXISTS public.ix_injected_rna_treatments_rna;
DROP INDEX IF EXISTS public.idx_transgene_alleles_code_num;
DROP INDEX IF EXISTS public.idx_fish_rnas_rna_id;
ALTER TABLE IF EXISTS ONLY public.treatments DROP CONSTRAINT IF EXISTS treatments_pkey;
ALTER TABLE IF EXISTS ONLY public.treatment_protocols DROP CONSTRAINT IF EXISTS treatment_protocols_pkey;
ALTER TABLE IF EXISTS ONLY public.transgene_alleles DROP CONSTRAINT IF EXISTS transgene_alleles_pkey;
ALTER TABLE IF EXISTS ONLY public.transgene_allele_registry DROP CONSTRAINT IF EXISTS transgene_allele_registry_pkey;
ALTER TABLE IF EXISTS ONLY public.transgene_allele_legacy_map DROP CONSTRAINT IF EXISTS transgene_allele_legacy_map_pkey;
ALTER TABLE IF EXISTS ONLY public.seed_last_upload_links DROP CONSTRAINT IF EXISTS seed_last_upload_links_pkey;
ALTER TABLE IF EXISTS ONLY public.rnas DROP CONSTRAINT IF EXISTS rnas_rna_code_key;
ALTER TABLE IF EXISTS ONLY public.rnas DROP CONSTRAINT IF EXISTS rnas_pkey;
ALTER TABLE IF EXISTS ONLY public.injected_rna_treatments DROP CONSTRAINT IF EXISTS injected_rna_treatments_pkey;
ALTER TABLE IF EXISTS ONLY public.fish_rnas DROP CONSTRAINT IF EXISTS fish_rnas_pkey;
ALTER TABLE IF EXISTS ONLY public.fish DROP CONSTRAINT IF EXISTS fish_pkey;
DROP TABLE IF EXISTS public.treatments;
DROP TABLE IF EXISTS public.treatment_protocols;
DROP TABLE IF EXISTS public.transgene_alleles;
DROP TABLE IF EXISTS public.transgene_allele_registry;
DROP TABLE IF EXISTS public.transgene_allele_legacy_map;
DROP TABLE IF EXISTS public.seed_last_upload_links;
DROP TABLE IF EXISTS public.rnas;
DROP TABLE IF EXISTS public.injected_rna_treatments;
DROP TABLE IF EXISTS public.fish_rnas;
DROP TABLE IF EXISTS public.fish;
DROP FUNCTION IF EXISTS public.upsert_transgene_allele_name(p_base text, p_name text, OUT out_allele_number integer);
DROP FUNCTION IF EXISTS public.upsert_transgene_allele_label(p_base text, p_label text, OUT out_allele_number integer);
DROP FUNCTION IF EXISTS public.to_base36(n integer);
DROP FUNCTION IF EXISTS public.tg_upsert_fish_seed_maps();
DROP FUNCTION IF EXISTS public.reseed_bases_from_sidecar_names();
DROP FUNCTION IF EXISTS public.next_allele_number(code text);
DROP FUNCTION IF EXISTS public.gen_fish_code(p_ts timestamp with time zone);
DROP FUNCTION IF EXISTS public.code_prefix(p_base text);
DROP FUNCTION IF EXISTS public.allocate_allele_number(p_base_code text, p_legacy_label text);
DROP TYPE IF EXISTS public.treatment_unit;
DROP TYPE IF EXISTS public.treatment_route;
DROP EXTENSION IF EXISTS pgcrypto;
--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: treatment_route; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.treatment_route AS ENUM (
    'bath',
    'injection',
    'feed',
    'other'
);


--
-- Name: treatment_unit; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.treatment_unit AS ENUM (
    'µM',
    'mM',
    'nM',
    'mg/L',
    'µg/mL',
    '%',
    'other'
);


--
-- Name: allocate_allele_number(text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.allocate_allele_number(p_base_code text, p_legacy_label text DEFAULT NULL::text) RETURNS integer
    LANGUAGE plpgsql
    AS $$
declare
  v_num integer;
begin
  if p_base_code is null or btrim(p_base_code) = '' then
    raise exception 'allocate_allele_number(): base_code is required';
  end if;

  -- If a legacy label maps already, return its canonical number.
  if p_legacy_label is not null and btrim(p_legacy_label) <> '' then
    select allele_number into v_num
    from public.transgene_allele_registry
    where base_code = p_base_code
      and legacy_label = p_legacy_label;
    if found then
      return v_num;
    end if;
  end if;

  -- Allocate next free number for this base_code (concurrency-safe).
  loop
    select coalesce(max(allele_number), 0) + 1
      into v_num
    from public.transgene_allele_registry
    where base_code = p_base_code;

    begin
      insert into public.transgene_allele_registry(base_code, allele_number, legacy_label)
      values (p_base_code, v_num, nullif(p_legacy_label,''));
      return v_num;
    exception when unique_violation then
      -- racing with another allocator; try again
      continue;
    end;
  end loop;
end
$$;


--
-- Name: code_prefix(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.code_prefix(p_base text) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT
    AS $_$
  SELECT lower(regexp_replace(btrim($1), '[^A-Za-z]+$',''))  -- letters at the front
$_$;


--
-- Name: gen_fish_code(timestamp with time zone); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_fish_code(p_ts timestamp with time zone DEFAULT now()) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
    y int := extract(year from p_ts);
    k int;
BEGIN
    INSERT INTO public.fish_year_counters(year, n)
    VALUES (y, 0)
    ON CONFLICT (year) DO NOTHING;

    UPDATE public.fish_year_counters
    SET n = n + 1
    WHERE year = y
    RETURNING n INTO k;

    RETURN format('FSH-%s-%s', y, lpad(to_base36(k), 3, '0'));
END;
$$;


--
-- Name: next_allele_number(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.next_allele_number(code text) RETURNS text
    LANGUAGE sql
    AS $$
  SELECT (COALESCE(MAX(allele_number::int), 0) + 1)::text
  FROM public.transgene_alleles
  WHERE transgene_base_code = next_allele_number.code
$$;


--
-- Name: reseed_bases_from_sidecar_names(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.reseed_bases_from_sidecar_names() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  -- bases we need to reseed, scoped to current sidecar contents
  CREATE TEMP TABLE _bases ON COMMIT DROP AS
  SELECT DISTINCT slul.transgene_base_code AS base
  FROM public.seed_last_upload_links slul
  WHERE slul.transgene_base_code IS NOT NULL AND btrim(slul.transgene_base_code) <> '';

  -- wipe normalized links/allele defs for those bases (FK-safe)
  DELETE FROM public.fish_transgene_alleles fta
  USING _bases b
  WHERE fta.transgene_base_code = b.base;

  DELETE FROM public.transgene_alleles ta
  USING _bases b
  WHERE ta.transgene_base_code = b.base;

  -- collect distinct allele_name labels per base (non-empty)
  CREATE TEMP TABLE _ordered ON COMMIT DROP AS
  SELECT
    slul.transgene_base_code                                     AS base,
    NULLIF(btrim(slul.allele_name), '')                          AS allele_name,
    ROW_NUMBER() OVER (PARTITION BY slul.transgene_base_code
                       ORDER BY lower(NULLIF(btrim(slul.allele_name), ''))) AS allele_number
  FROM (
    SELECT DISTINCT transgene_base_code, allele_name
    FROM public.seed_last_upload_links
    WHERE transgene_base_code IS NOT NULL AND btrim(transgene_base_code) <> ''
  ) slul
  WHERE slul.allele_name IS NOT NULL;

  -- seed canonical 1..N with auto code = prefix-number
  INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, allele_code, allele_name)
  SELECT
    o.base,
    o.allele_number,
    public.code_prefix(o.base) || '-' || o.allele_number::text,
    o.allele_name
  FROM _ordered o
  ORDER BY o.base, o.allele_number;
END$$;


--
-- Name: tg_upsert_fish_seed_maps(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.tg_upsert_fish_seed_maps() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
  if new.seed_batch_id is not null and new.fish_id is not null then
    -- 1) Ensure seed_batches has a row (label defaults to id; you can prettify later)
    insert into public.seed_batches(seed_batch_id, batch_label)
    values (new.seed_batch_id, new.seed_batch_id)
    on conflict (seed_batch_id) do nothing;

    -- 2) Tie this fish to the batch id (latest wins)
    insert into public.fish_seed_batches(fish_id, seed_batch_id, updated_at)
    values (new.fish_id, new.seed_batch_id, now())
    on conflict (fish_id) do update
      set seed_batch_id = excluded.seed_batch_id,
          updated_at    = excluded.updated_at;
  end if;
  return new;
end
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
-- Name: fish; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish (
    id uuid NOT NULL
);


--
-- Name: fish_rnas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish_rnas (
    fish_id uuid NOT NULL,
    rna_id uuid NOT NULL
);


--
-- Name: injected_rna_treatments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.injected_rna_treatments (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    fish_id uuid NOT NULL,
    rna_id uuid NOT NULL,
    amount numeric,
    units text,
    at_time timestamp with time zone,
    note text
);


--
-- Name: rnas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rnas (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    rna_code text,
    name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text
);


--
-- Name: seed_last_upload_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.seed_last_upload_links (
    fish_code text NOT NULL,
    transgene_base_code text,
    allele_number integer,
    zygosity text,
    uploaded_at timestamp with time zone DEFAULT now(),
    allele_code text,
    allele_name text
);


--
-- Name: transgene_allele_legacy_map; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transgene_allele_legacy_map (
    transgene_base_code text NOT NULL,
    legacy_label text NOT NULL,
    allele_number text NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: transgene_allele_registry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transgene_allele_registry (
    base_code text NOT NULL,
    allele_number integer NOT NULL,
    legacy_label text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: transgene_alleles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transgene_alleles (
    transgene_base_code text NOT NULL,
    allele_number integer NOT NULL,
    allele_name text,
    description text,
    allele_code text
);


--
-- Name: treatment_protocols; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.treatment_protocols (
    protocol_code text NOT NULL,
    display_name text NOT NULL,
    description text
);


--
-- Name: treatments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.treatments (
    treatment_type text NOT NULL,
    display_name text NOT NULL,
    route public.treatment_route DEFAULT 'bath'::public.treatment_route NOT NULL,
    protocol_code text,
    notes text
);


--
-- Name: fish fish_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT fish_pkey PRIMARY KEY (id);


--
-- Name: fish_rnas fish_rnas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_rnas
    ADD CONSTRAINT fish_rnas_pkey PRIMARY KEY (fish_id, rna_id);


--
-- Name: injected_rna_treatments injected_rna_treatments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.injected_rna_treatments
    ADD CONSTRAINT injected_rna_treatments_pkey PRIMARY KEY (id_uuid);


--
-- Name: rnas rnas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rnas
    ADD CONSTRAINT rnas_pkey PRIMARY KEY (id_uuid);


--
-- Name: rnas rnas_rna_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rnas
    ADD CONSTRAINT rnas_rna_code_key UNIQUE (rna_code);


--
-- Name: seed_last_upload_links seed_last_upload_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seed_last_upload_links
    ADD CONSTRAINT seed_last_upload_links_pkey PRIMARY KEY (fish_code);


--
-- Name: transgene_allele_legacy_map transgene_allele_legacy_map_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgene_allele_legacy_map
    ADD CONSTRAINT transgene_allele_legacy_map_pkey PRIMARY KEY (transgene_base_code, legacy_label);


--
-- Name: transgene_allele_registry transgene_allele_registry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgene_allele_registry
    ADD CONSTRAINT transgene_allele_registry_pkey PRIMARY KEY (base_code, allele_number);


--
-- Name: transgene_alleles transgene_alleles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgene_alleles
    ADD CONSTRAINT transgene_alleles_pkey PRIMARY KEY (transgene_base_code, allele_number);


--
-- Name: treatment_protocols treatment_protocols_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.treatment_protocols
    ADD CONSTRAINT treatment_protocols_pkey PRIMARY KEY (protocol_code);


--
-- Name: treatments treatments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.treatments
    ADD CONSTRAINT treatments_pkey PRIMARY KEY (treatment_type);


--
-- Name: idx_fish_rnas_rna_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_fish_rnas_rna_id ON public.fish_rnas USING btree (rna_id);


--
-- Name: idx_transgene_alleles_code_num; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transgene_alleles_code_num ON public.transgene_alleles USING btree (transgene_base_code, allele_number);


--
-- Name: ix_injected_rna_treatments_rna; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_injected_rna_treatments_rna ON public.injected_rna_treatments USING btree (rna_id);


--
-- Name: ix_registry_base_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_registry_base_code ON public.transgene_allele_registry USING btree (base_code);


--
-- Name: uniq_registry_base_legacy; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uniq_registry_base_legacy ON public.transgene_allele_registry USING btree (base_code, legacy_label);


--
-- Name: uq_irt_natural; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_irt_natural ON public.injected_rna_treatments USING btree (fish_id, rna_id, at_time, amount, units, note);


--
-- Name: uq_rna_txn_dedupe; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_rna_txn_dedupe ON public.injected_rna_treatments USING btree (fish_id, rna_id, COALESCE(at_time, '1969-12-31 16:00:00-08'::timestamp with time zone), COALESCE(amount, (0)::numeric), COALESCE(units, ''::text), COALESCE(note, ''::text));


--
-- Name: uq_rnas_name_ci; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_rnas_name_ci ON public.rnas USING btree (lower(name)) WHERE (name IS NOT NULL);


--
-- Name: ux_transgene_alleles_base_code_norm; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_transgene_alleles_base_code_norm ON public.transgene_alleles USING btree (transgene_base_code, lower(btrim(allele_code))) WHERE ((allele_code IS NOT NULL) AND (btrim(allele_code) <> ''::text));


--
-- Name: ux_transgene_alleles_base_name_norm; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_transgene_alleles_base_name_norm ON public.transgene_alleles USING btree (transgene_base_code, lower(btrim(allele_name))) WHERE ((allele_name IS NOT NULL) AND (btrim(allele_name) <> ''::text));


--
-- Name: fish_rnas fish_rnas_fish_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_rnas
    ADD CONSTRAINT fish_rnas_fish_id_fkey FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;


--
-- Name: fish_rnas fish_rnas_rna_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_rnas
    ADD CONSTRAINT fish_rnas_rna_id_fkey FOREIGN KEY (rna_id) REFERENCES public.rnas(id_uuid) ON DELETE RESTRICT;


--
-- Name: injected_rna_treatments injected_rna_treatments_fish_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.injected_rna_treatments
    ADD CONSTRAINT injected_rna_treatments_fish_id_fkey FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;


--
-- Name: injected_rna_treatments injected_rna_treatments_rna_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.injected_rna_treatments
    ADD CONSTRAINT injected_rna_treatments_rna_id_fkey FOREIGN KEY (rna_id) REFERENCES public.rnas(id_uuid) ON DELETE RESTRICT;


--
-- Name: injected_rna_treatments irt_fish_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.injected_rna_treatments
    ADD CONSTRAINT irt_fish_fk FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;


--
-- Name: treatments treatments_protocol_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.treatments
    ADD CONSTRAINT treatments_protocol_code_fkey FOREIGN KEY (protocol_code) REFERENCES public.treatment_protocols(protocol_code);


--
-- PostgreSQL database dump complete
--

\unrestrict 7fmKaip6q2zYQjOQMYEhNMt3Z7IYUcvqEEEMwgx6r01bJnmJ3Bxo4alyOQLBKcl

