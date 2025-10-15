


SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE SCHEMA IF NOT EXISTS "public";


ALTER SCHEMA "public" OWNER TO "pg_database_owner";


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE TYPE "public"."container_status" AS ENUM (
    'planned',
    'active',
    'to_kill',
    'retired'
);


ALTER TYPE "public"."container_status" OWNER TO "postgres";


CREATE TYPE "public"."cross_plan_status" AS ENUM (
    'planned',
    'canceled',
    'executed'
);


ALTER TYPE "public"."cross_plan_status" OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."apply_plasmid_treatment"("p_fish_id" "uuid", "p_plasmid_id" "uuid", "p_amount" numeric, "p_units" "text", "p_at_time" timestamp with time zone, "p_note" "text") RETURNS "void"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."apply_plasmid_treatment"("p_fish_id" "uuid", "p_plasmid_id" "uuid", "p_amount" numeric, "p_units" "text", "p_at_time" timestamp with time zone, "p_note" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."apply_rna_treatment"("p_fish_id" "uuid", "p_rna_id" "uuid", "p_amount" numeric, "p_units" "text", "p_at_time" timestamp with time zone, "p_note" "text") RETURNS "void"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."apply_rna_treatment"("p_fish_id" "uuid", "p_rna_id" "uuid", "p_amount" numeric, "p_units" "text", "p_at_time" timestamp with time zone, "p_note" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."assign_fish_to_tank"("p_fish_id" "uuid", "p_container_id" "uuid", "p_by" "text", "p_note" "text" DEFAULT NULL::"text") RETURNS "uuid"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."assign_fish_to_tank"("p_fish_id" "uuid", "p_container_id" "uuid", "p_by" "text", "p_note" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."create_label_job"("p_entity_type" "text", "p_entity_id" "uuid", "p_template" "text", "p_media" "text", "p_requested_by" "text", "p_cards" "jsonb", "p_dedupe_hash" "text" DEFAULT NULL::"text", "p_replace" boolean DEFAULT false) RETURNS "uuid"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."create_label_job"("p_entity_type" "text", "p_entity_id" "uuid", "p_template" "text", "p_media" "text", "p_requested_by" "text", "p_cards" "jsonb", "p_dedupe_hash" "text", "p_replace" boolean) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."create_offspring_batch"("p_mother_id" "uuid", "p_father_id" "uuid", "p_count" integer, "p_created_by" "text" DEFAULT NULL::"text", "p_birth_date" "date" DEFAULT NULL::"date", "p_name_prefix" "text" DEFAULT NULL::"text") RETURNS TABLE("child_id" "uuid", "fish_code" "text")
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."create_offspring_batch"("p_mother_id" "uuid", "p_father_id" "uuid", "p_count" integer, "p_created_by" "text", "p_birth_date" "date", "p_name_prefix" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."ensure_inventory_tank"("p_label" "text", "p_by" "text", "p_status" "public"."container_status" DEFAULT 'active'::"public"."container_status") RETURNS "uuid"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."ensure_inventory_tank"("p_label" "text", "p_by" "text", "p_status" "public"."container_status") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."ensure_inventory_tank_text"("p_label" "text", "p_by" "text", "p_status" "text") RETURNS "uuid"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  RETURN public.ensure_inventory_tank(p_label, p_by, p_status::container_status);
END$$;


ALTER FUNCTION "public"."ensure_inventory_tank_text"("p_label" "text", "p_by" "text", "p_status" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."ensure_inventory_tank_v"("p_label" "text", "p_by" "text", "p_status" "public"."container_status" DEFAULT 'active'::"public"."container_status", "p_volume_l" integer DEFAULT NULL::integer) RETURNS "uuid"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."ensure_inventory_tank_v"("p_label" "text", "p_by" "text", "p_status" "public"."container_status", "p_volume_l" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."ensure_inventory_tank_v_text"("p_label" "text", "p_by" "text", "p_status" "text", "p_volume_l" integer) RETURNS "uuid"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  RETURN public.ensure_inventory_tank_v(p_label, p_by, p_status::container_status, p_volume_l);
END$$;


ALTER FUNCTION "public"."ensure_inventory_tank_v_text"("p_label" "text", "p_by" "text", "p_status" "text", "p_volume_l" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."ensure_rna_for_plasmid"("p_plasmid_code" "text", "p_suffix" "text" DEFAULT '-RNA'::"text", "p_name" "text" DEFAULT NULL::"text", "p_created_by" "text" DEFAULT NULL::"text", "p_notes" "text" DEFAULT NULL::"text") RETURNS TABLE("rna_id" "uuid", "rna_code" "text")
    LANGUAGE "plpgsql"
    AS $$
DECLARE
  v_plasmid_id uuid;
  v_code text;
BEGIN
  SELECT id_uuid INTO v_plasmid_id
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
  RETURNING id_uuid, code INTO rna_id, rna_code;

  RETURN NEXT;
END;
$$;


ALTER FUNCTION "public"."ensure_rna_for_plasmid"("p_plasmid_code" "text", "p_suffix" "text", "p_name" "text", "p_created_by" "text", "p_notes" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."ensure_transgene_allele"("p_base" "text", "p_nickname" "text") RETURNS TABLE("ret_allele_number" integer, "ret_allele_nickname" "text")
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."ensure_transgene_allele"("p_base" "text", "p_nickname" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."fish_before_insert_code"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $_$
BEGIN
  IF NEW.fish_code IS NULL
     OR btrim(NEW.fish_code) = ''
     OR NEW.fish_code !~ '^FSH-[0-9]{2}[0-9A-Z]{4,}$' THEN
    NEW.fish_code := public.make_fish_code_yy_seq36(now());
  END IF;
  RETURN NEW;
END $_$;


ALTER FUNCTION "public"."fish_before_insert_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."fish_bi_set_fish_code"() RETURNS "trigger"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."fish_bi_set_fish_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."gen_clutch_code"() RETURNS "text"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."gen_clutch_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."gen_clutch_instance_code"() RETURNS "text"
    LANGUAGE "plpgsql"
    AS $$
DECLARE y text := to_char(current_date,'YY'); n bigint;
BEGIN SELECT nextval('public.clutch_instance_code_seq') INTO n; RETURN format('CI-%s%05s', y, n); END;
$$;


ALTER FUNCTION "public"."gen_clutch_instance_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."gen_cross_code"() RETURNS "text"
    LANGUAGE "plpgsql"
    AS $$
DECLARE y text := to_char(current_date,'YY'); n bigint;
BEGIN SELECT nextval('public.cross_code_seq') INTO n; RETURN format('CR-%s%05s', y, n); END;
$$;


ALTER FUNCTION "public"."gen_cross_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."gen_cross_name"("mom" "text", "dad" "text") RETURNS "text"
    LANGUAGE "sql" IMMUTABLE
    AS $$
  SELECT trim(coalesce(NULLIF(mom,''),'?')) || ' × ' || trim(coalesce(NULLIF(dad,''),'?'));
$$;


ALTER FUNCTION "public"."gen_cross_name"("mom" "text", "dad" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."gen_cross_run_code"() RETURNS "text"
    LANGUAGE "plpgsql"
    AS $$
DECLARE y text := to_char(current_date,'YY'); n bigint;
BEGIN SELECT nextval('public.cross_run_code_seq') INTO n; RETURN format('XR-%s%05s', y, n); END;
$$;


ALTER FUNCTION "public"."gen_cross_run_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."gen_tank_code"() RETURNS "text"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."gen_tank_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."inherit_transgene_alleles"("child_id" "uuid", "mother_id" "uuid", "father_id" "uuid") RETURNS "void"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."inherit_transgene_alleles"("child_id" "uuid", "mother_id" "uuid", "father_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."is_container_live"("s" "text") RETURNS boolean
    LANGUAGE "sql" IMMUTABLE
    AS $$
  select s in ('active','new_tank')
$$;


ALTER FUNCTION "public"."is_container_live"("s" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."make_fish_code_compact"() RETURNS "text"
    LANGUAGE "sql"
    AS $$
  SELECT 'FSH-' || to_char(current_date,'YY') || util_mig._to_base36(nextval('public.fish_code_seq'), 4)
$$;


ALTER FUNCTION "public"."make_fish_code_compact"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."make_fish_code_yy_seq36"("ts" timestamp with time zone DEFAULT "now"()) RETURNS "text"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."make_fish_code_yy_seq36"("ts" timestamp with time zone) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."make_tank_code_compact"() RETURNS "text"
    LANGUAGE "sql"
    AS $$
  select 'TANK-' || to_char(current_date,'YY') || util_mig._to_base36(nextval('public.tank_code_seq'), 4)
$$;


ALTER FUNCTION "public"."make_tank_code_compact"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."mark_container_active"("p_id" "uuid", "p_by" "text") RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  UPDATE public.containers
  SET status='active',
      status_changed_at=now(),
      activated_at=COALESCE(activated_at, now())
  WHERE id_uuid=p_id;
END$$;


ALTER FUNCTION "public"."mark_container_active"("p_id" "uuid", "p_by" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."mark_container_inactive"("p_id" "uuid", "p_by" "text") RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$ BEGIN
  PERFORM public.set_container_status(p_id, 'to_kill', p_by, 'compat: inactive→to_kill');
END $$;


ALTER FUNCTION "public"."mark_container_inactive"("p_id" "uuid", "p_by" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."mark_container_retired"("p_id" "uuid", "p_by" "text", "p_reason" "text" DEFAULT NULL::"text") RETURNS "void"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."mark_container_retired"("p_id" "uuid", "p_by" "text", "p_reason" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."mark_container_to_kill"("p_id" "uuid", "p_by" "text", "p_reason" "text" DEFAULT NULL::"text") RETURNS "void"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."mark_container_to_kill"("p_id" "uuid", "p_by" "text", "p_reason" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."next_fish_code"() RETURNS "text"
    LANGUAGE "sql"
    AS $$
  SELECT 'FSH-' || to_char(nextval('public.fish_code_seq'), 'FM000000');
$$;


ALTER FUNCTION "public"."next_fish_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."normalize_cross_code"("p_code" "text") RETURNS "text"
    LANGUAGE "sql" STABLE
    AS $$
  SELECT CASE
    WHEN p_code IS NULL OR length(btrim(p_code))=0 THEN NULL
    WHEN upper(p_code) ~ '^CR-'     THEN 'CROSS-' || substr(upper(p_code), 4)
    WHEN upper(p_code) ~ '^CROSS-'  THEN upper(p_code)
    ELSE upper(p_code)
  END
$$;


ALTER FUNCTION "public"."normalize_cross_code"("p_code" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."safe_drop_view"("_schema" "text", "_name" "text") RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_views WHERE schemaname=_schema AND viewname=_name) THEN
    EXECUTE format('DROP VIEW %I.%I CASCADE', _schema, _name);
  END IF;
END$$;


ALTER FUNCTION "public"."safe_drop_view"("_schema" "text", "_name" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."set_container_status"("p_id" "uuid", "p_new" "public"."container_status", "p_by" "text", "p_reason" "text" DEFAULT NULL::"text") RETURNS "void"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."set_container_status"("p_id" "uuid", "p_new" "public"."container_status", "p_by" "text", "p_reason" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."tg_upsert_fish_seed_maps"() RETURNS "trigger"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."tg_upsert_fish_seed_maps"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."to_base36"("n" integer) RETURNS "text"
    LANGUAGE "plpgsql" IMMUTABLE
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


ALTER FUNCTION "public"."to_base36"("n" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."trg_clutch_code"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  IF NEW.clutch_code IS NULL OR btrim(NEW.clutch_code) = '' THEN
    NEW.clutch_code := public.gen_clutch_code();
  END IF;
  RETURN NEW;
END$$;


ALTER FUNCTION "public"."trg_clutch_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."trg_clutch_instance_code"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN IF NEW.clutch_instance_code IS NULL OR btrim(NEW.clutch_instance_code)='' THEN NEW.clutch_instance_code:=public.gen_clutch_instance_code(); END IF; RETURN NEW; END;
$$;


ALTER FUNCTION "public"."trg_clutch_instance_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."trg_containers_activate_on_label"() RETURNS "trigger"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."trg_containers_activate_on_label"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."trg_cross_code"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN IF NEW.cross_code IS NULL OR btrim(NEW.cross_code)='' THEN NEW.cross_code:=public.gen_cross_code(); END IF; RETURN NEW; END;
$$;


ALTER FUNCTION "public"."trg_cross_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."trg_cross_code_normalize"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  -- Normalize unconditionally; other BEFORE triggers may set NEW.cross_code
  NEW.cross_code := public.normalize_cross_code(NEW.cross_code);
  RETURN NEW;
END
$$;


ALTER FUNCTION "public"."trg_cross_code_normalize"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."trg_cross_name_fill"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  IF NEW.cross_name IS NULL OR btrim(NEW.cross_name)='' THEN NEW.cross_name:=public.gen_cross_name(NEW.mother_code,NEW.father_code); END IF;
  IF NEW.cross_nickname IS NULL OR btrim(NEW.cross_nickname)='' THEN NEW.cross_nickname:=NEW.cross_name; END IF;
  RETURN NEW;
END
$$;


ALTER FUNCTION "public"."trg_cross_name_fill"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."trg_cross_run_code"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN IF NEW.cross_run_code IS NULL OR btrim(NEW.cross_run_code)='' THEN NEW.cross_run_code:=public.gen_cross_run_code(); END IF; RETURN NEW; END;
$$;


ALTER FUNCTION "public"."trg_cross_run_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."trg_fish_autotank"() RETURNS "trigger"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."trg_fish_autotank"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."trg_log_container_status"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.status IS DISTINCT FROM OLD.status THEN
    INSERT INTO public.container_status_history(container_id, old_status, new_status, changed_by, reason)
    VALUES (NEW.id_uuid, OLD.status, NEW.status, current_user, 'trigger');
  END IF;
  RETURN NEW;
END $$;


ALTER FUNCTION "public"."trg_log_container_status"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."trg_plasmid_auto_ensure_rna"() RETURNS "trigger"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."trg_plasmid_auto_ensure_rna"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."trg_registry_fill_modern"() RETURNS "trigger"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."trg_registry_fill_modern"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."trg_set_updated_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END
$$;


ALTER FUNCTION "public"."trg_set_updated_at"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."upsert_fish_by_batch_name_dob"("p_seed_batch_id" "text", "p_name" "text", "p_date_birth" "date", "p_genetic_background" "text" DEFAULT NULL::"text", "p_nickname" "text" DEFAULT NULL::"text", "p_line_building_stage" "text" DEFAULT NULL::"text", "p_description" "text" DEFAULT NULL::"text", "p_notes" "text" DEFAULT NULL::"text", "p_created_by" "text" DEFAULT NULL::"text") RETURNS TABLE("fish_id" "uuid", "fish_code" "text")
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public', 'pg_temp'
    AS $$
DECLARE
  v_id   uuid;
  v_code text;
BEGIN
  -- try existing (batch, name, dob)
  SELECT f.id_uuid, f.fish_code
    INTO v_id, v_code
  FROM public.fish f
  JOIN public.fish_seed_batches_map m
    ON m.fish_id = f.id_uuid
   AND m.seed_batch_id = p_seed_batch_id
  WHERE f.name = p_name
    AND f.date_birth = p_date_birth
  LIMIT 1;

  IF v_id IS NOT NULL THEN
    UPDATE public.fish
       SET name                = COALESCE(p_name, name),
           date_birth          = COALESCE(p_date_birth, date_birth),
           genetic_background  = COALESCE(p_genetic_background, genetic_background),
           nickname            = COALESCE(p_nickname, nickname),
           line_building_stage = COALESCE(p_line_building_stage, line_building_stage),
           description         = COALESCE(p_description, description),
           notes               = COALESCE(p_notes, notes),
           created_by          = COALESCE(p_created_by, created_by)
     WHERE id_uuid = v_id;

    RETURN QUERY SELECT v_id, v_code;
    RETURN;
  END IF;

  -- insert new
  INSERT INTO public.fish (
    name, date_birth, genetic_background, nickname,
    line_building_stage, description, notes, created_by
  )
  VALUES (
    p_name, p_date_birth, p_genetic_background, p_nickname,
    p_line_building_stage, p_description, p_notes, p_created_by
  )
  RETURNING id_uuid, public.fish.fish_code  -- disambiguate the column
  INTO v_id, v_code;

  -- map to batch (idempotent)
  INSERT INTO public.fish_seed_batches_map (fish_id, seed_batch_id)
  VALUES (v_id, p_seed_batch_id)
  ON CONFLICT DO NOTHING;

  RETURN QUERY SELECT v_id, v_code;
END;
$$;


ALTER FUNCTION "public"."upsert_fish_by_batch_name_dob"("p_seed_batch_id" "text", "p_name" "text", "p_date_birth" "date", "p_genetic_background" "text", "p_nickname" "text", "p_line_building_stage" "text", "p_description" "text", "p_notes" "text", "p_created_by" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."upsert_transgene_allele_label"("p_base" "text", "p_label" "text", OUT "out_allele_number" integer) RETURNS integer
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."upsert_transgene_allele_label"("p_base" "text", "p_label" "text", OUT "out_allele_number" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."upsert_transgene_allele_name"("p_base" "text", "p_name" "text", OUT "out_allele_number" integer) RETURNS integer
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."upsert_transgene_allele_name"("p_base" "text", "p_name" "text", OUT "out_allele_number" integer) OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."allele_nicknames" (
    "base_code" "text" NOT NULL,
    "allele_code" "text" NOT NULL,
    "allele_nickname" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."allele_nicknames" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."bruker_mounts" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "selection_id" "uuid" NOT NULL,
    "mount_date" "date" NOT NULL,
    "mount_time" time without time zone NOT NULL,
    "n_top" integer NOT NULL,
    "n_bottom" integer NOT NULL,
    "orientation" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text",
    "mount_code" "text",
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "selection_id_uuid" "uuid",
    CONSTRAINT "bruker_mounts_n_bottom_check" CHECK (("n_bottom" >= 0)),
    CONSTRAINT "bruker_mounts_n_top_check" CHECK (("n_top" >= 0)),
    CONSTRAINT "bruker_mounts_orientation_check" CHECK (("orientation" = ANY (ARRAY['dorsal'::"text", 'ventral'::"text", 'left'::"text", 'right'::"text", 'front'::"text", 'back'::"text", 'other'::"text"])))
);


ALTER TABLE "public"."bruker_mounts" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."clutch_containers" (
    "container_id" "uuid" NOT NULL,
    "clutch_id" "uuid" NOT NULL,
    "is_mixed" boolean DEFAULT true NOT NULL,
    "selection_label" "text",
    "source_container_id" "uuid",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text" NOT NULL,
    "note" "text",
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."clutch_containers" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."clutch_genotype_options" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "clutch_id" "uuid" NOT NULL,
    "allele_code" "text",
    "transgene_base_code" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."clutch_genotype_options" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."clutch_instance_code_seq"
    START WITH 10000
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."clutch_instance_code_seq" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."clutch_instances" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "label" "text",
    "phenotype" "text",
    "notes" "text",
    "red_selected" boolean,
    "red_intensity" "text",
    "red_note" "text",
    "green_selected" boolean,
    "green_intensity" "text",
    "green_note" "text",
    "annotated_by" "text",
    "annotated_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "cross_instance_id" "uuid",
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL
);


ALTER TABLE "public"."clutch_instances" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."clutch_plan_treatments" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "clutch_id" "uuid" NOT NULL,
    "material_type" "text" NOT NULL,
    "material_code" "text" NOT NULL,
    "material_name" "text",
    "dose" numeric,
    "units" "text",
    "at_hpf" numeric,
    "notes" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "clutch_plan_treatments_material_type_check" CHECK (("material_type" = ANY (ARRAY['plasmid'::"text", 'rna'::"text"])))
);


ALTER TABLE "public"."clutch_plan_treatments" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."clutch_plans" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "mom_code" "text" NOT NULL,
    "dad_code" "text" NOT NULL,
    "cross_date" "date" DEFAULT CURRENT_DATE NOT NULL,
    "note" "text",
    "created_by" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "planned_name" "text",
    "planned_nickname" "text",
    "clutch_code" "text",
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."clutch_plans" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."clutch_treatments" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "clutch_id" "uuid" NOT NULL,
    "type" "text" NOT NULL,
    "reagent_id" "uuid",
    "amount" numeric,
    "units" "text",
    "at_time" timestamp with time zone,
    "note" "text",
    "created_by" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "clutch_treatments_type_check" CHECK (("type" = ANY (ARRAY['injected_plasmid'::"text", 'injected_rna'::"text"])))
);


ALTER TABLE "public"."clutch_treatments" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."clutches" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "cross_id" "uuid" NOT NULL,
    "batch_label" "text",
    "seed_batch_id" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text" NOT NULL,
    "note" "text",
    "date_birth" "date",
    "run_id" "uuid",
    "planned_cross_id" "uuid",
    "cross_instance_id" "uuid",
    "clutch_instance_code" "text",
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."clutches" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."container_status_history" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "container_id" "uuid" NOT NULL,
    "old_status" "public"."container_status" NOT NULL,
    "new_status" "public"."container_status" NOT NULL,
    "changed_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "changed_by" "text",
    "reason" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."container_status_history" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."containers" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "container_type" "text" NOT NULL,
    "label" "text",
    "status" "text" DEFAULT 'planned'::"public"."container_status" NOT NULL,
    "created_by" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "note" "text",
    "request_id" "uuid",
    "status_changed_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "activated_at" timestamp with time zone,
    "deactivated_at" timestamp with time zone,
    "last_seen_at" timestamp with time zone,
    "last_seen_source" "text",
    "tank_volume_l" integer,
    "tank_code" "text",
    "updated_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "chk_containers_type_allowed" CHECK (("container_type" = ANY (ARRAY['inventory_tank'::"text", 'crossing_tank'::"text", 'holding_tank'::"text", 'nursery_tank'::"text", 'petri_dish'::"text"]))),
    CONSTRAINT "chk_containers_volume_allowed" CHECK ((("tank_volume_l" IS NULL) OR ("tank_volume_l" = ANY (ARRAY[2, 4, 8, 16])))),
    CONSTRAINT "chk_tank_code_shape" CHECK ((("tank_code" IS NULL) OR ("tank_code" ~ '^TANK-[0-9A-Z]{2}[0-9A-Z]{4,}$'::"text"))),
    CONSTRAINT "containers_status_check" CHECK (("status" = ANY (ARRAY['planned'::"text", 'new_tank'::"text", 'active'::"text", 'ready_to_kill'::"text", 'inactive'::"text"])))
);


ALTER TABLE "public"."containers" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."cross_code_seq"
    START WITH 10000
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."cross_code_seq" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."cross_instances" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "cross_id" "uuid" NOT NULL,
    "cross_date" "date" DEFAULT CURRENT_DATE NOT NULL,
    "mother_tank_id" "uuid",
    "father_tank_id" "uuid",
    "note" "text",
    "created_by" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "cross_run_code" "text",
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."cross_instances" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."cross_plan_genotype_alleles" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "plan_id" "uuid" NOT NULL,
    "transgene_base_code" "text" NOT NULL,
    "allele_number" integer NOT NULL,
    "zygosity_planned" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."cross_plan_genotype_alleles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."cross_plan_runs" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "plan_id" "uuid" NOT NULL,
    "seq" integer NOT NULL,
    "planned_date" "date" NOT NULL,
    "tank_a_id" "uuid",
    "tank_b_id" "uuid",
    "status" "text" DEFAULT 'planned'::"text" NOT NULL,
    "note" "text",
    "created_by" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."cross_plan_runs" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."cross_plan_treatments" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "plan_id" "uuid" NOT NULL,
    "treatment_name" "text" NOT NULL,
    "amount" numeric,
    "units" "text",
    "timing_note" "text",
    "injection_mix" "text",
    "treatment_notes" "text",
    "rna_id" "uuid",
    "plasmid_id" "uuid",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "chk_cpt_one_reagent" CHECK ((((("rna_id" IS NOT NULL))::integer + (("plasmid_id" IS NOT NULL))::integer) <= 1))
);


ALTER TABLE "public"."cross_plan_treatments" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."cross_plans" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "plan_date" "date" NOT NULL,
    "tank_a_id" "uuid",
    "tank_b_id" "uuid",
    "status" "public"."cross_plan_status" DEFAULT 'planned'::"public"."cross_plan_status" NOT NULL,
    "created_by" "text" NOT NULL,
    "note" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "mother_fish_id" "uuid",
    "father_fish_id" "uuid",
    "plan_title" "text",
    "plan_nickname" "text",
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."cross_plans" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."cross_run_code_seq"
    START WITH 10000
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."cross_run_code_seq" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."crosses" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "mother_code" "text" NOT NULL,
    "father_code" "text" NOT NULL,
    "created_by" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "note" "text",
    "planned_for" "date",
    "cross_code" "text",
    "cross_name" "text",
    "cross_nickname" "text",
    "updated_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "chk_cross_code_shape" CHECK ((("cross_code" IS NULL) OR ("cross_code" ~ '^CROSS-[0-9A-Z]{2}[0-9A-Z]{4,}$'::"text")))
);


ALTER TABLE "public"."crosses" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."fish" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "fish_code" "text" NOT NULL,
    "name" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text",
    "date_birth" "date",
    "nickname" "text",
    "line_building_stage" "text",
    "id_uuid" "uuid" GENERATED ALWAYS AS ("id") STORED NOT NULL,
    "genetic_background" "text",
    "description" "text",
    "notes" "text",
    "updated_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "chk_fish_code_shape" CHECK ((("fish_code" IS NULL) OR ("fish_code" ~ '^FSH-[0-9A-Z]{2}[0-9A-Z]+$'::"text"))),
    CONSTRAINT "ck_fish_fish_code_format" CHECK (("fish_code" ~ '^FSH-[0-9]{2}[0-9A-Z]{4,}$'::"text"))
);


ALTER TABLE "public"."fish" OWNER TO "postgres";


COMMENT ON COLUMN "public"."fish"."genetic_background" IS 'Background genetic strain (from CSV: genetic_background).';



CREATE TABLE IF NOT EXISTS "public"."fish_code_audit" (
    "id" bigint NOT NULL,
    "at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "fish_id" "uuid",
    "fish_code" "text",
    "app_name" "text",
    "client_addr" "inet",
    "pid" integer,
    "note" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."fish_code_audit" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."fish_code_audit_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."fish_code_audit_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."fish_code_audit_id_seq" OWNED BY "public"."fish_code_audit"."id";



CREATE SEQUENCE IF NOT EXISTS "public"."fish_code_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."fish_code_seq" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."fish_seed_batches" (
    "fish_id" "uuid" NOT NULL,
    "seed_batch_id" "text" NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."fish_seed_batches" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."fish_seed_batches_map" (
    "fish_id" "uuid" NOT NULL,
    "seed_batch_id" "text",
    "logged_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."fish_seed_batches_map" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."fish_tank_memberships" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "fish_id" "uuid" NOT NULL,
    "container_id" "uuid" NOT NULL,
    "joined_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "left_at" timestamp with time zone,
    "note" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."fish_tank_memberships" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."fish_transgene_alleles" (
    "fish_id" "uuid" NOT NULL,
    "transgene_base_code" "text" NOT NULL,
    "allele_number" integer NOT NULL,
    "zygosity" "text",
    "allele_nickname" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text",
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."fish_transgene_alleles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."fish_year_counters" (
    "year" integer NOT NULL,
    "n" bigint DEFAULT 0 NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."fish_year_counters" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."injected_plasmid_treatments" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "fish_id" "uuid" NOT NULL,
    "plasmid_id" "uuid" NOT NULL,
    "amount" numeric,
    "units" "text",
    "at_time" timestamp with time zone,
    "note" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."injected_plasmid_treatments" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."injected_rna_treatments" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "fish_id" "uuid" NOT NULL,
    "rna_id" "uuid" NOT NULL,
    "amount" numeric,
    "units" "text",
    "at_time" timestamp with time zone,
    "note" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."injected_rna_treatments" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."label_items" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "job_id" "uuid" NOT NULL,
    "seq" integer NOT NULL,
    "fish_code" "text",
    "tank_id" "uuid",
    "request_id" "uuid",
    "payload" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "qr_text" "text",
    "rendered_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "label_items_seq_check" CHECK (("seq" > 0))
);


ALTER TABLE "public"."label_items" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."label_jobs" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "entity_type" "text" NOT NULL,
    "entity_id" "uuid",
    "template" "text" DEFAULT 'tank_2.4x1.5'::"text" NOT NULL,
    "media" "text" DEFAULT '2.4x1.5'::"text" NOT NULL,
    "status" "text" DEFAULT 'queued'::"text" NOT NULL,
    "requested_by" "text" NOT NULL,
    "requested_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "started_at" timestamp with time zone,
    "finished_at" timestamp with time zone,
    "error_text" "text",
    "num_labels" integer DEFAULT 0 NOT NULL,
    "file_url" "text",
    "file_bytes" "bytea",
    "source_params" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "notes" "text",
    "dedupe_hash" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "label_jobs_num_labels_check" CHECK (("num_labels" >= 0)),
    CONSTRAINT "label_jobs_status_check" CHECK (("status" = ANY (ARRAY['queued'::"text", 'processing'::"text", 'done'::"text", 'error'::"text", 'cancelled'::"text"])))
);


ALTER TABLE "public"."label_jobs" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."load_log_fish" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "fish_id" "uuid" NOT NULL,
    "seed_batch_id" "text" NOT NULL,
    "row_key" "text" NOT NULL,
    "logged_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."load_log_fish" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."planned_crosses" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "clutch_id" "uuid",
    "mom_code" "text" NOT NULL,
    "dad_code" "text" NOT NULL,
    "crossing_tank_id" "uuid",
    "cross_date" "date" DEFAULT CURRENT_DATE NOT NULL,
    "note" "text",
    "created_by" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "mother_tank_id" "uuid",
    "father_tank_id" "uuid",
    "cross_code" "text",
    "cross_id" "uuid",
    "cross_instance_id" "uuid",
    "is_canonical" boolean DEFAULT true NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "name" "text",
    "nickname" "text",
    "planned_for" "date",
    "status" "text",
    "notes" "text"
);


ALTER TABLE "public"."planned_crosses" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."plasmid_registry" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "plasmid_code" "text" NOT NULL,
    "plasmid_nickname" "text",
    "backbone" "text",
    "insert_desc" "text",
    "vendor" "text",
    "lot_number" "text",
    "notes" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text",
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."plasmid_registry" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."plasmids" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "code" "text" NOT NULL,
    "name" "text",
    "nickname" "text",
    "fluors" "text",
    "resistance" "text",
    "supports_invitro_rna" boolean DEFAULT false NOT NULL,
    "created_by" "text",
    "notes" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."plasmids" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."rna_registry" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "rna_code" "text" NOT NULL,
    "rna_nickname" "text",
    "vendor" "text",
    "lot_number" "text",
    "notes" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text",
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."rna_registry" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."rnas" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "code" "text" NOT NULL,
    "name" "text",
    "source_plasmid_id" "uuid",
    "created_by" "text",
    "notes" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."rnas" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."seed_batches" AS
 SELECT NULL::"text" AS "seed_batch_id",
    NULL::"text" AS "batch_label"
  WHERE false;


ALTER VIEW "public"."seed_batches" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."selection_labels" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "code" "text" NOT NULL,
    "display_name" "text" NOT NULL,
    "color_hex" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text",
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."selection_labels" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."seq_clutch_code"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."seq_clutch_code" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."tank_code_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."tank_code_seq" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."tank_requests" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "fish_id" "uuid" NOT NULL,
    "requested_count" integer NOT NULL,
    "fulfilled_count" integer DEFAULT 0 NOT NULL,
    "requested_for" "date",
    "note" "text",
    "status" "text" DEFAULT 'open'::"text" NOT NULL,
    "created_by" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"(),
    CONSTRAINT "tank_requests_fulfilled_count_check" CHECK (("fulfilled_count" >= 0)),
    CONSTRAINT "tank_requests_requested_count_check" CHECK (("requested_count" > 0)),
    CONSTRAINT "tank_requests_status_check" CHECK (("status" = ANY (ARRAY['open'::"text", 'fulfilled'::"text", 'cancelled'::"text"])))
);


ALTER TABLE "public"."tank_requests" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."tank_year_counters" (
    "year" integer NOT NULL,
    "n" bigint DEFAULT 0 NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."tank_year_counters" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."transgene_allele_counters" (
    "transgene_base_code" "text" NOT NULL,
    "next_number" integer DEFAULT 1 NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."transgene_allele_counters" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."transgene_allele_registry" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "transgene_base_code" "text" NOT NULL,
    "allele_number" integer NOT NULL,
    "allele_nickname" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text",
    "base_code" "text",
    "legacy_label" "text",
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."transgene_allele_registry" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."transgene_alleles" (
    "transgene_base_code" "text" NOT NULL,
    "allele_number" integer NOT NULL,
    "allele_nickname" "text",
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."transgene_alleles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."transgenes" (
    "transgene_base_code" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text",
    "updated_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."transgenes" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."vw_planned_clutches_overview" AS
 WITH "x" AS (
         SELECT "cp"."id_uuid" AS "clutch_plan_id",
            "pc"."id_uuid" AS "planned_cross_id",
            "cp"."clutch_code",
            "cp"."planned_name" AS "clutch_name",
            "cp"."planned_nickname" AS "clutch_nickname",
            "pc"."cross_date",
            "cp"."created_by",
            "cp"."created_at",
            COALESCE("cp"."note", "pc"."note") AS "note"
           FROM ("public"."clutch_plans" "cp"
             LEFT JOIN "public"."planned_crosses" "pc" ON (("pc"."clutch_id" = "cp"."id_uuid")))
        ), "tx" AS (
         SELECT "t"."clutch_id" AS "clutch_plan_id",
            ("count"(*))::integer AS "n_treatments"
           FROM "public"."clutch_plan_treatments" "t"
          GROUP BY "t"."clutch_id"
        )
 SELECT "x"."clutch_plan_id",
    "x"."planned_cross_id",
    "x"."clutch_code",
    "x"."clutch_name",
    "x"."clutch_nickname",
    "x"."cross_date",
    "x"."created_by",
    "x"."created_at",
    "x"."note",
    COALESCE("tx"."n_treatments", 0) AS "n_treatments"
   FROM ("x"
     LEFT JOIN "tx" ON (("tx"."clutch_plan_id" = "x"."clutch_plan_id")))
  ORDER BY COALESCE((("x"."cross_date")::timestamp without time zone)::timestamp with time zone, "x"."created_at") DESC NULLS LAST;


ALTER VIEW "public"."vw_planned_clutches_overview" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_cross_concepts_overview" AS
 SELECT "v"."clutch_code" AS "conceptual_cross_code",
    "v"."clutch_code",
    COALESCE("v"."clutch_name", ''::"text") AS "name",
    COALESCE("v"."clutch_nickname", ''::"text") AS "nickname",
    COALESCE("pc"."mom_code", ''::"text") AS "mom_code",
    COALESCE("pc"."dad_code", ''::"text") AS "dad_code",
    COALESCE(( SELECT COALESCE("c"."tank_code", "c"."label") AS "coalesce"
           FROM "public"."containers" "c"
          WHERE ("c"."id_uuid" = "pc"."mother_tank_id")), ( SELECT COALESCE("c2"."tank_code", "c2"."label") AS "coalesce"
           FROM (("public"."fish" "f2"
             JOIN "public"."fish_tank_memberships" "m2" ON ((("m2"."fish_id" = "f2"."id") AND ("m2"."left_at" IS NULL))))
             JOIN "public"."containers" "c2" ON ((("c2"."id_uuid" = "m2"."container_id") AND ("c2"."status" = ANY (ARRAY['active'::"text", 'new_tank'::"text"])))))
          WHERE ("f2"."fish_code" = "pc"."mom_code")
          ORDER BY COALESCE("c2"."activated_at", "c2"."created_at") DESC NULLS LAST
         LIMIT 1), ''::"text") AS "mom_code_tank",
    COALESCE(( SELECT COALESCE("c"."tank_code", "c"."label") AS "coalesce"
           FROM "public"."containers" "c"
          WHERE ("c"."id_uuid" = "pc"."father_tank_id")), ( SELECT COALESCE("c2"."tank_code", "c2"."label") AS "coalesce"
           FROM (("public"."fish" "f2"
             JOIN "public"."fish_tank_memberships" "m2" ON ((("m2"."fish_id" = "f2"."id") AND ("m2"."left_at" IS NULL))))
             JOIN "public"."containers" "c2" ON ((("c2"."id_uuid" = "m2"."container_id") AND ("c2"."status" = ANY (ARRAY['active'::"text", 'new_tank'::"text"])))))
          WHERE ("f2"."fish_code" = "pc"."dad_code")
          ORDER BY COALESCE("c2"."activated_at", "c2"."created_at") DESC NULLS LAST
         LIMIT 1), ''::"text") AS "dad_code_tank",
    COALESCE("v"."n_treatments", 0) AS "n_treatments",
    COALESCE("v"."created_by", ''::"text") AS "created_by",
    "v"."created_at"
   FROM ("public"."vw_planned_clutches_overview" "v"
     LEFT JOIN "public"."planned_crosses" "pc" ON (("pc"."cross_code" = "v"."clutch_code")));


ALTER VIEW "public"."v_cross_concepts_overview" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."vw_cross_runs_overview" AS
 SELECT "ci"."id_uuid" AS "cross_instance_id",
    "ci"."cross_run_code",
    "ci"."cross_date",
    "cr"."id_uuid" AS "cross_id",
    "cr"."cross_code",
    "cr"."mother_code" AS "mom_code",
    "cr"."father_code" AS "dad_code",
    COALESCE(( SELECT COALESCE("c"."tank_code", "c"."label") AS "coalesce"
           FROM "public"."containers" "c"
          WHERE ("c"."id_uuid" = "ci"."mother_tank_id")), ( SELECT COALESCE("c2"."tank_code", "c2"."label") AS "coalesce"
           FROM (("public"."fish" "f2"
             JOIN "public"."fish_tank_memberships" "m2" ON ((("m2"."fish_id" = "f2"."id") AND ("m2"."left_at" IS NULL))))
             JOIN "public"."containers" "c2" ON ((("c2"."id_uuid" = "m2"."container_id") AND ("c2"."status" = ANY (ARRAY['active'::"text", 'new_tank'::"text"])))))
          WHERE ("f2"."fish_code" = "cr"."mother_code")
          ORDER BY COALESCE("c2"."activated_at", "c2"."created_at") DESC NULLS LAST
         LIMIT 1)) AS "mother_tank_label",
    COALESCE(( SELECT COALESCE("c"."tank_code", "c"."label") AS "coalesce"
           FROM "public"."containers" "c"
          WHERE ("c"."id_uuid" = "ci"."father_tank_id")), ( SELECT COALESCE("c2"."tank_code", "c2"."label") AS "coalesce"
           FROM (("public"."fish" "f2"
             JOIN "public"."fish_tank_memberships" "m2" ON ((("m2"."fish_id" = "f2"."id") AND ("m2"."left_at" IS NULL))))
             JOIN "public"."containers" "c2" ON ((("c2"."id_uuid" = "m2"."container_id") AND ("c2"."status" = ANY (ARRAY['active'::"text", 'new_tank'::"text"])))))
          WHERE ("f2"."fish_code" = "cr"."father_code")
          ORDER BY COALESCE("c2"."activated_at", "c2"."created_at") DESC NULLS LAST
         LIMIT 1)) AS "father_tank_label",
    "ci"."note" AS "run_note",
    "ci"."created_by" AS "run_created_by",
    "ci"."created_at" AS "run_created_at",
    0 AS "n_clutches",
    0 AS "n_containers"
   FROM ("public"."cross_instances" "ci"
     JOIN "public"."crosses" "cr" ON (("cr"."id_uuid" = "ci"."cross_id")));


ALTER VIEW "public"."vw_cross_runs_overview" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_bruker_mounts_enriched" AS
 WITH "m" AS (
         SELECT "bruker_mounts"."id",
            "bruker_mounts"."selection_id",
            "bruker_mounts"."mount_date",
            "bruker_mounts"."mount_time",
            "bruker_mounts"."n_top",
            "bruker_mounts"."n_bottom",
            "bruker_mounts"."orientation",
            "bruker_mounts"."created_at",
            "bruker_mounts"."created_by",
            "bruker_mounts"."mount_code",
            "bruker_mounts"."updated_at"
           FROM "public"."bruker_mounts"
        ), "ci" AS (
         SELECT ("clutch_instances"."id")::"text" AS "selection_id",
            "clutch_instances"."cross_instance_id",
            COALESCE("clutch_instances"."label", ''::"text") AS "selection_label"
           FROM "public"."clutch_instances"
        ), "r" AS (
         SELECT "vw_cross_runs_overview"."cross_instance_id",
            "vw_cross_runs_overview"."cross_run_code",
            "vw_cross_runs_overview"."mom_code",
            "vw_cross_runs_overview"."dad_code"
           FROM "public"."vw_cross_runs_overview"
        ), "c" AS (
         SELECT "v_cross_concepts_overview"."mom_code",
            "v_cross_concepts_overview"."dad_code",
            "v_cross_concepts_overview"."name" AS "clutch_name",
            "v_cross_concepts_overview"."nickname" AS "clutch_nickname"
           FROM "public"."v_cross_concepts_overview"
        ), "ann" AS (
         SELECT "clutch_instances"."cross_instance_id",
            "string_agg"(NULLIF(TRIM(BOTH FROM "concat_ws"(' '::"text",
                CASE
                    WHEN (COALESCE("clutch_instances"."red_intensity", ''::"text") <> ''::"text") THEN ('red='::"text" || "clutch_instances"."red_intensity")
                    ELSE NULL::"text"
                END,
                CASE
                    WHEN (COALESCE("clutch_instances"."green_intensity", ''::"text") <> ''::"text") THEN ('green='::"text" || "clutch_instances"."green_intensity")
                    ELSE NULL::"text"
                END,
                CASE
                    WHEN (COALESCE("clutch_instances"."notes", ''::"text") <> ''::"text") THEN ('note='::"text" || "clutch_instances"."notes")
                    ELSE NULL::"text"
                END)), ''::"text"), ' | '::"text" ORDER BY "clutch_instances"."created_at") AS "annotations_rollup"
           FROM "public"."clutch_instances"
          GROUP BY "clutch_instances"."cross_instance_id"
        )
 SELECT ((('BRUKER '::"text" || "to_char"(("m"."mount_date")::timestamp with time zone, 'YYYY-MM-DD'::"text")) || ' #'::"text") || "row_number"() OVER (PARTITION BY "m"."mount_date" ORDER BY "m"."mount_time", "m"."created_at")) AS "mount_code",
    "m"."mount_date",
    "m"."mount_time",
    "ci"."selection_label",
    "r"."cross_run_code",
    "c"."clutch_name",
    "c"."clutch_nickname",
    "ann"."annotations_rollup",
    "m"."n_top",
    "m"."n_bottom",
    "m"."orientation",
    "m"."created_at",
    "m"."created_by",
    "m"."selection_id",
    "r"."cross_instance_id"
   FROM (((("m"
     LEFT JOIN "ci" ON (("ci"."selection_id" = ("m"."selection_id")::"text")))
     LEFT JOIN "r" ON (("r"."cross_instance_id" = "ci"."cross_instance_id")))
     LEFT JOIN "c" ON ((("c"."mom_code" = "r"."mom_code") AND ("c"."dad_code" = "r"."dad_code"))))
     LEFT JOIN "ann" ON (("ann"."cross_instance_id" = "r"."cross_instance_id")));


ALTER VIEW "public"."v_bruker_mounts_enriched" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_clutch_instance_selections" AS
 SELECT "id" AS "selection_id",
    "cross_instance_id",
    "created_at" AS "selection_created_at",
    "annotated_at" AS "selection_annotated_at",
    "red_intensity",
    "green_intensity",
    "notes",
    "annotated_by",
    "label"
   FROM "public"."clutch_instances" "ci";


ALTER VIEW "public"."v_clutch_instance_selections" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_clutch_instances_annotations" AS
 SELECT "id",
    COALESCE("label", ''::"text") AS "label",
    COALESCE("phenotype", ''::"text") AS "phenotype",
    COALESCE("notes", ''::"text") AS "notes",
    COALESCE("red_selected", false) AS "red_selected",
    COALESCE("red_intensity", ''::"text") AS "red_intensity",
    COALESCE("red_note", ''::"text") AS "red_note",
    COALESCE("green_selected", false) AS "green_selected",
    COALESCE("green_intensity", ''::"text") AS "green_intensity",
    COALESCE("green_note", ''::"text") AS "green_note",
    COALESCE("annotated_by", ''::"text") AS "annotated_by",
    "annotated_at",
    "created_at"
   FROM "public"."clutch_instances";


ALTER VIEW "public"."v_clutch_instances_annotations" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_containers_crossing_candidates" AS
 SELECT "id_uuid",
    "container_type",
    "label",
    "status",
    "created_by",
    "created_at",
    "status_changed_at",
    "activated_at",
    "deactivated_at",
    "last_seen_at",
    "note"
   FROM "public"."containers"
  WHERE ("container_type" = ANY (ARRAY['inventory_tank'::"text", 'crossing_tank'::"text", 'holding_tank'::"text", 'nursery_tank'::"text", 'petri_dish'::"text"]));


ALTER VIEW "public"."v_containers_crossing_candidates" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_containers_live" AS
 SELECT "id_uuid",
    "container_type",
    "label",
    "status",
    "created_by",
    "created_at",
    "note",
    "request_id",
    "status_changed_at",
    "activated_at",
    "deactivated_at",
    "last_seen_at",
    "last_seen_source",
    "tank_volume_l",
    "tank_code"
   FROM "public"."containers"
  WHERE ("status" = ANY (ARRAY['active'::"text", 'new_tank'::"text"]));


ALTER VIEW "public"."v_containers_live" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_cross_plan_runs_enriched" AS
 SELECT "r"."id",
    "r"."plan_id",
    "r"."seq",
    "r"."planned_date",
    "r"."status",
    "r"."note",
    "r"."created_by",
    "r"."created_at",
    "p"."plan_title",
    "p"."plan_nickname",
    "p"."mother_fish_id",
    "p"."father_fish_id",
    "fm"."fish_code" AS "mother_fish_code",
    "ff"."fish_code" AS "father_fish_code",
    "ca"."label" AS "tank_a_label",
    "cb"."label" AS "tank_b_label"
   FROM ((((("public"."cross_plan_runs" "r"
     JOIN "public"."cross_plans" "p" ON (("p"."id" = "r"."plan_id")))
     LEFT JOIN "public"."fish" "fm" ON (("fm"."id" = "p"."mother_fish_id")))
     LEFT JOIN "public"."fish" "ff" ON (("ff"."id" = "p"."father_fish_id")))
     LEFT JOIN "public"."containers" "ca" ON (("ca"."id_uuid" = "r"."tank_a_id")))
     LEFT JOIN "public"."containers" "cb" ON (("cb"."id_uuid" = "r"."tank_b_id")));


ALTER VIEW "public"."v_cross_plan_runs_enriched" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_cross_plans_enriched" AS
 SELECT "p"."id",
    "p"."plan_date",
    "p"."status",
    "p"."created_by",
    "p"."note",
    "p"."created_at",
    "p"."mother_fish_id",
    "fm"."fish_code" AS "mother_fish_code",
    "p"."father_fish_id",
    "ff"."fish_code" AS "father_fish_code",
    "p"."tank_a_id",
    "ca"."label" AS "tank_a_label",
    "p"."tank_b_id",
    "cb"."label" AS "tank_b_label",
    COALESCE(( SELECT "string_agg"("format"('%s[%s]%s'::"text", "g"."transgene_base_code", "g"."allele_number", COALESCE((' '::"text" || "g"."zygosity_planned"), ''::"text")), ', '::"text" ORDER BY "g"."transgene_base_code", "g"."allele_number") AS "string_agg"
           FROM "public"."cross_plan_genotype_alleles" "g"
          WHERE ("g"."plan_id" = "p"."id")), ''::"text") AS "genotype_plan",
    COALESCE(( SELECT "string_agg"(TRIM(BOTH ' '::"text" FROM "concat"("t"."treatment_name",
                CASE
                    WHEN ("t"."amount" IS NOT NULL) THEN (' '::"text" || ("t"."amount")::"text")
                    ELSE ''::"text"
                END,
                CASE
                    WHEN ("t"."units" IS NOT NULL) THEN (' '::"text" || "t"."units")
                    ELSE ''::"text"
                END,
                CASE
                    WHEN ("t"."timing_note" IS NOT NULL) THEN ((' ['::"text" || "t"."timing_note") || ']'::"text")
                    ELSE ''::"text"
                END)), ', '::"text" ORDER BY "t"."treatment_name") AS "string_agg"
           FROM "public"."cross_plan_treatments" "t"
          WHERE ("t"."plan_id" = "p"."id")), ''::"text") AS "treatments_plan"
   FROM (((("public"."cross_plans" "p"
     LEFT JOIN "public"."fish" "fm" ON (("fm"."id" = "p"."mother_fish_id")))
     LEFT JOIN "public"."fish" "ff" ON (("ff"."id" = "p"."father_fish_id")))
     LEFT JOIN "public"."containers" "ca" ON (("ca"."id_uuid" = "p"."tank_a_id")))
     LEFT JOIN "public"."containers" "cb" ON (("cb"."id_uuid" = "p"."tank_b_id")));


ALTER VIEW "public"."v_cross_plans_enriched" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_crosses_status" AS
 SELECT "id_uuid",
    "mother_code",
    "father_code",
    "planned_for",
    "created_by",
    "created_at",
        CASE
            WHEN (EXISTS ( SELECT 1
               FROM "public"."clutches" "x"
              WHERE ("x"."cross_id" = "c"."id_uuid"))) THEN 'realized'::"text"
            ELSE 'planned'::"text"
        END AS "status"
   FROM "public"."crosses" "c";


ALTER VIEW "public"."v_crosses_status" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_fish_label_fields" AS
 SELECT "fish_code",
    "nickname",
    "name",
    NULL::"text" AS "base_code",
    NULL::"text" AS "tg_nick",
    "line_building_stage" AS "stage",
    "date_birth" AS "dob",
    NULLIF("array_to_string"(ARRAY( SELECT (("fa2"."transgene_base_code" || '^'::"text") || ("fa2"."allele_number")::"text")
           FROM "public"."fish_transgene_alleles" "fa2"
          WHERE ("fa2"."fish_id" = "f"."id_uuid")
          ORDER BY "fa2"."transgene_base_code", "fa2"."allele_number"), '; '::"text"), ''::"text") AS "genotype",
    "genetic_background"
   FROM "public"."fish" "f";


ALTER VIEW "public"."v_fish_label_fields" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_fish_living_tank_counts" AS
 SELECT "m"."fish_id",
    ("count"(*))::integer AS "n_living_tanks"
   FROM ("public"."fish_tank_memberships" "m"
     JOIN "public"."containers" "c" ON (("c"."id_uuid" = "m"."container_id")))
  WHERE (("m"."left_at" IS NULL) AND ("c"."status" = ANY (ARRAY['active'::"text", 'new_tank'::"text"])))
  GROUP BY "m"."fish_id";


ALTER VIEW "public"."v_fish_living_tank_counts" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."vw_fish_overview_with_label" AS
 WITH "base" AS (
         SELECT "f"."fish_code",
            "f"."name",
            "f"."nickname",
            "f"."line_building_stage",
            "f"."date_birth",
            "f"."genetic_background",
            "f"."created_by",
            "f"."created_at"
           FROM "public"."fish" "f"
        ), "allele" AS (
         SELECT DISTINCT ON ("f2"."fish_code") "f2"."fish_code",
            "l"."transgene_base_code",
            "l"."allele_number",
            "ta"."allele_nickname"
           FROM (("public"."fish_transgene_alleles" "l"
             JOIN "public"."fish" "f2" ON (("f2"."id_uuid" = "l"."fish_id")))
             LEFT JOIN "public"."transgene_alleles" "ta" ON ((("ta"."transgene_base_code" = "l"."transgene_base_code") AND ("ta"."allele_number" = "l"."allele_number"))))
          ORDER BY "f2"."fish_code", "l"."transgene_base_code", "l"."allele_number"
        ), "batch" AS (
         SELECT DISTINCT ON ("f3"."fish_code") "f3"."fish_code",
            "m"."seed_batch_id"
           FROM ("public"."fish_seed_batches_map" "m"
             JOIN "public"."fish" "f3" ON (("f3"."id_uuid" = "m"."fish_id")))
          ORDER BY "f3"."fish_code", "m"."logged_at" DESC NULLS LAST, "m"."created_at" DESC NULLS LAST
        )
 SELECT "b"."fish_code",
    "b"."name",
    "b"."nickname",
    "b"."line_building_stage",
    "b"."date_birth",
    "b"."genetic_background",
    "b"."created_by",
    "b"."created_at",
    "a"."transgene_base_code" AS "transgene_base_code_filled",
    ("a"."allele_number")::"text" AS "allele_code_filled",
    "a"."allele_nickname" AS "allele_name_filled",
    "batch"."seed_batch_id",
    "batch"."seed_batch_id" AS "batch_label",
    COALESCE("b"."nickname", ''::"text") AS "nickname_print",
    COALESCE("b"."genetic_background", ''::"text") AS "genetic_background_print",
    COALESCE("b"."line_building_stage", ''::"text") AS "line_building_stage_print",
    COALESCE("to_char"(("b"."date_birth")::timestamp with time zone, 'YYYY-MM-DD'::"text"), ''::"text") AS "date_birth_print",
        CASE
            WHEN ("a"."transgene_base_code" IS NULL) THEN ''::"text"
            WHEN ("a"."allele_number" IS NOT NULL) THEN (("a"."transgene_base_code" || '-'::"text") || ("a"."allele_number")::"text")
            WHEN ("a"."allele_nickname" IS NOT NULL) THEN (("a"."transgene_base_code" || ' '::"text") || "a"."allele_nickname")
            ELSE "a"."transgene_base_code"
        END AS "genotype_print",
        CASE
            WHEN ("b"."date_birth" IS NOT NULL) THEN (CURRENT_DATE - "b"."date_birth")
            ELSE NULL::integer
        END AS "age_days",
        CASE
            WHEN ("b"."date_birth" IS NOT NULL) THEN ((CURRENT_DATE - "b"."date_birth") / 7)
            ELSE NULL::integer
        END AS "age_weeks",
    COALESCE("b"."created_by", ''::"text") AS "created_by_enriched",
    NULL::"text" AS "plasmid_injections_text",
    NULL::"text" AS "rna_injections_text"
   FROM (("base" "b"
     LEFT JOIN "allele" "a" USING ("fish_code"))
     LEFT JOIN "batch" USING ("fish_code"))
  ORDER BY "b"."fish_code";


ALTER VIEW "public"."vw_fish_overview_with_label" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_fish_overview" AS
 SELECT "fish_code",
    COALESCE("name", ''::"text") AS "name",
    COALESCE("nickname", ''::"text") AS "nickname",
    COALESCE(''::"text", ''::"text", "allele_name_filled", "allele_code_filled", ''::"text") AS "genotype",
    NULL::"text" AS "genetic_background",
    COALESCE("line_building_stage", ''::"text") AS "stage",
    NULL::"date" AS "date_birth",
    NULL::timestamp with time zone AS "created_at",
    COALESCE("created_by", ''::"text") AS "created_by",
    COALESCE("batch_label", ''::"text") AS "batch_display",
    COALESCE(''::"text", ''::"text", "allele_name_filled", "allele_code_filled", ''::"text") AS "genotype_print",
    NULL::"text" AS "genetic_background_print"
   FROM "public"."vw_fish_overview_with_label" "v";


ALTER VIEW "public"."v_fish_overview" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_fish_overview_canonical" AS
 SELECT "fish_code",
    "name",
    "nickname",
    "line_building_stage",
    "date_birth",
    "genetic_background",
    "created_at",
    NULLIF("array_to_string"(ARRAY( SELECT (("fa2"."transgene_base_code" || '^'::"text") || ("fa2"."allele_number")::"text")
           FROM "public"."fish_transgene_alleles" "fa2"
          WHERE ("fa2"."fish_id" = "f"."id_uuid")
          ORDER BY "fa2"."transgene_base_code", "fa2"."allele_number"), '; '::"text"), ''::"text") AS "genotype_text",
    ("date_part"('day'::"text", ("now"() - ("date_birth")::timestamp with time zone)))::integer AS "age_days",
    ( SELECT "m"."seed_batch_id"
           FROM "public"."fish_seed_batches_map" "m"
          WHERE ("m"."fish_id" = "f"."id_uuid")
          ORDER BY "m"."logged_at" DESC
         LIMIT 1) AS "seed_batch_id"
   FROM "public"."fish" "f"
  ORDER BY "created_at" DESC;


ALTER VIEW "public"."v_fish_overview_canonical" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_label_jobs_recent" AS
 SELECT "id_uuid",
    "entity_type",
    "entity_id",
    "template",
    "media",
    "status",
    "requested_by",
    "requested_at",
    "started_at",
    "finished_at",
    "num_labels",
    (("file_bytes" IS NOT NULL) OR ("file_url" IS NOT NULL)) AS "has_file"
   FROM "public"."label_jobs" "j"
  ORDER BY "requested_at" DESC;


ALTER VIEW "public"."v_label_jobs_recent" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."vw_bruker_mounts_enriched" AS
 SELECT ((('BRUKER '::"text" || "to_char"(("mount_date")::timestamp with time zone, 'YYYY-MM-DD'::"text")) || ' #'::"text") || "row_number"() OVER (PARTITION BY "mount_date" ORDER BY "mount_time", "created_at")) AS "mount_code",
    "selection_id",
    "mount_date",
    "mount_time",
    "n_top",
    "n_bottom",
    "orientation",
    "created_at",
    "created_by"
   FROM "public"."bruker_mounts";


ALTER VIEW "public"."vw_bruker_mounts_enriched" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."vw_clutches_concept_overview" AS
 WITH "base" AS (
         SELECT "cp"."id_uuid" AS "clutch_plan_id",
            "pc"."id_uuid" AS "planned_cross_id",
            "cp"."clutch_code",
            "cp"."planned_name" AS "clutch_name",
            "cp"."planned_nickname" AS "clutch_nickname",
            "pc"."cross_date" AS "date_planned",
            COALESCE("cp"."note", "pc"."note") AS "note",
            "cp"."created_by",
            "cp"."created_at"
           FROM ("public"."clutch_plans" "cp"
             LEFT JOIN "public"."planned_crosses" "pc" ON (("pc"."clutch_id" = "cp"."id_uuid")))
        ), "inst" AS (
         SELECT "c"."planned_cross_id",
            ("count"(*))::integer AS "n_instances",
            "max"("c"."date_birth") AS "latest_date_birth",
            ("count"("c"."cross_id"))::integer AS "n_crosses"
           FROM "public"."clutches" "c"
          GROUP BY "c"."planned_cross_id"
        ), "cont" AS (
         SELECT "c"."planned_cross_id",
            ("count"("cc".*))::integer AS "n_containers"
           FROM ("public"."clutches" "c"
             JOIN "public"."clutch_containers" "cc" ON (("cc"."clutch_id" = "c"."id_uuid")))
          GROUP BY "c"."planned_cross_id"
        )
 SELECT "b"."clutch_plan_id",
    "b"."planned_cross_id",
    "b"."clutch_code",
    "b"."clutch_name",
    "b"."clutch_nickname",
    "b"."date_planned",
    "b"."created_by",
    "b"."created_at",
    "b"."note",
    COALESCE("i"."n_instances", 0) AS "n_instances",
    COALESCE(COALESCE("i"."n_crosses", 0), 0) AS "n_crosses",
    COALESCE("ct"."n_containers", 0) AS "n_containers",
    "i"."latest_date_birth"
   FROM (("base" "b"
     LEFT JOIN "inst" "i" ON (("i"."planned_cross_id" = "b"."planned_cross_id")))
     LEFT JOIN "cont" "ct" ON (("ct"."planned_cross_id" = "b"."planned_cross_id")))
  ORDER BY COALESCE((("b"."date_planned")::timestamp without time zone)::timestamp with time zone, "b"."created_at") DESC NULLS LAST;


ALTER VIEW "public"."vw_clutches_concept_overview" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."vw_clutches_overview_human" AS
 WITH "base" AS (
         SELECT "c"."id_uuid" AS "clutch_id",
            "c"."date_birth",
            "c"."created_by",
            "c"."created_at",
            "c"."note",
            "c"."batch_label",
            "c"."seed_batch_id",
            "c"."planned_cross_id",
            "cp"."clutch_code",
            "cp"."planned_name" AS "clutch_name",
            COALESCE("mt"."label", "mt"."tank_code") AS "mom_tank_label",
            COALESCE("ft"."label", "ft"."tank_code") AS "dad_tank_label",
            "c"."cross_id"
           FROM (((("public"."clutches" "c"
             LEFT JOIN "public"."planned_crosses" "pc" ON (("pc"."id_uuid" = "c"."planned_cross_id")))
             LEFT JOIN "public"."clutch_plans" "cp" ON (("cp"."id_uuid" = "pc"."clutch_id")))
             LEFT JOIN "public"."containers" "mt" ON (("mt"."id_uuid" = "pc"."mother_tank_id")))
             LEFT JOIN "public"."containers" "ft" ON (("ft"."id_uuid" = "pc"."father_tank_id")))
        ), "instances" AS (
         SELECT "cc"."clutch_id",
            ("count"(*))::integer AS "n_instances"
           FROM "public"."clutch_containers" "cc"
          GROUP BY "cc"."clutch_id"
        ), "crosses_via_clutches" AS (
         SELECT "b_1"."clutch_id",
            ("count"("x"."id_uuid"))::integer AS "n_crosses"
           FROM ("base" "b_1"
             LEFT JOIN "public"."crosses" "x" ON (("x"."id_uuid" = "b_1"."cross_id")))
          GROUP BY "b_1"."clutch_id"
        )
 SELECT "b"."clutch_id",
    "b"."date_birth",
    "b"."created_by",
    "b"."created_at",
    "b"."note",
    "b"."batch_label",
    "b"."seed_batch_id",
    "b"."clutch_code",
    "b"."clutch_name",
    NULL::"text" AS "clutch_nickname",
    "b"."mom_tank_label",
    "b"."dad_tank_label",
    COALESCE("i"."n_instances", 0) AS "n_instances",
    COALESCE("cx"."n_crosses", 0) AS "n_crosses"
   FROM (("base" "b"
     LEFT JOIN "instances" "i" ON (("i"."clutch_id" = "b"."clutch_id")))
     LEFT JOIN "crosses_via_clutches" "cx" ON (("cx"."clutch_id" = "b"."clutch_id")))
  ORDER BY COALESCE((("b"."date_birth")::timestamp without time zone)::timestamp with time zone, "b"."created_at") DESC NULLS LAST;


ALTER VIEW "public"."vw_clutches_overview_human" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."vw_crosses_concept" AS
 WITH "runs" AS (
         SELECT "cross_instances"."cross_id",
            ("count"(*))::integer AS "n_runs",
            "max"("cross_instances"."cross_date") AS "latest_cross_date"
           FROM "public"."cross_instances"
          GROUP BY "cross_instances"."cross_id"
        ), "cl" AS (
         SELECT "clutches"."cross_id",
            ("count"(*))::integer AS "n_clutches"
           FROM "public"."clutches"
          GROUP BY "clutches"."cross_id"
        ), "cnt" AS (
         SELECT "c"."cross_id",
            ("count"("cc".*))::integer AS "n_containers"
           FROM ("public"."clutches" "c"
             JOIN "public"."clutch_containers" "cc" ON (("cc"."clutch_id" = "c"."id_uuid")))
          GROUP BY "c"."cross_id"
        )
 SELECT "x"."id_uuid" AS "cross_id",
    COALESCE("x"."cross_code", ("x"."id_uuid")::"text") AS "cross_code",
    "x"."mother_code" AS "mom_code",
    "x"."father_code" AS "dad_code",
    "x"."created_by",
    "x"."created_at",
    COALESCE("runs"."n_runs", 0) AS "n_runs",
    "runs"."latest_cross_date",
    COALESCE("cl"."n_clutches", 0) AS "n_clutches",
    COALESCE("cnt"."n_containers", 0) AS "n_containers"
   FROM ((("public"."crosses" "x"
     LEFT JOIN "runs" ON (("runs"."cross_id" = "x"."id_uuid")))
     LEFT JOIN "cl" ON (("cl"."cross_id" = "x"."id_uuid")))
     LEFT JOIN "cnt" ON (("cnt"."cross_id" = "x"."id_uuid")))
  ORDER BY "x"."created_at" DESC;


ALTER VIEW "public"."vw_crosses_concept" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."vw_fish_standard" AS
 WITH "base" AS (
         SELECT "f"."id" AS "id_uuid",
            "f"."fish_code",
            COALESCE("f"."name", ''::"text") AS "name",
            COALESCE("f"."nickname", ''::"text") AS "nickname",
            "f"."date_birth",
            "f"."created_at",
            COALESCE("f"."created_by", ''::"text") AS "created_by_raw"
           FROM "public"."fish" "f"
        ), "label" AS (
         SELECT "v"."fish_code",
            "v"."genotype_print" AS "genotype",
            COALESCE("v"."genetic_background_print", "v"."genetic_background") AS "genetic_background",
            COALESCE("v"."line_building_stage", "v"."line_building_stage_print") AS "stage",
            "v"."batch_label",
            "v"."seed_batch_id",
            "v"."transgene_base_code_filled" AS "transgene_base_code",
            "v"."allele_code_filled" AS "allele_code",
            "v"."created_by_enriched",
            NULLIF("v"."plasmid_injections_text", ''::"text") AS "plasmid_injections_text",
            NULLIF("v"."rna_injections_text", ''::"text") AS "rna_injections_text"
           FROM "public"."vw_fish_overview_with_label" "v"
        ), "tank_counts" AS (
         SELECT "m"."fish_id",
            ("count"(*))::integer AS "n_living_tanks"
           FROM ("public"."fish_tank_memberships" "m"
             JOIN "public"."containers" "c" ON (("c"."id_uuid" = "m"."container_id")))
          WHERE (("m"."left_at" IS NULL) AND ("c"."container_type" = 'inventory_tank'::"text") AND ("c"."deactivated_at" IS NULL) AND (COALESCE("c"."status", ''::"text") = ANY (ARRAY['active'::"text", 'planned'::"text"])))
          GROUP BY "m"."fish_id"
        ), "roll" AS (
         SELECT "l_1"."fish_code",
            TRIM(BOTH '; '::"text" FROM "concat_ws"('; '::"text",
                CASE
                    WHEN ("l_1"."plasmid_injections_text" IS NOT NULL) THEN ('plasmid: '::"text" || "l_1"."plasmid_injections_text")
                    ELSE NULL::"text"
                END,
                CASE
                    WHEN ("l_1"."rna_injections_text" IS NOT NULL) THEN ('RNA: '::"text" || "l_1"."rna_injections_text")
                    ELSE NULL::"text"
                END)) AS "treatments_rollup"
           FROM "label" "l_1"
        )
 SELECT "b"."id_uuid",
    "b"."fish_code",
    "b"."name",
    "b"."nickname",
    "l"."genotype",
    "l"."genetic_background",
    "l"."stage",
    "b"."date_birth",
    (CURRENT_DATE - "b"."date_birth") AS "age_days",
    "b"."created_at",
    COALESCE("l"."created_by_enriched", "b"."created_by_raw") AS "created_by",
    COALESCE("l"."batch_label", "l"."seed_batch_id") AS "batch_display",
    "l"."transgene_base_code",
    "l"."allele_code",
    "r"."treatments_rollup",
    COALESCE("t"."n_living_tanks", 0) AS "n_living_tanks"
   FROM ((("base" "b"
     LEFT JOIN "label" "l" USING ("fish_code"))
     LEFT JOIN "roll" "r" USING ("fish_code"))
     LEFT JOIN "tank_counts" "t" ON (("t"."fish_id" = "b"."id_uuid")));


ALTER VIEW "public"."vw_fish_standard" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."vw_label_rows" AS
 WITH "base" AS (
         SELECT "f"."id_uuid",
            "f"."fish_code",
            "f"."name",
            "f"."nickname",
            "f"."line_building_stage",
            "f"."date_birth",
            "f"."genetic_background",
            "f"."created_at"
           FROM "public"."fish" "f"
        ), "allele" AS (
         SELECT DISTINCT ON ("f2"."fish_code") "f2"."fish_code",
            "l"."transgene_base_code",
            "l"."allele_number",
            "ta"."allele_nickname"
           FROM (("public"."fish_transgene_alleles" "l"
             JOIN "public"."fish" "f2" ON (("f2"."id_uuid" = "l"."fish_id")))
             LEFT JOIN "public"."transgene_alleles" "ta" ON ((("ta"."transgene_base_code" = "l"."transgene_base_code") AND ("ta"."allele_number" = "l"."allele_number"))))
          ORDER BY "f2"."fish_code", "l"."transgene_base_code", "l"."allele_number"
        ), "batch" AS (
         SELECT DISTINCT ON ("f3"."fish_code") "f3"."fish_code",
            "m"."seed_batch_id"
           FROM ("public"."fish_seed_batches_map" "m"
             JOIN "public"."fish" "f3" ON (("f3"."id_uuid" = "m"."fish_id")))
          ORDER BY "f3"."fish_code", "m"."logged_at" DESC NULLS LAST, "m"."created_at" DESC NULLS LAST
        )
 SELECT "b"."id_uuid",
    "b"."created_at",
    "b"."fish_code",
    "b"."name",
    "a"."transgene_base_code" AS "transgene_base_code_filled",
    ("a"."allele_number")::"text" AS "allele_code_filled",
    "a"."allele_nickname" AS "allele_name_filled",
    "batch"."seed_batch_id" AS "batch_label",
    COALESCE("b"."nickname", ''::"text") AS "nickname_print",
    COALESCE("b"."genetic_background", ''::"text") AS "genetic_background_print",
    COALESCE("b"."line_building_stage", ''::"text") AS "line_building_stage_print",
    COALESCE("to_char"(("b"."date_birth")::timestamp with time zone, 'YYYY-MM-DD'::"text"), ''::"text") AS "date_birth_print",
        CASE
            WHEN ("a"."transgene_base_code" IS NULL) THEN ''::"text"
            WHEN ("a"."allele_number" IS NOT NULL) THEN (("a"."transgene_base_code" || '-'::"text") || ("a"."allele_number")::"text")
            WHEN ("a"."allele_nickname" IS NOT NULL) THEN (("a"."transgene_base_code" || ' '::"text") || "a"."allele_nickname")
            ELSE "a"."transgene_base_code"
        END AS "genotype_print"
   FROM (("base" "b"
     LEFT JOIN "allele" "a" USING ("fish_code"))
     LEFT JOIN "batch" USING ("fish_code"))
  ORDER BY "b"."fish_code";


ALTER VIEW "public"."vw_label_rows" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."vw_plasmids_overview" AS
 SELECT "p"."id_uuid",
    "p"."code",
    "p"."name",
    "p"."nickname",
    "p"."fluors",
    "p"."resistance",
    "p"."supports_invitro_rna",
    "p"."created_by",
    "p"."notes",
    "p"."created_at",
    "r"."id_uuid" AS "rna_id",
    "r"."code" AS "rna_code",
    "r"."name" AS "rna_name",
    "r"."source_plasmid_id"
   FROM ("public"."plasmids" "p"
     LEFT JOIN "public"."rnas" "r" ON (("r"."source_plasmid_id" = "p"."id_uuid")))
  ORDER BY "p"."code";


ALTER VIEW "public"."vw_plasmids_overview" OWNER TO "postgres";


ALTER TABLE ONLY "public"."fish_code_audit" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."fish_code_audit_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."allele_nicknames"
    ADD CONSTRAINT "allele_nicknames_pkey" PRIMARY KEY ("base_code", "allele_code");



ALTER TABLE ONLY "public"."bruker_mounts"
    ADD CONSTRAINT "bruker_mounts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."clutch_containers"
    ADD CONSTRAINT "clutch_containers_pkey" PRIMARY KEY ("container_id");



ALTER TABLE ONLY "public"."clutch_genotype_options"
    ADD CONSTRAINT "clutch_genotype_options_clutch_id_allele_code_transgene_bas_key" UNIQUE ("clutch_id", "allele_code", "transgene_base_code");



ALTER TABLE ONLY "public"."clutch_genotype_options"
    ADD CONSTRAINT "clutch_genotype_options_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."clutch_instances"
    ADD CONSTRAINT "clutch_instances_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."clutch_plan_treatments"
    ADD CONSTRAINT "clutch_plan_treatments_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."clutch_plans"
    ADD CONSTRAINT "clutch_plans_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."clutch_treatments"
    ADD CONSTRAINT "clutch_treatments_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."clutches"
    ADD CONSTRAINT "clutches_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."container_status_history"
    ADD CONSTRAINT "container_status_history_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."containers"
    ADD CONSTRAINT "containers_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."cross_instances"
    ADD CONSTRAINT "cross_instances_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."cross_plan_genotype_alleles"
    ADD CONSTRAINT "cross_plan_genotype_alleles_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."cross_plan_genotype_alleles"
    ADD CONSTRAINT "cross_plan_genotype_alleles_plan_id_transgene_base_code_all_key" UNIQUE ("plan_id", "transgene_base_code", "allele_number");



ALTER TABLE ONLY "public"."cross_plan_runs"
    ADD CONSTRAINT "cross_plan_runs_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."cross_plan_runs"
    ADD CONSTRAINT "cross_plan_runs_plan_id_seq_key" UNIQUE ("plan_id", "seq");



ALTER TABLE ONLY "public"."cross_plan_treatments"
    ADD CONSTRAINT "cross_plan_treatments_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."cross_plans"
    ADD CONSTRAINT "cross_plans_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."crosses"
    ADD CONSTRAINT "crosses_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."fish_code_audit"
    ADD CONSTRAINT "fish_code_audit_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."fish"
    ADD CONSTRAINT "fish_fish_code_key" UNIQUE ("fish_code");



ALTER TABLE ONLY "public"."fish"
    ADD CONSTRAINT "fish_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."fish_seed_batches_map"
    ADD CONSTRAINT "fish_seed_batches_map_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."fish_seed_batches"
    ADD CONSTRAINT "fish_seed_batches_pkey" PRIMARY KEY ("fish_id");



ALTER TABLE ONLY "public"."fish_tank_memberships"
    ADD CONSTRAINT "fish_tank_memberships_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."fish_transgene_alleles"
    ADD CONSTRAINT "fish_transgene_alleles_pkey" PRIMARY KEY ("fish_id", "transgene_base_code", "allele_number");



ALTER TABLE ONLY "public"."fish_year_counters"
    ADD CONSTRAINT "fish_year_counters_pkey" PRIMARY KEY ("year");



ALTER TABLE ONLY "public"."injected_plasmid_treatments"
    ADD CONSTRAINT "injected_plasmid_treatments_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."injected_rna_treatments"
    ADD CONSTRAINT "injected_rna_treatments_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."label_items"
    ADD CONSTRAINT "label_items_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."label_jobs"
    ADD CONSTRAINT "label_jobs_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."load_log_fish"
    ADD CONSTRAINT "load_log_fish_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."planned_crosses"
    ADD CONSTRAINT "planned_crosses_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."plasmid_registry"
    ADD CONSTRAINT "plasmid_registry_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."plasmid_registry"
    ADD CONSTRAINT "plasmid_registry_plasmid_code_key" UNIQUE ("plasmid_code");



ALTER TABLE ONLY "public"."plasmids"
    ADD CONSTRAINT "plasmids_code_key" UNIQUE ("code");



ALTER TABLE ONLY "public"."plasmids"
    ADD CONSTRAINT "plasmids_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."rna_registry"
    ADD CONSTRAINT "rna_registry_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."rna_registry"
    ADD CONSTRAINT "rna_registry_rna_code_key" UNIQUE ("rna_code");



ALTER TABLE ONLY "public"."rnas"
    ADD CONSTRAINT "rnas_code_key" UNIQUE ("code");



ALTER TABLE ONLY "public"."rnas"
    ADD CONSTRAINT "rnas_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."selection_labels"
    ADD CONSTRAINT "selection_labels_code_key" UNIQUE ("code");



ALTER TABLE ONLY "public"."selection_labels"
    ADD CONSTRAINT "selection_labels_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."tank_requests"
    ADD CONSTRAINT "tank_requests_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."tank_year_counters"
    ADD CONSTRAINT "tank_year_counters_pkey" PRIMARY KEY ("year");



ALTER TABLE ONLY "public"."transgene_allele_counters"
    ADD CONSTRAINT "transgene_allele_counters_pkey" PRIMARY KEY ("transgene_base_code");



ALTER TABLE ONLY "public"."transgene_allele_registry"
    ADD CONSTRAINT "transgene_allele_registry_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."transgene_allele_registry"
    ADD CONSTRAINT "transgene_allele_registry_transgene_base_code_allele_number_key" UNIQUE ("transgene_base_code", "allele_number");



ALTER TABLE ONLY "public"."transgene_alleles"
    ADD CONSTRAINT "transgene_alleles_pkey" PRIMARY KEY ("transgene_base_code", "allele_number");



ALTER TABLE ONLY "public"."transgenes"
    ADD CONSTRAINT "transgenes_pkey" PRIMARY KEY ("transgene_base_code");



ALTER TABLE ONLY "public"."crosses"
    ADD CONSTRAINT "uq_cross_code" UNIQUE ("cross_code");



ALTER TABLE ONLY "public"."cross_plans"
    ADD CONSTRAINT "uq_cross_plans_unique" UNIQUE ("plan_date", "tank_a_id", "tank_b_id");



ALTER TABLE ONLY "public"."fish"
    ADD CONSTRAINT "uq_fish_code" UNIQUE ("fish_code");



ALTER TABLE ONLY "public"."fish"
    ADD CONSTRAINT "uq_fish_fish_code" UNIQUE ("fish_code");



ALTER TABLE ONLY "public"."fish"
    ADD CONSTRAINT "uq_fish_id_uuid" UNIQUE ("id_uuid");



ALTER TABLE ONLY "public"."fish_seed_batches_map"
    ADD CONSTRAINT "uq_fsbm_natural" UNIQUE ("fish_id", "seed_batch_id");



ALTER TABLE ONLY "public"."load_log_fish"
    ADD CONSTRAINT "uq_load_log_fish_batch_row" UNIQUE ("seed_batch_id", "row_key");



ALTER TABLE ONLY "public"."transgene_allele_registry"
    ADD CONSTRAINT "uq_registry_legacy" UNIQUE ("base_code", "legacy_label");



ALTER TABLE ONLY "public"."transgene_allele_registry"
    ADD CONSTRAINT "uq_registry_modern" UNIQUE ("transgene_base_code", "allele_nickname");



ALTER TABLE ONLY "public"."containers"
    ADD CONSTRAINT "uq_tank_code" UNIQUE ("tank_code");



CREATE INDEX "idx_cc_clutch" ON "public"."clutch_containers" USING "btree" ("clutch_id");



CREATE INDEX "idx_cc_clutch_id" ON "public"."clutch_containers" USING "btree" ("clutch_id");



CREATE INDEX "idx_cc_created_desc" ON "public"."clutch_containers" USING "btree" ("created_at" DESC);



CREATE INDEX "idx_cc_selection" ON "public"."clutch_containers" USING "btree" ("selection_label");



CREATE INDEX "idx_cgo_clutch" ON "public"."clutch_genotype_options" USING "btree" ("clutch_id");



CREATE INDEX "idx_clutch_containers_container_id" ON "public"."clutch_containers" USING "btree" ("container_id");



CREATE INDEX "idx_clutch_containers_source_container_id" ON "public"."clutch_containers" USING "btree" ("source_container_id");



CREATE INDEX "idx_clutch_plan_treatments_clutch_id" ON "public"."clutch_plan_treatments" USING "btree" ("clutch_id");



CREATE INDEX "idx_clutches_batch" ON "public"."clutches" USING "btree" ("batch_label");



CREATE INDEX "idx_clutches_created_desc" ON "public"."clutches" USING "btree" ("created_at" DESC);



CREATE INDEX "idx_clutches_cross_id" ON "public"."clutches" USING "btree" ("cross_id");



CREATE INDEX "idx_clutches_cross_instance_id" ON "public"."clutches" USING "btree" ("cross_instance_id");



CREATE INDEX "idx_clutches_planned_cross_id" ON "public"."clutches" USING "btree" ("planned_cross_id");



CREATE INDEX "idx_clutches_run_id" ON "public"."clutches" USING "btree" ("run_id");



CREATE INDEX "idx_clutches_seed" ON "public"."clutches" USING "btree" ("seed_batch_id");



CREATE INDEX "idx_containers_created_desc" ON "public"."containers" USING "btree" ("created_at" DESC);



CREATE INDEX "idx_containers_request_id" ON "public"."containers" USING "btree" ("request_id");



CREATE INDEX "idx_containers_type_status" ON "public"."containers" USING "btree" ("container_type", "status");



CREATE INDEX "idx_cp_father_fish_id" ON "public"."cross_plans" USING "btree" ("father_fish_id");



CREATE INDEX "idx_cp_mother_fish_id" ON "public"."cross_plans" USING "btree" ("mother_fish_id");



CREATE INDEX "idx_cp_tank_a_id" ON "public"."cross_plans" USING "btree" ("tank_a_id");



CREATE INDEX "idx_cp_tank_b_id" ON "public"."cross_plans" USING "btree" ("tank_b_id");



CREATE INDEX "idx_cpga_plan" ON "public"."cross_plan_genotype_alleles" USING "btree" ("plan_id");



CREATE INDEX "idx_cpr_plan_id" ON "public"."cross_plan_runs" USING "btree" ("plan_id");



CREATE INDEX "idx_cpr_tank_a_id" ON "public"."cross_plan_runs" USING "btree" ("tank_a_id");



CREATE INDEX "idx_cpr_tank_b_id" ON "public"."cross_plan_runs" USING "btree" ("tank_b_id");



CREATE INDEX "idx_cpt_plan" ON "public"."cross_plan_treatments" USING "btree" ("plan_id");



CREATE INDEX "idx_cpt_plan_id" ON "public"."cross_plan_treatments" USING "btree" ("plan_id");



CREATE INDEX "idx_cpt_plasmid" ON "public"."cross_plan_treatments" USING "btree" ("plasmid_id");



CREATE INDEX "idx_cpt_plasmid_id" ON "public"."cross_plan_treatments" USING "btree" ("plasmid_id");



CREATE INDEX "idx_cpt_rna" ON "public"."cross_plan_treatments" USING "btree" ("rna_id");



CREATE INDEX "idx_cpt_rna_id" ON "public"."cross_plan_treatments" USING "btree" ("rna_id");



CREATE INDEX "idx_cross_instances_cross_id" ON "public"."cross_instances" USING "btree" ("cross_id");



CREATE INDEX "idx_cross_instances_father_tank_id" ON "public"."cross_instances" USING "btree" ("father_tank_id");



CREATE INDEX "idx_cross_instances_mother_tank_id" ON "public"."cross_instances" USING "btree" ("mother_tank_id");



CREATE INDEX "idx_cross_plan_genotype_alleles_base_allele" ON "public"."cross_plan_genotype_alleles" USING "btree" ("transgene_base_code", "allele_number");



CREATE INDEX "idx_cross_plan_runs_date" ON "public"."cross_plan_runs" USING "btree" ("planned_date");



CREATE INDEX "idx_cross_plan_runs_plan" ON "public"."cross_plan_runs" USING "btree" ("plan_id");



CREATE INDEX "idx_cross_plan_runs_tank_a_id" ON "public"."cross_plan_runs" USING "btree" ("tank_a_id");



CREATE INDEX "idx_cross_plan_runs_tank_b_id" ON "public"."cross_plan_runs" USING "btree" ("tank_b_id");



CREATE INDEX "idx_cross_plans_created_by" ON "public"."cross_plans" USING "btree" ("created_by");



CREATE INDEX "idx_cross_plans_day_father" ON "public"."cross_plans" USING "btree" ("plan_date", "father_fish_id");



CREATE INDEX "idx_cross_plans_day_mother" ON "public"."cross_plans" USING "btree" ("plan_date", "mother_fish_id");



CREATE INDEX "idx_cross_plans_father" ON "public"."cross_plans" USING "btree" ("father_fish_id");



CREATE INDEX "idx_cross_plans_mother" ON "public"."cross_plans" USING "btree" ("mother_fish_id");



CREATE INDEX "idx_cross_plans_nick" ON "public"."cross_plans" USING "btree" ("plan_nickname");



CREATE INDEX "idx_cross_plans_plan_date" ON "public"."cross_plans" USING "btree" ("plan_date");



CREATE INDEX "idx_cross_plans_tank_a" ON "public"."cross_plans" USING "btree" ("tank_a_id");



CREATE INDEX "idx_cross_plans_tank_b" ON "public"."cross_plans" USING "btree" ("tank_b_id");



CREATE INDEX "idx_cross_plans_title" ON "public"."cross_plans" USING "btree" ("plan_title");



CREATE INDEX "idx_crosses_created_desc" ON "public"."crosses" USING "btree" ("created_at" DESC);



CREATE INDEX "idx_crosses_parents_code" ON "public"."crosses" USING "btree" ("mother_code", "father_code");



CREATE INDEX "idx_csh_changed_at" ON "public"."container_status_history" USING "btree" ("changed_at");



CREATE INDEX "idx_csh_container" ON "public"."container_status_history" USING "btree" ("container_id");



CREATE INDEX "idx_ct_clutch" ON "public"."clutch_treatments" USING "btree" ("clutch_id");



CREATE INDEX "idx_fish_seed_batches_fish_id" ON "public"."fish_seed_batches" USING "btree" ("fish_id");



CREATE INDEX "idx_fish_transgene_alleles_base_allele" ON "public"."fish_transgene_alleles" USING "btree" ("transgene_base_code", "allele_number");



CREATE INDEX "idx_fish_transgene_alles_base_allele" ON "public"."fish_transgene_alleles" USING "btree" ("transgene_base_code", "allele_number");



CREATE INDEX "idx_fsbm_fish_id" ON "public"."fish_seed_batches_map" USING "btree" ("fish_id");



CREATE INDEX "idx_fsbm_logged_at" ON "public"."fish_seed_batches_map" USING "btree" ("logged_at" DESC);



CREATE INDEX "idx_fsbm_seed_batch_id" ON "public"."fish_seed_batches_map" USING "btree" ("seed_batch_id");



CREATE INDEX "idx_fta_base_allele" ON "public"."fish_transgene_alleles" USING "btree" ("transgene_base_code", "allele_number");



CREATE INDEX "idx_fta_fish_id" ON "public"."fish_transgene_alleles" USING "btree" ("fish_id");



CREATE INDEX "idx_ftm_container" ON "public"."fish_tank_memberships" USING "btree" ("container_id");



CREATE INDEX "idx_ftm_container_id" ON "public"."fish_tank_memberships" USING "btree" ("container_id");



CREATE INDEX "idx_ftm_fish" ON "public"."fish_tank_memberships" USING "btree" ("fish_id");



CREATE INDEX "idx_ftm_fish_id" ON "public"."fish_tank_memberships" USING "btree" ("fish_id");



CREATE INDEX "idx_ipt_fish_id" ON "public"."injected_plasmid_treatments" USING "btree" ("fish_id");



CREATE INDEX "idx_irt_fish_id" ON "public"."injected_rna_treatments" USING "btree" ("fish_id");



CREATE INDEX "idx_label_items_job_seq" ON "public"."label_items" USING "btree" ("job_id", "seq");



CREATE INDEX "idx_label_items_request" ON "public"."label_items" USING "btree" ("request_id");



CREATE INDEX "idx_label_items_tank" ON "public"."label_items" USING "btree" ("tank_id");



CREATE INDEX "idx_label_jobs_entity" ON "public"."label_jobs" USING "btree" ("entity_type", "entity_id");



CREATE INDEX "idx_label_jobs_requested_by" ON "public"."label_jobs" USING "btree" ("requested_by", "requested_at" DESC);



CREATE INDEX "idx_label_jobs_status" ON "public"."label_jobs" USING "btree" ("status", "requested_at" DESC);



CREATE INDEX "idx_li_job_id" ON "public"."label_items" USING "btree" ("job_id");



CREATE INDEX "idx_li_request_id" ON "public"."label_items" USING "btree" ("request_id");



CREATE INDEX "idx_li_tank_id" ON "public"."label_items" USING "btree" ("tank_id");



CREATE INDEX "idx_load_log_fish_fish_id" ON "public"."load_log_fish" USING "btree" ("fish_id");



CREATE INDEX "idx_pc_clutch_id" ON "public"."planned_crosses" USING "btree" ("clutch_id");



CREATE INDEX "idx_pc_cross_id" ON "public"."planned_crosses" USING "btree" ("cross_id");



CREATE INDEX "idx_pc_cross_instance_id" ON "public"."planned_crosses" USING "btree" ("cross_instance_id");



CREATE INDEX "idx_pc_father_tank_id" ON "public"."planned_crosses" USING "btree" ("father_tank_id");



CREATE INDEX "idx_pc_mother_tank_id" ON "public"."planned_crosses" USING "btree" ("mother_tank_id");



CREATE INDEX "idx_planned_crosses_clutch" ON "public"."planned_crosses" USING "btree" ("clutch_id");



CREATE INDEX "idx_planned_crosses_cross_id" ON "public"."planned_crosses" USING "btree" ("cross_id");



CREATE INDEX "idx_planned_crosses_cross_instance_id" ON "public"."planned_crosses" USING "btree" ("cross_instance_id");



CREATE INDEX "idx_planned_crosses_father_tank_id" ON "public"."planned_crosses" USING "btree" ("father_tank_id");



CREATE INDEX "idx_planned_crosses_mother_tank_id" ON "public"."planned_crosses" USING "btree" ("mother_tank_id");



CREATE INDEX "idx_plasmid_registry_code" ON "public"."plasmid_registry" USING "btree" ("plasmid_code");



CREATE INDEX "idx_rna_registry_code" ON "public"."rna_registry" USING "btree" ("rna_code");



CREATE INDEX "idx_rnas_source_plasmid" ON "public"."rnas" USING "btree" ("source_plasmid_id");



CREATE INDEX "idx_ta_base_nick_ci" ON "public"."transgene_alleles" USING "btree" ("transgene_base_code", "lower"("allele_nickname"));



CREATE INDEX "idx_tank_requests_fish_id" ON "public"."tank_requests" USING "btree" ("fish_id");



CREATE INDEX "idx_vfltc_fish" ON "public"."fish_tank_memberships" USING "btree" ("fish_id");



CREATE INDEX "idx_xi_cross_id" ON "public"."cross_instances" USING "btree" ("cross_id");



CREATE INDEX "idx_xi_father_tank_id" ON "public"."cross_instances" USING "btree" ("father_tank_id");



CREATE INDEX "idx_xi_mother_tank_id" ON "public"."cross_instances" USING "btree" ("mother_tank_id");



CREATE INDEX "ix_bm_mount_date" ON "public"."bruker_mounts" USING "btree" ("mount_date");



CREATE INDEX "ix_bm_selection_id" ON "public"."bruker_mounts" USING "btree" ("selection_id");



CREATE INDEX "ix_bm_selection_id_uuid" ON "public"."bruker_mounts" USING "btree" ("selection_id_uuid");



CREATE INDEX "ix_bruker_mounts_selection_date" ON "public"."bruker_mounts" USING "btree" ("selection_id", "mount_date");



CREATE INDEX "ix_ci_created_at" ON "public"."clutch_instances" USING "btree" ("created_at");



CREATE INDEX "ix_ci_cross_instance_id" ON "public"."clutch_instances" USING "btree" ("cross_instance_id");



CREATE INDEX "ix_clutch_instances_annotated_at" ON "public"."clutch_instances" USING "btree" ("annotated_at");



CREATE INDEX "ix_clutch_instances_created_at" ON "public"."clutch_instances" USING "btree" ("created_at");



CREATE INDEX "ix_cross_instances_cross_id" ON "public"."cross_instances" USING "btree" ("cross_id");



CREATE INDEX "ix_cross_instances_father_id" ON "public"."cross_instances" USING "btree" ("father_tank_id");



CREATE INDEX "ix_cross_instances_mother_id" ON "public"."cross_instances" USING "btree" ("mother_tank_id");



CREATE INDEX "ix_ftm_container" ON "public"."fish_tank_memberships" USING "btree" ("container_id");



CREATE INDEX "ix_ftm_fish" ON "public"."fish_tank_memberships" USING "btree" ("fish_id");



CREATE INDEX "ix_ftm_left_null" ON "public"."fish_tank_memberships" USING "btree" ("left_at");



CREATE INDEX "ix_injected_rna_treatments_rna" ON "public"."injected_rna_treatments" USING "btree" ("rna_id");



CREATE INDEX "ix_registry_base_code" ON "public"."transgene_allele_registry" USING "btree" ("base_code");



CREATE UNIQUE INDEX "uniq_registry_base_legacy" ON "public"."transgene_allele_registry" USING "btree" ("base_code", "legacy_label") WHERE (("base_code" IS NOT NULL) AND ("legacy_label" IS NOT NULL));



CREATE UNIQUE INDEX "uniq_registry_modern_key" ON "public"."transgene_allele_registry" USING "btree" ("transgene_base_code", "allele_nickname") WHERE (("transgene_base_code" IS NOT NULL) AND ("allele_nickname" IS NOT NULL));



CREATE UNIQUE INDEX "uq_clutch_instances_id_uuid" ON "public"."clutch_instances" USING "btree" ("id_uuid");



CREATE UNIQUE INDEX "uq_clutch_plans_clutch_code" ON "public"."clutch_plans" USING "btree" ("clutch_code");



CREATE UNIQUE INDEX "uq_clutches_instance_code" ON "public"."clutches" USING "btree" ("clutch_instance_code") WHERE ("clutch_instance_code" IS NOT NULL);



CREATE UNIQUE INDEX "uq_clutches_planned_by_date" ON "public"."clutches" USING "btree" ("planned_cross_id", "date_birth");



CREATE UNIQUE INDEX "uq_containers_tank_code" ON "public"."containers" USING "btree" ("tank_code") WHERE ("tank_code" IS NOT NULL);



CREATE UNIQUE INDEX "uq_crosses_concept_pair" ON "public"."crosses" USING "btree" ("upper"(TRIM(BOTH FROM "mother_code")), "upper"(TRIM(BOTH FROM "father_code")));



CREATE UNIQUE INDEX "uq_crosses_cross_code" ON "public"."crosses" USING "btree" ("cross_code") WHERE ("cross_code" IS NOT NULL);



CREATE UNIQUE INDEX "uq_fsbm_batch_fish" ON "public"."fish_seed_batches_map" USING "btree" ("seed_batch_id", "fish_id");



CREATE UNIQUE INDEX "uq_fta_fish_base" ON "public"."fish_transgene_alleles" USING "btree" ("fish_id", "transgene_base_code");



CREATE UNIQUE INDEX "uq_ftm_fish_open" ON "public"."fish_tank_memberships" USING "btree" ("fish_id") WHERE ("left_at" IS NULL);



CREATE UNIQUE INDEX "uq_ipt_natural" ON "public"."injected_plasmid_treatments" USING "btree" ("fish_id", "plasmid_id", "at_time", "amount", "units", "note");



CREATE UNIQUE INDEX "uq_irt_natural" ON "public"."injected_rna_treatments" USING "btree" ("fish_id", "rna_id", "at_time", "amount", "units", "note");



CREATE UNIQUE INDEX "uq_label_jobs_dedupe" ON "public"."label_jobs" USING "btree" ("dedupe_hash") WHERE ("dedupe_hash" IS NOT NULL);



CREATE UNIQUE INDEX "uq_planned_crosses_clutch_parents_canonical" ON "public"."planned_crosses" USING "btree" ("clutch_id", "mother_tank_id", "father_tank_id") WHERE (("is_canonical" = true) AND ("mother_tank_id" IS NOT NULL) AND ("father_tank_id" IS NOT NULL));



CREATE UNIQUE INDEX "uq_planned_crosses_cross_code" ON "public"."planned_crosses" USING "btree" ("cross_code") WHERE ("cross_code" IS NOT NULL);



CREATE UNIQUE INDEX "uq_plasmids_code" ON "public"."plasmids" USING "btree" ("code");



CREATE UNIQUE INDEX "uq_rna_txn_dedupe" ON "public"."injected_rna_treatments" USING "btree" ("fish_id", "rna_id", COALESCE("at_time", '1970-01-01 00:00:00+00'::timestamp with time zone), COALESCE("amount", (0)::numeric), COALESCE("units", ''::"text"), COALESCE("note", ''::"text"));



CREATE UNIQUE INDEX "uq_rnas_one_per_plasmid" ON "public"."rnas" USING "btree" ("source_plasmid_id") WHERE ("source_plasmid_id" IS NOT NULL);



CREATE UNIQUE INDEX "uq_tar_base_number" ON "public"."transgene_allele_registry" USING "btree" ("transgene_base_code", "allele_number");



CREATE UNIQUE INDEX "ux_planned_crosses_cross_code" ON "public"."planned_crosses" USING "btree" ("cross_code");



CREATE OR REPLACE TRIGGER "bi_set_fish_code" BEFORE INSERT ON "public"."fish" FOR EACH ROW EXECUTE FUNCTION "public"."fish_bi_set_fish_code"();



CREATE OR REPLACE TRIGGER "trg_audit_del" AFTER DELETE ON "public"."containers" FOR EACH ROW EXECUTE FUNCTION "audit"."fn_writes"();



CREATE OR REPLACE TRIGGER "trg_audit_del" AFTER DELETE ON "public"."fish" FOR EACH ROW EXECUTE FUNCTION "audit"."fn_writes"();



CREATE OR REPLACE TRIGGER "trg_audit_del" AFTER DELETE ON "public"."fish_tank_memberships" FOR EACH ROW EXECUTE FUNCTION "audit"."fn_writes"();



CREATE OR REPLACE TRIGGER "trg_audit_del" AFTER DELETE ON "public"."fish_transgene_alleles" FOR EACH ROW EXECUTE FUNCTION "audit"."fn_writes"();



CREATE OR REPLACE TRIGGER "trg_audit_del" AFTER DELETE ON "public"."transgene_alleles" FOR EACH ROW EXECUTE FUNCTION "audit"."fn_writes"();



CREATE OR REPLACE TRIGGER "trg_audit_ins" AFTER INSERT ON "public"."containers" FOR EACH ROW EXECUTE FUNCTION "audit"."fn_writes"();



CREATE OR REPLACE TRIGGER "trg_audit_ins" AFTER INSERT ON "public"."fish" FOR EACH ROW EXECUTE FUNCTION "audit"."fn_writes"();



CREATE OR REPLACE TRIGGER "trg_audit_ins" AFTER INSERT ON "public"."fish_tank_memberships" FOR EACH ROW EXECUTE FUNCTION "audit"."fn_writes"();



CREATE OR REPLACE TRIGGER "trg_audit_ins" AFTER INSERT ON "public"."fish_transgene_alleles" FOR EACH ROW EXECUTE FUNCTION "audit"."fn_writes"();



CREATE OR REPLACE TRIGGER "trg_audit_ins" AFTER INSERT ON "public"."transgene_alleles" FOR EACH ROW EXECUTE FUNCTION "audit"."fn_writes"();



CREATE OR REPLACE TRIGGER "trg_audit_upd" AFTER UPDATE ON "public"."containers" FOR EACH ROW EXECUTE FUNCTION "audit"."fn_writes"();



CREATE OR REPLACE TRIGGER "trg_audit_upd" AFTER UPDATE ON "public"."fish" FOR EACH ROW EXECUTE FUNCTION "audit"."fn_writes"();



CREATE OR REPLACE TRIGGER "trg_audit_upd" AFTER UPDATE ON "public"."fish_tank_memberships" FOR EACH ROW EXECUTE FUNCTION "audit"."fn_writes"();



CREATE OR REPLACE TRIGGER "trg_audit_upd" AFTER UPDATE ON "public"."fish_transgene_alleles" FOR EACH ROW EXECUTE FUNCTION "audit"."fn_writes"();



CREATE OR REPLACE TRIGGER "trg_audit_upd" AFTER UPDATE ON "public"."transgene_alleles" FOR EACH ROW EXECUTE FUNCTION "audit"."fn_writes"();



CREATE OR REPLACE TRIGGER "trg_clutch_code" BEFORE INSERT ON "public"."clutch_plans" FOR EACH ROW EXECUTE FUNCTION "public"."trg_clutch_code"();



CREATE OR REPLACE TRIGGER "trg_clutch_instance_code" BEFORE INSERT ON "public"."clutches" FOR EACH ROW EXECUTE FUNCTION "public"."trg_clutch_instance_code"();



CREATE OR REPLACE TRIGGER "trg_containers_activate_on_label" BEFORE UPDATE OF "label" ON "public"."containers" FOR EACH ROW EXECUTE FUNCTION "public"."trg_containers_activate_on_label"();



CREATE OR REPLACE TRIGGER "trg_containers_status_history" AFTER UPDATE OF "status" ON "public"."containers" FOR EACH ROW EXECUTE FUNCTION "public"."trg_log_container_status"();



CREATE OR REPLACE TRIGGER "trg_cross_code" BEFORE INSERT ON "public"."crosses" FOR EACH ROW EXECUTE FUNCTION "public"."trg_cross_code"();



CREATE OR REPLACE TRIGGER "trg_cross_name_fill" BEFORE INSERT ON "public"."crosses" FOR EACH ROW EXECUTE FUNCTION "public"."trg_cross_name_fill"();



CREATE OR REPLACE TRIGGER "trg_cross_run_code" BEFORE INSERT ON "public"."cross_instances" FOR EACH ROW EXECUTE FUNCTION "public"."trg_cross_run_code"();



CREATE OR REPLACE TRIGGER "trg_fish_autotank" AFTER INSERT ON "public"."fish" FOR EACH ROW EXECUTE FUNCTION "public"."trg_fish_autotank"();



CREATE OR REPLACE TRIGGER "trg_fish_before_insert_code" BEFORE INSERT ON "public"."fish" FOR EACH ROW EXECUTE FUNCTION "public"."fish_before_insert_code"();



CREATE OR REPLACE TRIGGER "trg_plasmids_auto_ensure_rna" AFTER INSERT OR UPDATE OF "supports_invitro_rna", "code" ON "public"."plasmids" FOR EACH ROW EXECUTE FUNCTION "public"."trg_plasmid_auto_ensure_rna"();



CREATE OR REPLACE TRIGGER "trg_registry_fill_modern" BEFORE INSERT OR UPDATE ON "public"."transgene_allele_registry" FOR EACH ROW EXECUTE FUNCTION "public"."trg_registry_fill_modern"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."allele_nicknames" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."bruker_mounts" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."clutch_containers" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."clutch_genotype_options" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."clutch_instances" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."clutch_plan_treatments" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."clutch_plans" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."clutch_treatments" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."clutches" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."container_status_history" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."containers" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."cross_instances" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."cross_plan_genotype_alleles" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."cross_plan_runs" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."cross_plan_treatments" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."cross_plans" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."crosses" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."fish" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."fish_code_audit" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."fish_seed_batches" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."fish_seed_batches_map" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."fish_tank_memberships" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."fish_transgene_alleles" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."fish_year_counters" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."injected_plasmid_treatments" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."injected_rna_treatments" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."label_items" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."label_jobs" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."load_log_fish" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."planned_crosses" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."plasmid_registry" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."plasmids" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."rna_registry" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."rnas" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."selection_labels" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."tank_requests" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."tank_year_counters" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."transgene_allele_counters" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."transgene_allele_registry" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."transgene_alleles" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_set_updated_at" BEFORE UPDATE ON "public"."transgenes" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_updated_at"();



CREATE OR REPLACE TRIGGER "zz_bi_normalize_cross_code" BEFORE INSERT OR UPDATE ON "public"."crosses" FOR EACH ROW EXECUTE FUNCTION "public"."trg_cross_code_normalize"();



ALTER TABLE ONLY "public"."clutch_containers"
    ADD CONSTRAINT "clutch_containers_clutch_id_fkey" FOREIGN KEY ("clutch_id") REFERENCES "public"."clutches"("id_uuid") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."clutch_containers"
    ADD CONSTRAINT "clutch_containers_container_id_fkey" FOREIGN KEY ("container_id") REFERENCES "public"."containers"("id_uuid") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."clutch_containers"
    ADD CONSTRAINT "clutch_containers_source_container_id_fkey" FOREIGN KEY ("source_container_id") REFERENCES "public"."containers"("id_uuid") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."clutch_genotype_options"
    ADD CONSTRAINT "clutch_genotype_options_clutch_id_fkey" FOREIGN KEY ("clutch_id") REFERENCES "public"."clutches"("id_uuid") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."clutch_plan_treatments"
    ADD CONSTRAINT "clutch_plan_treatments_clutch_id_fkey" FOREIGN KEY ("clutch_id") REFERENCES "public"."clutch_plans"("id_uuid") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."clutch_treatments"
    ADD CONSTRAINT "clutch_treatments_clutch_id_fkey" FOREIGN KEY ("clutch_id") REFERENCES "public"."clutches"("id_uuid") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."clutches"
    ADD CONSTRAINT "clutches_cross_id_fkey" FOREIGN KEY ("cross_id") REFERENCES "public"."crosses"("id_uuid") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."clutches"
    ADD CONSTRAINT "clutches_cross_instance_id_fkey" FOREIGN KEY ("cross_instance_id") REFERENCES "public"."cross_instances"("id_uuid") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."clutches"
    ADD CONSTRAINT "clutches_planned_cross_id_fkey" FOREIGN KEY ("planned_cross_id") REFERENCES "public"."planned_crosses"("id_uuid");



ALTER TABLE ONLY "public"."clutches"
    ADD CONSTRAINT "clutches_run_id_fkey" FOREIGN KEY ("run_id") REFERENCES "public"."cross_plan_runs"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."container_status_history"
    ADD CONSTRAINT "container_status_history_container_id_fkey" FOREIGN KEY ("container_id") REFERENCES "public"."containers"("id_uuid") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."containers"
    ADD CONSTRAINT "containers_request_id_fkey" FOREIGN KEY ("request_id") REFERENCES "public"."tank_requests"("id_uuid") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."cross_instances"
    ADD CONSTRAINT "cross_instances_cross_id_fkey" FOREIGN KEY ("cross_id") REFERENCES "public"."crosses"("id_uuid") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."cross_instances"
    ADD CONSTRAINT "cross_instances_father_tank_id_fkey" FOREIGN KEY ("father_tank_id") REFERENCES "public"."containers"("id_uuid");



ALTER TABLE ONLY "public"."cross_instances"
    ADD CONSTRAINT "cross_instances_mother_tank_id_fkey" FOREIGN KEY ("mother_tank_id") REFERENCES "public"."containers"("id_uuid");



ALTER TABLE ONLY "public"."cross_plan_genotype_alleles"
    ADD CONSTRAINT "cross_plan_genotype_alleles_plan_id_fkey" FOREIGN KEY ("plan_id") REFERENCES "public"."cross_plans"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."cross_plan_runs"
    ADD CONSTRAINT "cross_plan_runs_plan_id_fkey" FOREIGN KEY ("plan_id") REFERENCES "public"."cross_plans"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."cross_plan_runs"
    ADD CONSTRAINT "cross_plan_runs_tank_a_id_fkey" FOREIGN KEY ("tank_a_id") REFERENCES "public"."containers"("id_uuid");



ALTER TABLE ONLY "public"."cross_plan_runs"
    ADD CONSTRAINT "cross_plan_runs_tank_b_id_fkey" FOREIGN KEY ("tank_b_id") REFERENCES "public"."containers"("id_uuid");



ALTER TABLE ONLY "public"."cross_plan_treatments"
    ADD CONSTRAINT "cross_plan_treatments_plan_id_fkey" FOREIGN KEY ("plan_id") REFERENCES "public"."cross_plans"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."cross_plan_treatments"
    ADD CONSTRAINT "cross_plan_treatments_plasmid_id_fkey" FOREIGN KEY ("plasmid_id") REFERENCES "public"."plasmid_registry"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."cross_plan_treatments"
    ADD CONSTRAINT "cross_plan_treatments_rna_id_fkey" FOREIGN KEY ("rna_id") REFERENCES "public"."rna_registry"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."cross_plans"
    ADD CONSTRAINT "cross_plans_father_fish_id_fkey" FOREIGN KEY ("father_fish_id") REFERENCES "public"."fish"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."cross_plans"
    ADD CONSTRAINT "cross_plans_mother_fish_id_fkey" FOREIGN KEY ("mother_fish_id") REFERENCES "public"."fish"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."fish_tank_memberships"
    ADD CONSTRAINT "fish_tank_memberships_container_id_fkey" FOREIGN KEY ("container_id") REFERENCES "public"."containers"("id_uuid") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."fish_tank_memberships"
    ADD CONSTRAINT "fish_tank_memberships_fish_id_fkey" FOREIGN KEY ("fish_id") REFERENCES "public"."fish"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."fish_transgene_alleles"
    ADD CONSTRAINT "fish_transgene_alleles_fish_id_fkey" FOREIGN KEY ("fish_id") REFERENCES "public"."fish"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."fish_transgene_alleles"
    ADD CONSTRAINT "fish_transgene_alleles_transgene_base_code_allele_number_fkey" FOREIGN KEY ("transgene_base_code", "allele_number") REFERENCES "public"."transgene_alleles"("transgene_base_code", "allele_number") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."bruker_mounts"
    ADD CONSTRAINT "fk_bm_selection_id" FOREIGN KEY ("selection_id_uuid") REFERENCES "public"."clutch_instances"("id_uuid") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."cross_instances"
    ADD CONSTRAINT "fk_ci_cross" FOREIGN KEY ("cross_id") REFERENCES "public"."crosses"("id_uuid");



ALTER TABLE ONLY "public"."cross_instances"
    ADD CONSTRAINT "fk_ci_father_container" FOREIGN KEY ("father_tank_id") REFERENCES "public"."containers"("id_uuid");



ALTER TABLE ONLY "public"."cross_instances"
    ADD CONSTRAINT "fk_ci_mother_container" FOREIGN KEY ("mother_tank_id") REFERENCES "public"."containers"("id_uuid");



ALTER TABLE ONLY "public"."clutch_instances"
    ADD CONSTRAINT "fk_ci_xrun" FOREIGN KEY ("cross_instance_id") REFERENCES "public"."cross_instances"("id_uuid") NOT VALID;



ALTER TABLE ONLY "public"."cross_plan_genotype_alleles"
    ADD CONSTRAINT "fk_cpga_transgene_allele" FOREIGN KEY ("transgene_base_code", "allele_number") REFERENCES "public"."transgene_alleles"("transgene_base_code", "allele_number") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."cross_plans"
    ADD CONSTRAINT "fk_cross_plans_tank_a_cont" FOREIGN KEY ("tank_a_id") REFERENCES "public"."containers"("id_uuid") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."cross_plans"
    ADD CONSTRAINT "fk_cross_plans_tank_b_cont" FOREIGN KEY ("tank_b_id") REFERENCES "public"."containers"("id_uuid") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."fish_seed_batches"
    ADD CONSTRAINT "fk_fsb_fish" FOREIGN KEY ("fish_id") REFERENCES "public"."fish"("id") ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;



ALTER TABLE ONLY "public"."fish_seed_batches_map"
    ADD CONSTRAINT "fk_fsbm_fish" FOREIGN KEY ("fish_id") REFERENCES "public"."fish"("id_uuid") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."injected_plasmid_treatments"
    ADD CONSTRAINT "fk_ipt_fish" FOREIGN KEY ("fish_id") REFERENCES "public"."fish"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."transgene_alleles"
    ADD CONSTRAINT "fk_transgene_alleles_base" FOREIGN KEY ("transgene_base_code") REFERENCES "public"."transgenes"("transgene_base_code") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."injected_plasmid_treatments"
    ADD CONSTRAINT "injected_plasmid_treatments_fish_id_fkey" FOREIGN KEY ("fish_id") REFERENCES "public"."fish"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."injected_rna_treatments"
    ADD CONSTRAINT "injected_rna_treatments_fish_id_fkey" FOREIGN KEY ("fish_id") REFERENCES "public"."fish"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."injected_rna_treatments"
    ADD CONSTRAINT "irt_fish_fk" FOREIGN KEY ("fish_id") REFERENCES "public"."fish"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."label_items"
    ADD CONSTRAINT "label_items_job_id_fkey" FOREIGN KEY ("job_id") REFERENCES "public"."label_jobs"("id_uuid") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."label_items"
    ADD CONSTRAINT "label_items_request_id_fkey" FOREIGN KEY ("request_id") REFERENCES "public"."tank_requests"("id_uuid") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."label_items"
    ADD CONSTRAINT "label_items_tank_id_fkey" FOREIGN KEY ("tank_id") REFERENCES "public"."containers"("id_uuid") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."load_log_fish"
    ADD CONSTRAINT "load_log_fish_fish_id_fkey" FOREIGN KEY ("fish_id") REFERENCES "public"."fish"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."planned_crosses"
    ADD CONSTRAINT "planned_crosses_clutch_id_fkey" FOREIGN KEY ("clutch_id") REFERENCES "public"."clutch_plans"("id_uuid") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."planned_crosses"
    ADD CONSTRAINT "planned_crosses_cross_id_fkey" FOREIGN KEY ("cross_id") REFERENCES "public"."crosses"("id_uuid") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."planned_crosses"
    ADD CONSTRAINT "planned_crosses_cross_instance_id_fkey" FOREIGN KEY ("cross_instance_id") REFERENCES "public"."cross_instances"("id_uuid") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."planned_crosses"
    ADD CONSTRAINT "planned_crosses_father_tank_id_fkey" FOREIGN KEY ("father_tank_id") REFERENCES "public"."containers"("id_uuid");



ALTER TABLE ONLY "public"."planned_crosses"
    ADD CONSTRAINT "planned_crosses_mother_tank_id_fkey" FOREIGN KEY ("mother_tank_id") REFERENCES "public"."containers"("id_uuid");



ALTER TABLE ONLY "public"."rnas"
    ADD CONSTRAINT "rnas_source_plasmid_id_fkey" FOREIGN KEY ("source_plasmid_id") REFERENCES "public"."plasmids"("id_uuid") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."tank_requests"
    ADD CONSTRAINT "tank_requests_fish_id_fkey" FOREIGN KEY ("fish_id") REFERENCES "public"."fish"("id_uuid") ON DELETE CASCADE;



ALTER TABLE "public"."allele_nicknames" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "allow_read_auth" ON "public"."allele_nicknames" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."bruker_mounts" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."clutch_containers" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."clutch_genotype_options" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."clutch_instances" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."clutch_plan_treatments" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."clutch_plans" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."clutch_treatments" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."clutches" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."container_status_history" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."containers" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."cross_instances" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."cross_plan_genotype_alleles" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."cross_plan_runs" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."cross_plan_treatments" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."cross_plans" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."crosses" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."fish" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."fish_code_audit" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."fish_seed_batches" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."fish_seed_batches_map" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."fish_tank_memberships" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."fish_transgene_alleles" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."fish_year_counters" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."injected_plasmid_treatments" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."injected_rna_treatments" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."label_items" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."label_jobs" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."load_log_fish" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."planned_crosses" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."plasmid_registry" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."plasmids" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."rna_registry" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."rnas" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."selection_labels" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."tank_requests" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."tank_year_counters" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."transgene_allele_counters" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."transgene_allele_registry" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."transgene_alleles" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "allow_read_auth" ON "public"."transgenes" FOR SELECT TO "authenticated" USING (true);



CREATE POLICY "app_rw_insert_bm" ON "public"."bruker_mounts" FOR INSERT TO "app_rw" WITH CHECK (true);



CREATE POLICY "app_rw_insert_ci" ON "public"."cross_instances" FOR INSERT TO "app_rw" WITH CHECK (true);



CREATE POLICY "app_rw_insert_ci_annot" ON "public"."clutch_instances" FOR INSERT TO "app_rw" WITH CHECK (true);



CREATE POLICY "app_rw_insert_fish" ON "public"."fish" FOR INSERT TO "app_rw" WITH CHECK (true);



CREATE POLICY "app_rw_insert_fta" ON "public"."fish_transgene_alleles" FOR INSERT TO "app_rw" WITH CHECK (true);



CREATE POLICY "app_rw_insert_planned_crosses" ON "public"."planned_crosses" FOR INSERT TO "app_rw" WITH CHECK (true);



CREATE POLICY "app_rw_insert_tga" ON "public"."transgene_alleles" FOR INSERT TO "app_rw" WITH CHECK (true);



CREATE POLICY "app_rw_select_bm" ON "public"."bruker_mounts" FOR SELECT TO "app_rw" USING (true);



CREATE POLICY "app_rw_select_ci" ON "public"."cross_instances" FOR SELECT TO "app_rw" USING (true);



CREATE POLICY "app_rw_select_ci_annot" ON "public"."clutch_instances" FOR SELECT TO "app_rw" USING (true);



CREATE POLICY "app_rw_select_fish" ON "public"."fish" FOR SELECT TO "app_rw" USING (true);



CREATE POLICY "app_rw_select_fta" ON "public"."fish_transgene_alleles" FOR SELECT TO "app_rw" USING (true);



CREATE POLICY "app_rw_select_planned_crosses" ON "public"."planned_crosses" FOR SELECT TO "app_rw" USING (true);



CREATE POLICY "app_rw_select_tga" ON "public"."transgene_alleles" FOR SELECT TO "app_rw" USING (true);



CREATE POLICY "app_rw_update_bm" ON "public"."bruker_mounts" FOR UPDATE TO "app_rw" USING (true) WITH CHECK (true);



CREATE POLICY "app_rw_update_ci" ON "public"."cross_instances" FOR UPDATE TO "app_rw" USING (true) WITH CHECK (true);



CREATE POLICY "app_rw_update_ci_annot" ON "public"."clutch_instances" FOR UPDATE TO "app_rw" USING (true) WITH CHECK (true);



CREATE POLICY "app_rw_update_fish" ON "public"."fish" FOR UPDATE TO "app_rw" USING (true) WITH CHECK (true);



CREATE POLICY "app_rw_update_fta" ON "public"."fish_transgene_alleles" FOR UPDATE TO "app_rw" USING (true) WITH CHECK (true);



CREATE POLICY "app_rw_update_planned_crosses" ON "public"."planned_crosses" FOR UPDATE TO "app_rw" USING (true) WITH CHECK (true);



CREATE POLICY "app_rw_update_tga" ON "public"."transgene_alleles" FOR UPDATE TO "app_rw" USING (true) WITH CHECK (true);



ALTER TABLE "public"."bruker_mounts" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."clutch_containers" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."clutch_genotype_options" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."clutch_instances" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."clutch_plan_treatments" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."clutch_plans" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."clutch_treatments" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."clutches" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."container_status_history" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."containers" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."cross_instances" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."cross_plan_genotype_alleles" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."cross_plan_runs" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."cross_plan_treatments" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."cross_plans" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."crosses" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."fish" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."fish_code_audit" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."fish_seed_batches" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."fish_seed_batches_map" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."fish_tank_memberships" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."fish_transgene_alleles" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."fish_year_counters" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."injected_plasmid_treatments" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."injected_rna_treatments" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."label_items" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."label_jobs" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."load_log_fish" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."planned_crosses" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."plasmid_registry" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."plasmids" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."rna_registry" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."rnas" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."selection_labels" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."tank_requests" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."tank_year_counters" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."transgene_allele_counters" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."transgene_allele_registry" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."transgene_alleles" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."transgenes" ENABLE ROW LEVEL SECURITY;


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";
GRANT USAGE ON SCHEMA "public" TO "app_rw";



GRANT ALL ON FUNCTION "public"."apply_plasmid_treatment"("p_fish_id" "uuid", "p_plasmid_id" "uuid", "p_amount" numeric, "p_units" "text", "p_at_time" timestamp with time zone, "p_note" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."apply_plasmid_treatment"("p_fish_id" "uuid", "p_plasmid_id" "uuid", "p_amount" numeric, "p_units" "text", "p_at_time" timestamp with time zone, "p_note" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."apply_plasmid_treatment"("p_fish_id" "uuid", "p_plasmid_id" "uuid", "p_amount" numeric, "p_units" "text", "p_at_time" timestamp with time zone, "p_note" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."apply_rna_treatment"("p_fish_id" "uuid", "p_rna_id" "uuid", "p_amount" numeric, "p_units" "text", "p_at_time" timestamp with time zone, "p_note" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."apply_rna_treatment"("p_fish_id" "uuid", "p_rna_id" "uuid", "p_amount" numeric, "p_units" "text", "p_at_time" timestamp with time zone, "p_note" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."apply_rna_treatment"("p_fish_id" "uuid", "p_rna_id" "uuid", "p_amount" numeric, "p_units" "text", "p_at_time" timestamp with time zone, "p_note" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."assign_fish_to_tank"("p_fish_id" "uuid", "p_container_id" "uuid", "p_by" "text", "p_note" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."assign_fish_to_tank"("p_fish_id" "uuid", "p_container_id" "uuid", "p_by" "text", "p_note" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."assign_fish_to_tank"("p_fish_id" "uuid", "p_container_id" "uuid", "p_by" "text", "p_note" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."create_label_job"("p_entity_type" "text", "p_entity_id" "uuid", "p_template" "text", "p_media" "text", "p_requested_by" "text", "p_cards" "jsonb", "p_dedupe_hash" "text", "p_replace" boolean) TO "anon";
GRANT ALL ON FUNCTION "public"."create_label_job"("p_entity_type" "text", "p_entity_id" "uuid", "p_template" "text", "p_media" "text", "p_requested_by" "text", "p_cards" "jsonb", "p_dedupe_hash" "text", "p_replace" boolean) TO "authenticated";
GRANT ALL ON FUNCTION "public"."create_label_job"("p_entity_type" "text", "p_entity_id" "uuid", "p_template" "text", "p_media" "text", "p_requested_by" "text", "p_cards" "jsonb", "p_dedupe_hash" "text", "p_replace" boolean) TO "service_role";



GRANT ALL ON FUNCTION "public"."create_offspring_batch"("p_mother_id" "uuid", "p_father_id" "uuid", "p_count" integer, "p_created_by" "text", "p_birth_date" "date", "p_name_prefix" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."create_offspring_batch"("p_mother_id" "uuid", "p_father_id" "uuid", "p_count" integer, "p_created_by" "text", "p_birth_date" "date", "p_name_prefix" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."create_offspring_batch"("p_mother_id" "uuid", "p_father_id" "uuid", "p_count" integer, "p_created_by" "text", "p_birth_date" "date", "p_name_prefix" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."ensure_inventory_tank"("p_label" "text", "p_by" "text", "p_status" "public"."container_status") TO "anon";
GRANT ALL ON FUNCTION "public"."ensure_inventory_tank"("p_label" "text", "p_by" "text", "p_status" "public"."container_status") TO "authenticated";
GRANT ALL ON FUNCTION "public"."ensure_inventory_tank"("p_label" "text", "p_by" "text", "p_status" "public"."container_status") TO "service_role";



GRANT ALL ON FUNCTION "public"."ensure_inventory_tank_text"("p_label" "text", "p_by" "text", "p_status" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."ensure_inventory_tank_text"("p_label" "text", "p_by" "text", "p_status" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."ensure_inventory_tank_text"("p_label" "text", "p_by" "text", "p_status" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."ensure_inventory_tank_v"("p_label" "text", "p_by" "text", "p_status" "public"."container_status", "p_volume_l" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."ensure_inventory_tank_v"("p_label" "text", "p_by" "text", "p_status" "public"."container_status", "p_volume_l" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."ensure_inventory_tank_v"("p_label" "text", "p_by" "text", "p_status" "public"."container_status", "p_volume_l" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."ensure_inventory_tank_v_text"("p_label" "text", "p_by" "text", "p_status" "text", "p_volume_l" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."ensure_inventory_tank_v_text"("p_label" "text", "p_by" "text", "p_status" "text", "p_volume_l" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."ensure_inventory_tank_v_text"("p_label" "text", "p_by" "text", "p_status" "text", "p_volume_l" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."ensure_rna_for_plasmid"("p_plasmid_code" "text", "p_suffix" "text", "p_name" "text", "p_created_by" "text", "p_notes" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."ensure_rna_for_plasmid"("p_plasmid_code" "text", "p_suffix" "text", "p_name" "text", "p_created_by" "text", "p_notes" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."ensure_rna_for_plasmid"("p_plasmid_code" "text", "p_suffix" "text", "p_name" "text", "p_created_by" "text", "p_notes" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."ensure_transgene_allele"("p_base" "text", "p_nickname" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."ensure_transgene_allele"("p_base" "text", "p_nickname" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."ensure_transgene_allele"("p_base" "text", "p_nickname" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."fish_before_insert_code"() TO "anon";
GRANT ALL ON FUNCTION "public"."fish_before_insert_code"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."fish_before_insert_code"() TO "service_role";



GRANT ALL ON FUNCTION "public"."fish_bi_set_fish_code"() TO "anon";
GRANT ALL ON FUNCTION "public"."fish_bi_set_fish_code"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."fish_bi_set_fish_code"() TO "service_role";



GRANT ALL ON FUNCTION "public"."gen_clutch_code"() TO "anon";
GRANT ALL ON FUNCTION "public"."gen_clutch_code"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."gen_clutch_code"() TO "service_role";



GRANT ALL ON FUNCTION "public"."gen_clutch_instance_code"() TO "anon";
GRANT ALL ON FUNCTION "public"."gen_clutch_instance_code"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."gen_clutch_instance_code"() TO "service_role";



GRANT ALL ON FUNCTION "public"."gen_cross_code"() TO "anon";
GRANT ALL ON FUNCTION "public"."gen_cross_code"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."gen_cross_code"() TO "service_role";



GRANT ALL ON FUNCTION "public"."gen_cross_name"("mom" "text", "dad" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."gen_cross_name"("mom" "text", "dad" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."gen_cross_name"("mom" "text", "dad" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."gen_cross_run_code"() TO "anon";
GRANT ALL ON FUNCTION "public"."gen_cross_run_code"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."gen_cross_run_code"() TO "service_role";



GRANT ALL ON FUNCTION "public"."gen_tank_code"() TO "anon";
GRANT ALL ON FUNCTION "public"."gen_tank_code"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."gen_tank_code"() TO "service_role";



GRANT ALL ON FUNCTION "public"."inherit_transgene_alleles"("child_id" "uuid", "mother_id" "uuid", "father_id" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."inherit_transgene_alleles"("child_id" "uuid", "mother_id" "uuid", "father_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."inherit_transgene_alleles"("child_id" "uuid", "mother_id" "uuid", "father_id" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."is_container_live"("s" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."is_container_live"("s" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."is_container_live"("s" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."make_fish_code_compact"() TO "anon";
GRANT ALL ON FUNCTION "public"."make_fish_code_compact"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."make_fish_code_compact"() TO "service_role";



GRANT ALL ON FUNCTION "public"."make_fish_code_yy_seq36"("ts" timestamp with time zone) TO "anon";
GRANT ALL ON FUNCTION "public"."make_fish_code_yy_seq36"("ts" timestamp with time zone) TO "authenticated";
GRANT ALL ON FUNCTION "public"."make_fish_code_yy_seq36"("ts" timestamp with time zone) TO "service_role";



GRANT ALL ON FUNCTION "public"."make_tank_code_compact"() TO "anon";
GRANT ALL ON FUNCTION "public"."make_tank_code_compact"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."make_tank_code_compact"() TO "service_role";



GRANT ALL ON FUNCTION "public"."mark_container_active"("p_id" "uuid", "p_by" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."mark_container_active"("p_id" "uuid", "p_by" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."mark_container_active"("p_id" "uuid", "p_by" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."mark_container_inactive"("p_id" "uuid", "p_by" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."mark_container_inactive"("p_id" "uuid", "p_by" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."mark_container_inactive"("p_id" "uuid", "p_by" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."mark_container_retired"("p_id" "uuid", "p_by" "text", "p_reason" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."mark_container_retired"("p_id" "uuid", "p_by" "text", "p_reason" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."mark_container_retired"("p_id" "uuid", "p_by" "text", "p_reason" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."mark_container_to_kill"("p_id" "uuid", "p_by" "text", "p_reason" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."mark_container_to_kill"("p_id" "uuid", "p_by" "text", "p_reason" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."mark_container_to_kill"("p_id" "uuid", "p_by" "text", "p_reason" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."next_fish_code"() TO "anon";
GRANT ALL ON FUNCTION "public"."next_fish_code"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."next_fish_code"() TO "service_role";



GRANT ALL ON FUNCTION "public"."normalize_cross_code"("p_code" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."normalize_cross_code"("p_code" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."normalize_cross_code"("p_code" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."safe_drop_view"("_schema" "text", "_name" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."safe_drop_view"("_schema" "text", "_name" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."safe_drop_view"("_schema" "text", "_name" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."set_container_status"("p_id" "uuid", "p_new" "public"."container_status", "p_by" "text", "p_reason" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."set_container_status"("p_id" "uuid", "p_new" "public"."container_status", "p_by" "text", "p_reason" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."set_container_status"("p_id" "uuid", "p_new" "public"."container_status", "p_by" "text", "p_reason" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."tg_upsert_fish_seed_maps"() TO "anon";
GRANT ALL ON FUNCTION "public"."tg_upsert_fish_seed_maps"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."tg_upsert_fish_seed_maps"() TO "service_role";



GRANT ALL ON FUNCTION "public"."to_base36"("n" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."to_base36"("n" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."to_base36"("n" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."trg_clutch_code"() TO "anon";
GRANT ALL ON FUNCTION "public"."trg_clutch_code"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."trg_clutch_code"() TO "service_role";



GRANT ALL ON FUNCTION "public"."trg_clutch_instance_code"() TO "anon";
GRANT ALL ON FUNCTION "public"."trg_clutch_instance_code"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."trg_clutch_instance_code"() TO "service_role";



GRANT ALL ON FUNCTION "public"."trg_containers_activate_on_label"() TO "anon";
GRANT ALL ON FUNCTION "public"."trg_containers_activate_on_label"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."trg_containers_activate_on_label"() TO "service_role";



GRANT ALL ON FUNCTION "public"."trg_cross_code"() TO "anon";
GRANT ALL ON FUNCTION "public"."trg_cross_code"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."trg_cross_code"() TO "service_role";



GRANT ALL ON FUNCTION "public"."trg_cross_code_normalize"() TO "anon";
GRANT ALL ON FUNCTION "public"."trg_cross_code_normalize"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."trg_cross_code_normalize"() TO "service_role";



GRANT ALL ON FUNCTION "public"."trg_cross_name_fill"() TO "anon";
GRANT ALL ON FUNCTION "public"."trg_cross_name_fill"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."trg_cross_name_fill"() TO "service_role";



GRANT ALL ON FUNCTION "public"."trg_cross_run_code"() TO "anon";
GRANT ALL ON FUNCTION "public"."trg_cross_run_code"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."trg_cross_run_code"() TO "service_role";



GRANT ALL ON FUNCTION "public"."trg_fish_autotank"() TO "anon";
GRANT ALL ON FUNCTION "public"."trg_fish_autotank"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."trg_fish_autotank"() TO "service_role";



GRANT ALL ON FUNCTION "public"."trg_log_container_status"() TO "anon";
GRANT ALL ON FUNCTION "public"."trg_log_container_status"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."trg_log_container_status"() TO "service_role";



GRANT ALL ON FUNCTION "public"."trg_plasmid_auto_ensure_rna"() TO "anon";
GRANT ALL ON FUNCTION "public"."trg_plasmid_auto_ensure_rna"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."trg_plasmid_auto_ensure_rna"() TO "service_role";



GRANT ALL ON FUNCTION "public"."trg_registry_fill_modern"() TO "anon";
GRANT ALL ON FUNCTION "public"."trg_registry_fill_modern"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."trg_registry_fill_modern"() TO "service_role";



GRANT ALL ON FUNCTION "public"."trg_set_updated_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."trg_set_updated_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."trg_set_updated_at"() TO "service_role";



GRANT ALL ON FUNCTION "public"."upsert_fish_by_batch_name_dob"("p_seed_batch_id" "text", "p_name" "text", "p_date_birth" "date", "p_genetic_background" "text", "p_nickname" "text", "p_line_building_stage" "text", "p_description" "text", "p_notes" "text", "p_created_by" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."upsert_fish_by_batch_name_dob"("p_seed_batch_id" "text", "p_name" "text", "p_date_birth" "date", "p_genetic_background" "text", "p_nickname" "text", "p_line_building_stage" "text", "p_description" "text", "p_notes" "text", "p_created_by" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."upsert_fish_by_batch_name_dob"("p_seed_batch_id" "text", "p_name" "text", "p_date_birth" "date", "p_genetic_background" "text", "p_nickname" "text", "p_line_building_stage" "text", "p_description" "text", "p_notes" "text", "p_created_by" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."upsert_transgene_allele_label"("p_base" "text", "p_label" "text", OUT "out_allele_number" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."upsert_transgene_allele_label"("p_base" "text", "p_label" "text", OUT "out_allele_number" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."upsert_transgene_allele_label"("p_base" "text", "p_label" "text", OUT "out_allele_number" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."upsert_transgene_allele_name"("p_base" "text", "p_name" "text", OUT "out_allele_number" integer) TO "anon";
GRANT ALL ON FUNCTION "public"."upsert_transgene_allele_name"("p_base" "text", "p_name" "text", OUT "out_allele_number" integer) TO "authenticated";
GRANT ALL ON FUNCTION "public"."upsert_transgene_allele_name"("p_base" "text", "p_name" "text", OUT "out_allele_number" integer) TO "service_role";



GRANT ALL ON TABLE "public"."allele_nicknames" TO "anon";
GRANT ALL ON TABLE "public"."allele_nicknames" TO "authenticated";
GRANT ALL ON TABLE "public"."allele_nicknames" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."allele_nicknames" TO "app_rw";



GRANT ALL ON TABLE "public"."bruker_mounts" TO "anon";
GRANT ALL ON TABLE "public"."bruker_mounts" TO "authenticated";
GRANT ALL ON TABLE "public"."bruker_mounts" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."bruker_mounts" TO "app_rw";



GRANT ALL ON TABLE "public"."clutch_containers" TO "anon";
GRANT ALL ON TABLE "public"."clutch_containers" TO "authenticated";
GRANT ALL ON TABLE "public"."clutch_containers" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."clutch_containers" TO "app_rw";



GRANT ALL ON TABLE "public"."clutch_genotype_options" TO "anon";
GRANT ALL ON TABLE "public"."clutch_genotype_options" TO "authenticated";
GRANT ALL ON TABLE "public"."clutch_genotype_options" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."clutch_genotype_options" TO "app_rw";



GRANT ALL ON SEQUENCE "public"."clutch_instance_code_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."clutch_instance_code_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."clutch_instance_code_seq" TO "service_role";
GRANT ALL ON SEQUENCE "public"."clutch_instance_code_seq" TO "app_rw";



GRANT ALL ON TABLE "public"."clutch_instances" TO "anon";
GRANT ALL ON TABLE "public"."clutch_instances" TO "authenticated";
GRANT ALL ON TABLE "public"."clutch_instances" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."clutch_instances" TO "app_rw";



GRANT ALL ON TABLE "public"."clutch_plan_treatments" TO "anon";
GRANT ALL ON TABLE "public"."clutch_plan_treatments" TO "authenticated";
GRANT ALL ON TABLE "public"."clutch_plan_treatments" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."clutch_plan_treatments" TO "app_rw";



GRANT ALL ON TABLE "public"."clutch_plans" TO "anon";
GRANT ALL ON TABLE "public"."clutch_plans" TO "authenticated";
GRANT ALL ON TABLE "public"."clutch_plans" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."clutch_plans" TO "app_rw";



GRANT ALL ON TABLE "public"."clutch_treatments" TO "anon";
GRANT ALL ON TABLE "public"."clutch_treatments" TO "authenticated";
GRANT ALL ON TABLE "public"."clutch_treatments" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."clutch_treatments" TO "app_rw";



GRANT ALL ON TABLE "public"."clutches" TO "anon";
GRANT ALL ON TABLE "public"."clutches" TO "authenticated";
GRANT ALL ON TABLE "public"."clutches" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."clutches" TO "app_rw";



GRANT ALL ON TABLE "public"."container_status_history" TO "anon";
GRANT ALL ON TABLE "public"."container_status_history" TO "authenticated";
GRANT ALL ON TABLE "public"."container_status_history" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."container_status_history" TO "app_rw";



GRANT ALL ON TABLE "public"."containers" TO "anon";
GRANT ALL ON TABLE "public"."containers" TO "authenticated";
GRANT ALL ON TABLE "public"."containers" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."containers" TO "app_rw";



GRANT ALL ON SEQUENCE "public"."cross_code_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."cross_code_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."cross_code_seq" TO "service_role";
GRANT ALL ON SEQUENCE "public"."cross_code_seq" TO "app_rw";



GRANT ALL ON TABLE "public"."cross_instances" TO "anon";
GRANT ALL ON TABLE "public"."cross_instances" TO "authenticated";
GRANT ALL ON TABLE "public"."cross_instances" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."cross_instances" TO "app_rw";



GRANT ALL ON TABLE "public"."cross_plan_genotype_alleles" TO "anon";
GRANT ALL ON TABLE "public"."cross_plan_genotype_alleles" TO "authenticated";
GRANT ALL ON TABLE "public"."cross_plan_genotype_alleles" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."cross_plan_genotype_alleles" TO "app_rw";



GRANT ALL ON TABLE "public"."cross_plan_runs" TO "anon";
GRANT ALL ON TABLE "public"."cross_plan_runs" TO "authenticated";
GRANT ALL ON TABLE "public"."cross_plan_runs" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."cross_plan_runs" TO "app_rw";



GRANT ALL ON TABLE "public"."cross_plan_treatments" TO "anon";
GRANT ALL ON TABLE "public"."cross_plan_treatments" TO "authenticated";
GRANT ALL ON TABLE "public"."cross_plan_treatments" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."cross_plan_treatments" TO "app_rw";



GRANT ALL ON TABLE "public"."cross_plans" TO "anon";
GRANT ALL ON TABLE "public"."cross_plans" TO "authenticated";
GRANT ALL ON TABLE "public"."cross_plans" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."cross_plans" TO "app_rw";



GRANT ALL ON SEQUENCE "public"."cross_run_code_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."cross_run_code_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."cross_run_code_seq" TO "service_role";
GRANT ALL ON SEQUENCE "public"."cross_run_code_seq" TO "app_rw";



GRANT ALL ON TABLE "public"."crosses" TO "anon";
GRANT ALL ON TABLE "public"."crosses" TO "authenticated";
GRANT ALL ON TABLE "public"."crosses" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."crosses" TO "app_rw";



GRANT ALL ON TABLE "public"."fish" TO "anon";
GRANT ALL ON TABLE "public"."fish" TO "authenticated";
GRANT ALL ON TABLE "public"."fish" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."fish" TO "app_rw";



GRANT ALL ON TABLE "public"."fish_code_audit" TO "anon";
GRANT ALL ON TABLE "public"."fish_code_audit" TO "authenticated";
GRANT ALL ON TABLE "public"."fish_code_audit" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."fish_code_audit" TO "app_rw";



GRANT ALL ON SEQUENCE "public"."fish_code_audit_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."fish_code_audit_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."fish_code_audit_id_seq" TO "service_role";
GRANT ALL ON SEQUENCE "public"."fish_code_audit_id_seq" TO "app_rw";



GRANT ALL ON SEQUENCE "public"."fish_code_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."fish_code_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."fish_code_seq" TO "service_role";
GRANT ALL ON SEQUENCE "public"."fish_code_seq" TO "app_rw";



GRANT ALL ON TABLE "public"."fish_seed_batches" TO "anon";
GRANT ALL ON TABLE "public"."fish_seed_batches" TO "authenticated";
GRANT ALL ON TABLE "public"."fish_seed_batches" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."fish_seed_batches" TO "app_rw";



GRANT ALL ON TABLE "public"."fish_seed_batches_map" TO "anon";
GRANT ALL ON TABLE "public"."fish_seed_batches_map" TO "authenticated";
GRANT ALL ON TABLE "public"."fish_seed_batches_map" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."fish_seed_batches_map" TO "app_rw";



GRANT ALL ON TABLE "public"."fish_tank_memberships" TO "anon";
GRANT ALL ON TABLE "public"."fish_tank_memberships" TO "authenticated";
GRANT ALL ON TABLE "public"."fish_tank_memberships" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."fish_tank_memberships" TO "app_rw";



GRANT ALL ON TABLE "public"."fish_transgene_alleles" TO "anon";
GRANT ALL ON TABLE "public"."fish_transgene_alleles" TO "authenticated";
GRANT ALL ON TABLE "public"."fish_transgene_alleles" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."fish_transgene_alleles" TO "app_rw";



GRANT ALL ON TABLE "public"."fish_year_counters" TO "anon";
GRANT ALL ON TABLE "public"."fish_year_counters" TO "authenticated";
GRANT ALL ON TABLE "public"."fish_year_counters" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."fish_year_counters" TO "app_rw";



GRANT ALL ON TABLE "public"."injected_plasmid_treatments" TO "anon";
GRANT ALL ON TABLE "public"."injected_plasmid_treatments" TO "authenticated";
GRANT ALL ON TABLE "public"."injected_plasmid_treatments" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."injected_plasmid_treatments" TO "app_rw";



GRANT ALL ON TABLE "public"."injected_rna_treatments" TO "anon";
GRANT ALL ON TABLE "public"."injected_rna_treatments" TO "authenticated";
GRANT ALL ON TABLE "public"."injected_rna_treatments" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."injected_rna_treatments" TO "app_rw";



GRANT ALL ON TABLE "public"."label_items" TO "anon";
GRANT ALL ON TABLE "public"."label_items" TO "authenticated";
GRANT ALL ON TABLE "public"."label_items" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."label_items" TO "app_rw";



GRANT ALL ON TABLE "public"."label_jobs" TO "anon";
GRANT ALL ON TABLE "public"."label_jobs" TO "authenticated";
GRANT ALL ON TABLE "public"."label_jobs" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."label_jobs" TO "app_rw";



GRANT ALL ON TABLE "public"."load_log_fish" TO "anon";
GRANT ALL ON TABLE "public"."load_log_fish" TO "authenticated";
GRANT ALL ON TABLE "public"."load_log_fish" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."load_log_fish" TO "app_rw";



GRANT ALL ON TABLE "public"."planned_crosses" TO "anon";
GRANT ALL ON TABLE "public"."planned_crosses" TO "authenticated";
GRANT ALL ON TABLE "public"."planned_crosses" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."planned_crosses" TO "app_rw";



GRANT ALL ON TABLE "public"."plasmid_registry" TO "anon";
GRANT ALL ON TABLE "public"."plasmid_registry" TO "authenticated";
GRANT ALL ON TABLE "public"."plasmid_registry" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."plasmid_registry" TO "app_rw";



GRANT ALL ON TABLE "public"."plasmids" TO "anon";
GRANT ALL ON TABLE "public"."plasmids" TO "authenticated";
GRANT ALL ON TABLE "public"."plasmids" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."plasmids" TO "app_rw";



GRANT ALL ON TABLE "public"."rna_registry" TO "anon";
GRANT ALL ON TABLE "public"."rna_registry" TO "authenticated";
GRANT ALL ON TABLE "public"."rna_registry" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."rna_registry" TO "app_rw";



GRANT ALL ON TABLE "public"."rnas" TO "anon";
GRANT ALL ON TABLE "public"."rnas" TO "authenticated";
GRANT ALL ON TABLE "public"."rnas" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."rnas" TO "app_rw";



GRANT ALL ON TABLE "public"."seed_batches" TO "anon";
GRANT ALL ON TABLE "public"."seed_batches" TO "authenticated";
GRANT ALL ON TABLE "public"."seed_batches" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."seed_batches" TO "app_rw";



GRANT ALL ON TABLE "public"."selection_labels" TO "anon";
GRANT ALL ON TABLE "public"."selection_labels" TO "authenticated";
GRANT ALL ON TABLE "public"."selection_labels" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."selection_labels" TO "app_rw";



GRANT ALL ON SEQUENCE "public"."seq_clutch_code" TO "anon";
GRANT ALL ON SEQUENCE "public"."seq_clutch_code" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."seq_clutch_code" TO "service_role";
GRANT ALL ON SEQUENCE "public"."seq_clutch_code" TO "app_rw";



GRANT ALL ON SEQUENCE "public"."tank_code_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."tank_code_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."tank_code_seq" TO "service_role";
GRANT ALL ON SEQUENCE "public"."tank_code_seq" TO "app_rw";



GRANT ALL ON TABLE "public"."tank_requests" TO "anon";
GRANT ALL ON TABLE "public"."tank_requests" TO "authenticated";
GRANT ALL ON TABLE "public"."tank_requests" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."tank_requests" TO "app_rw";



GRANT ALL ON TABLE "public"."tank_year_counters" TO "anon";
GRANT ALL ON TABLE "public"."tank_year_counters" TO "authenticated";
GRANT ALL ON TABLE "public"."tank_year_counters" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."tank_year_counters" TO "app_rw";



GRANT ALL ON TABLE "public"."transgene_allele_counters" TO "anon";
GRANT ALL ON TABLE "public"."transgene_allele_counters" TO "authenticated";
GRANT ALL ON TABLE "public"."transgene_allele_counters" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."transgene_allele_counters" TO "app_rw";



GRANT ALL ON TABLE "public"."transgene_allele_registry" TO "anon";
GRANT ALL ON TABLE "public"."transgene_allele_registry" TO "authenticated";
GRANT ALL ON TABLE "public"."transgene_allele_registry" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."transgene_allele_registry" TO "app_rw";



GRANT ALL ON TABLE "public"."transgene_alleles" TO "anon";
GRANT ALL ON TABLE "public"."transgene_alleles" TO "authenticated";
GRANT ALL ON TABLE "public"."transgene_alleles" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."transgene_alleles" TO "app_rw";



GRANT ALL ON TABLE "public"."transgenes" TO "anon";
GRANT ALL ON TABLE "public"."transgenes" TO "authenticated";
GRANT ALL ON TABLE "public"."transgenes" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."transgenes" TO "app_rw";



GRANT ALL ON TABLE "public"."vw_planned_clutches_overview" TO "anon";
GRANT ALL ON TABLE "public"."vw_planned_clutches_overview" TO "authenticated";
GRANT ALL ON TABLE "public"."vw_planned_clutches_overview" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."vw_planned_clutches_overview" TO "app_rw";



GRANT ALL ON TABLE "public"."v_cross_concepts_overview" TO "anon";
GRANT ALL ON TABLE "public"."v_cross_concepts_overview" TO "authenticated";
GRANT ALL ON TABLE "public"."v_cross_concepts_overview" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."v_cross_concepts_overview" TO "app_rw";



GRANT ALL ON TABLE "public"."vw_cross_runs_overview" TO "anon";
GRANT ALL ON TABLE "public"."vw_cross_runs_overview" TO "authenticated";
GRANT ALL ON TABLE "public"."vw_cross_runs_overview" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."vw_cross_runs_overview" TO "app_rw";



GRANT ALL ON TABLE "public"."v_bruker_mounts_enriched" TO "anon";
GRANT ALL ON TABLE "public"."v_bruker_mounts_enriched" TO "authenticated";
GRANT ALL ON TABLE "public"."v_bruker_mounts_enriched" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."v_bruker_mounts_enriched" TO "app_rw";



GRANT ALL ON TABLE "public"."v_clutch_instance_selections" TO "anon";
GRANT ALL ON TABLE "public"."v_clutch_instance_selections" TO "authenticated";
GRANT ALL ON TABLE "public"."v_clutch_instance_selections" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."v_clutch_instance_selections" TO "app_rw";



GRANT ALL ON TABLE "public"."v_clutch_instances_annotations" TO "anon";
GRANT ALL ON TABLE "public"."v_clutch_instances_annotations" TO "authenticated";
GRANT ALL ON TABLE "public"."v_clutch_instances_annotations" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."v_clutch_instances_annotations" TO "app_rw";



GRANT ALL ON TABLE "public"."v_containers_crossing_candidates" TO "anon";
GRANT ALL ON TABLE "public"."v_containers_crossing_candidates" TO "authenticated";
GRANT ALL ON TABLE "public"."v_containers_crossing_candidates" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."v_containers_crossing_candidates" TO "app_rw";



GRANT ALL ON TABLE "public"."v_containers_live" TO "anon";
GRANT ALL ON TABLE "public"."v_containers_live" TO "authenticated";
GRANT ALL ON TABLE "public"."v_containers_live" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."v_containers_live" TO "app_rw";



GRANT ALL ON TABLE "public"."v_cross_plan_runs_enriched" TO "anon";
GRANT ALL ON TABLE "public"."v_cross_plan_runs_enriched" TO "authenticated";
GRANT ALL ON TABLE "public"."v_cross_plan_runs_enriched" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."v_cross_plan_runs_enriched" TO "app_rw";



GRANT ALL ON TABLE "public"."v_cross_plans_enriched" TO "anon";
GRANT ALL ON TABLE "public"."v_cross_plans_enriched" TO "authenticated";
GRANT ALL ON TABLE "public"."v_cross_plans_enriched" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."v_cross_plans_enriched" TO "app_rw";



GRANT ALL ON TABLE "public"."v_crosses_status" TO "anon";
GRANT ALL ON TABLE "public"."v_crosses_status" TO "authenticated";
GRANT ALL ON TABLE "public"."v_crosses_status" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."v_crosses_status" TO "app_rw";



GRANT ALL ON TABLE "public"."v_fish_label_fields" TO "anon";
GRANT ALL ON TABLE "public"."v_fish_label_fields" TO "authenticated";
GRANT ALL ON TABLE "public"."v_fish_label_fields" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."v_fish_label_fields" TO "app_rw";



GRANT ALL ON TABLE "public"."v_fish_living_tank_counts" TO "anon";
GRANT ALL ON TABLE "public"."v_fish_living_tank_counts" TO "authenticated";
GRANT ALL ON TABLE "public"."v_fish_living_tank_counts" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."v_fish_living_tank_counts" TO "app_rw";



GRANT ALL ON TABLE "public"."vw_fish_overview_with_label" TO "anon";
GRANT ALL ON TABLE "public"."vw_fish_overview_with_label" TO "authenticated";
GRANT ALL ON TABLE "public"."vw_fish_overview_with_label" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."vw_fish_overview_with_label" TO "app_rw";



GRANT ALL ON TABLE "public"."v_fish_overview" TO "anon";
GRANT ALL ON TABLE "public"."v_fish_overview" TO "authenticated";
GRANT ALL ON TABLE "public"."v_fish_overview" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."v_fish_overview" TO "app_rw";



GRANT ALL ON TABLE "public"."v_fish_overview_canonical" TO "anon";
GRANT ALL ON TABLE "public"."v_fish_overview_canonical" TO "authenticated";
GRANT ALL ON TABLE "public"."v_fish_overview_canonical" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."v_fish_overview_canonical" TO "app_rw";



GRANT ALL ON TABLE "public"."v_label_jobs_recent" TO "anon";
GRANT ALL ON TABLE "public"."v_label_jobs_recent" TO "authenticated";
GRANT ALL ON TABLE "public"."v_label_jobs_recent" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."v_label_jobs_recent" TO "app_rw";



GRANT ALL ON TABLE "public"."vw_bruker_mounts_enriched" TO "anon";
GRANT ALL ON TABLE "public"."vw_bruker_mounts_enriched" TO "authenticated";
GRANT ALL ON TABLE "public"."vw_bruker_mounts_enriched" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."vw_bruker_mounts_enriched" TO "app_rw";



GRANT ALL ON TABLE "public"."vw_clutches_concept_overview" TO "anon";
GRANT ALL ON TABLE "public"."vw_clutches_concept_overview" TO "authenticated";
GRANT ALL ON TABLE "public"."vw_clutches_concept_overview" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."vw_clutches_concept_overview" TO "app_rw";



GRANT ALL ON TABLE "public"."vw_clutches_overview_human" TO "anon";
GRANT ALL ON TABLE "public"."vw_clutches_overview_human" TO "authenticated";
GRANT ALL ON TABLE "public"."vw_clutches_overview_human" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."vw_clutches_overview_human" TO "app_rw";



GRANT ALL ON TABLE "public"."vw_crosses_concept" TO "anon";
GRANT ALL ON TABLE "public"."vw_crosses_concept" TO "authenticated";
GRANT ALL ON TABLE "public"."vw_crosses_concept" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."vw_crosses_concept" TO "app_rw";



GRANT ALL ON TABLE "public"."vw_fish_standard" TO "anon";
GRANT ALL ON TABLE "public"."vw_fish_standard" TO "authenticated";
GRANT ALL ON TABLE "public"."vw_fish_standard" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."vw_fish_standard" TO "app_rw";



GRANT ALL ON TABLE "public"."vw_label_rows" TO "anon";
GRANT ALL ON TABLE "public"."vw_label_rows" TO "authenticated";
GRANT ALL ON TABLE "public"."vw_label_rows" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."vw_label_rows" TO "app_rw";



GRANT ALL ON TABLE "public"."vw_plasmids_overview" TO "anon";
GRANT ALL ON TABLE "public"."vw_plasmids_overview" TO "authenticated";
GRANT ALL ON TABLE "public"."vw_plasmids_overview" TO "service_role";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."vw_plasmids_overview" TO "app_rw";



ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "app_rw";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT SELECT,INSERT,DELETE,UPDATE ON TABLES TO "app_rw";







RESET ALL;
