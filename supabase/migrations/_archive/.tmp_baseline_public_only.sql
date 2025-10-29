SET search_path TO public;
--
-- PostgreSQL database dump
--

\restrict vnE7Kr2qQUFYM7DfULg0xTFbKjtg4PM2LxT4CTnEPMQsGHlcKALCAi05FPQGuzR

-- Dumped from database version 17.4
-- Dumped by pg_dump version 18.0

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

--
--



--
-- Name: audit; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA audit;


--
-- Name: auth; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA auth;


--
-- Name: extensions; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA extensions;


--
-- Name: graphql; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA graphql;


--
-- Name: graphql_public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA graphql_public;


--
-- Name: pg_net; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions;


--
-- Name: EXTENSION pg_net; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_net IS 'Async HTTP';


--
-- Name: pgbouncer; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA pgbouncer;


--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

-- *not* creating schema, since initdb creates it


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS '';


--
-- Name: raw; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA raw;


--
-- Name: realtime; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA realtime;


--
-- Name: staging; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA staging;


--
-- Name: storage; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA storage;


--
-- Name: supabase_functions; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA supabase_functions;


--
-- Name: supabase_migrations; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA supabase_migrations;


--
-- Name: util_mig; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA util_mig;


--
-- Name: vault; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA vault;


--
-- Name: pg_graphql; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_graphql WITH SCHEMA graphql;


--
-- Name: EXTENSION pg_graphql; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_graphql IS 'pg_graphql: GraphQL support';


--
-- Name: pg_stat_statements; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA extensions;


--
-- Name: EXTENSION pg_stat_statements; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_stat_statements IS 'track planning and execution statistics of all SQL statements executed';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: supabase_vault; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS supabase_vault WITH SCHEMA vault;


--
-- Name: EXTENSION supabase_vault; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION supabase_vault IS 'Supabase Vault Extension';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA extensions;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: aal_level; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.aal_level AS ENUM (
    'aal1',
    'aal2',
    'aal3'
);


--
-- Name: code_challenge_method; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.code_challenge_method AS ENUM (
    's256',
    'plain'
);


--
-- Name: factor_status; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.factor_status AS ENUM (
    'unverified',
    'verified'
);


--
-- Name: factor_type; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.factor_type AS ENUM (
    'totp',
    'webauthn',
    'phone'
);


--
-- Name: oauth_authorization_status; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.oauth_authorization_status AS ENUM (
    'pending',
    'approved',
    'denied',
    'expired'
);


--
-- Name: oauth_client_type; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.oauth_client_type AS ENUM (
    'public',
    'confidential'
);


--
-- Name: oauth_registration_type; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.oauth_registration_type AS ENUM (
    'dynamic',
    'manual'
);


--
-- Name: oauth_response_type; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.oauth_response_type AS ENUM (
    'code'
);


--
-- Name: one_time_token_type; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.one_time_token_type AS ENUM (
    'confirmation_token',
    'reauthentication_token',
    'recovery_token',
    'email_change_token_new',
    'email_change_token_current',
    'phone_change_token'
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
-- Name: action; Type: TYPE; Schema: realtime; Owner: -
--

CREATE TYPE realtime.action AS ENUM (
    'INSERT',
    'UPDATE',
    'DELETE',
    'TRUNCATE',
    'ERROR'
);


--
-- Name: equality_op; Type: TYPE; Schema: realtime; Owner: -
--

CREATE TYPE realtime.equality_op AS ENUM (
    'eq',
    'neq',
    'lt',
    'lte',
    'gt',
    'gte',
    'in'
);


--
-- Name: user_defined_filter; Type: TYPE; Schema: realtime; Owner: -
--

CREATE TYPE realtime.user_defined_filter AS (
	column_name text,
	op realtime.equality_op,
	value text
);


--
-- Name: wal_column; Type: TYPE; Schema: realtime; Owner: -
--

CREATE TYPE realtime.wal_column AS (
	name text,
	type_name text,
	type_oid oid,
	value jsonb,
	is_pkey boolean,
	is_selectable boolean
);


--
-- Name: wal_rls; Type: TYPE; Schema: realtime; Owner: -
--

CREATE TYPE realtime.wal_rls AS (
	wal jsonb,
	is_rls_enabled boolean,
	subscription_ids uuid[],
	errors text[]
);


--
-- Name: buckettype; Type: TYPE; Schema: storage; Owner: -
--

CREATE TYPE storage.buckettype AS ENUM (
    'STANDARD',
    'ANALYTICS'
);


--
-- Name: attach_writes(regclass); Type: FUNCTION; Schema: audit; Owner: -
--

CREATE FUNCTION audit.attach_writes(t regclass) RETURNS void
    LANGUAGE plpgsql
    AS $$
begin
  execute format('drop trigger if exists trg_audit_ins on %s', t);
  execute format('drop trigger if exists trg_audit_upd on %s', t);
  execute format('drop trigger if exists trg_audit_del on %s', t);

  execute format('create trigger trg_audit_ins after insert on %s for each row execute function audit.fn_writes()', t);
  execute format('create trigger trg_audit_upd after update on %s for each row execute function audit.fn_writes()', t);
  execute format('create trigger trg_audit_del after delete on %s for each row execute function audit.fn_writes()', t);
end
$$;


--
-- Name: fn_writes(); Type: FUNCTION; Schema: audit; Owner: -
--

CREATE FUNCTION audit.fn_writes() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  RETURN COALESCE(NEW, OLD);
END;
$$;


--
-- Name: email(); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.email() RETURNS text
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.email', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'email')
  )::text
$$;


--
-- Name: FUNCTION email(); Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON FUNCTION auth.email() IS 'Deprecated. Use auth.jwt() -> ''email'' instead.';


--
-- Name: jwt(); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.jwt() RETURNS jsonb
    LANGUAGE sql STABLE
    AS $$
  select 
    coalesce(
        nullif(current_setting('request.jwt.claim', true), ''),
        nullif(current_setting('request.jwt.claims', true), '')
    )::jsonb
$$;


--
-- Name: role(); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.role() RETURNS text
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.role', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role')
  )::text
$$;


--
-- Name: FUNCTION role(); Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON FUNCTION auth.role() IS 'Deprecated. Use auth.jwt() -> ''role'' instead.';


--
-- Name: uid(); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.uid() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
  )::uuid
$$;


--
-- Name: FUNCTION uid(); Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON FUNCTION auth.uid() IS 'Deprecated. Use auth.jwt() -> ''sub'' instead.';


--
-- Name: grant_pg_cron_access(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.grant_pg_cron_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF EXISTS (
    SELECT
    FROM pg_event_trigger_ddl_commands() AS ev
    JOIN pg_extension AS ext
    ON ev.objid = ext.oid
    WHERE ext.extname = 'pg_cron'
  )
  THEN
    grant usage on schema cron to postgres with grant option;

    alter default privileges in schema cron grant all on tables to postgres with grant option;
    alter default privileges in schema cron grant all on functions to postgres with grant option;
    alter default privileges in schema cron grant all on sequences to postgres with grant option;

    alter default privileges for user supabase_admin in schema cron grant all
        on sequences to postgres with grant option;
    alter default privileges for user supabase_admin in schema cron grant all
        on tables to postgres with grant option;
    alter default privileges for user supabase_admin in schema cron grant all
        on functions to postgres with grant option;

    grant all privileges on all tables in schema cron to postgres with grant option;
    revoke all on table cron.job from postgres;
    grant select on table cron.job to postgres with grant option;
  END IF;
END;
$$;


--
-- Name: FUNCTION grant_pg_cron_access(); Type: COMMENT; Schema: extensions; Owner: -
--

COMMENT ON FUNCTION extensions.grant_pg_cron_access() IS 'Grants access to pg_cron';


--
-- Name: grant_pg_graphql_access(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.grant_pg_graphql_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $_$
DECLARE
    func_is_graphql_resolve bool;
BEGIN
    func_is_graphql_resolve = (
        SELECT n.proname = 'resolve'
        FROM pg_event_trigger_ddl_commands() AS ev
        LEFT JOIN pg_catalog.pg_proc AS n
        ON ev.objid = n.oid
    );

    IF func_is_graphql_resolve
    THEN
        -- Update public wrapper to pass all arguments through to the pg_graphql resolve func
        DROP FUNCTION IF EXISTS graphql_public.graphql;
        create or replace function graphql_public.graphql(
            "operationName" text default null,
            query text default null,
            variables jsonb default null,
            extensions jsonb default null
        )
            returns jsonb
            language sql
        as $$
            select graphql.resolve(
                query := query,
                variables := coalesce(variables, '{}'),
                "operationName" := "operationName",
                extensions := extensions
            );
        $$;

        -- This hook executes when `graphql.resolve` is created. That is not necessarily the last
        -- function in the extension so we need to grant permissions on existing entities AND
        -- update default permissions to any others that are created after `graphql.resolve`
        grant usage on schema graphql to postgres, anon, authenticated, service_role;
        grant select on all tables in schema graphql to postgres, anon, authenticated, service_role;
        grant execute on all functions in schema graphql to postgres, anon, authenticated, service_role;
        grant all on all sequences in schema graphql to postgres, anon, authenticated, service_role;
        alter default privileges in schema graphql grant all on tables to postgres, anon, authenticated, service_role;
        alter default privileges in schema graphql grant all on functions to postgres, anon, authenticated, service_role;
        alter default privileges in schema graphql grant all on sequences to postgres, anon, authenticated, service_role;

        -- Allow postgres role to allow granting usage on graphql and graphql_public schemas to custom roles
        grant usage on schema graphql_public to postgres with grant option;
        grant usage on schema graphql to postgres with grant option;
    END IF;

END;
$_$;


--
-- Name: FUNCTION grant_pg_graphql_access(); Type: COMMENT; Schema: extensions; Owner: -
--

COMMENT ON FUNCTION extensions.grant_pg_graphql_access() IS 'Grants access to pg_graphql';


--
-- Name: grant_pg_net_access(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.grant_pg_net_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_event_trigger_ddl_commands() AS ev
    JOIN pg_extension AS ext
    ON ev.objid = ext.oid
    WHERE ext.extname = 'pg_net'
  )
  THEN
    IF NOT EXISTS (
      SELECT 1
      FROM pg_roles
      WHERE rolname = 'supabase_functions_admin'
    )
    THEN
      CREATE USER supabase_functions_admin NOINHERIT CREATEROLE LOGIN NOREPLICATION;
    END IF;

    GRANT USAGE ON SCHEMA net TO supabase_functions_admin, postgres, anon, authenticated, service_role;

    IF EXISTS (
      SELECT FROM pg_extension
      WHERE extname = 'pg_net'
      -- all versions in use on existing projects as of 2025-02-20
      -- version 0.12.0 onwards don't need these applied
      AND extversion IN ('0.2', '0.6', '0.7', '0.7.1', '0.8', '0.10.0', '0.11.0')
    ) THEN
      ALTER function net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) SECURITY DEFINER;
      ALTER function net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) SECURITY DEFINER;

      ALTER function net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) SET search_path = net;
      ALTER function net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) SET search_path = net;

      REVOKE ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;
      REVOKE ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;

      GRANT EXECUTE ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin, postgres, anon, authenticated, service_role;
      GRANT EXECUTE ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin, postgres, anon, authenticated, service_role;
    END IF;
  END IF;
END;
$$;


--
-- Name: FUNCTION grant_pg_net_access(); Type: COMMENT; Schema: extensions; Owner: -
--

COMMENT ON FUNCTION extensions.grant_pg_net_access() IS 'Grants access to pg_net';


--
-- Name: pgrst_ddl_watch(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.pgrst_ddl_watch() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  cmd record;
BEGIN
  FOR cmd IN SELECT * FROM pg_event_trigger_ddl_commands()
  LOOP
    IF cmd.command_tag IN (
      'CREATE SCHEMA', 'ALTER SCHEMA'
    , 'CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO', 'ALTER TABLE'
    , 'CREATE FOREIGN TABLE', 'ALTER FOREIGN TABLE'
    , 'CREATE VIEW', 'ALTER VIEW'
    , 'CREATE MATERIALIZED VIEW', 'ALTER MATERIALIZED VIEW'
    , 'CREATE FUNCTION', 'ALTER FUNCTION'
    , 'CREATE TRIGGER'
    , 'CREATE TYPE', 'ALTER TYPE'
    , 'CREATE RULE'
    , 'COMMENT'
    )
    -- don't notify in case of CREATE TEMP table or other objects created on pg_temp
    AND cmd.schema_name is distinct from 'pg_temp'
    THEN
      NOTIFY pgrst, 'reload schema';
    END IF;
  END LOOP;
END; $$;


--
-- Name: pgrst_drop_watch(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.pgrst_drop_watch() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  obj record;
BEGIN
  FOR obj IN SELECT * FROM pg_event_trigger_dropped_objects()
  LOOP
    IF obj.object_type IN (
      'schema'
    , 'table'
    , 'foreign table'
    , 'view'
    , 'materialized view'
    , 'function'
    , 'trigger'
    , 'type'
    , 'rule'
    )
    AND obj.is_temporary IS false -- no pg_temp objects
    THEN
      NOTIFY pgrst, 'reload schema';
    END IF;
  END LOOP;
END; $$;


--
-- Name: set_graphql_placeholder(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.set_graphql_placeholder() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $_$
    DECLARE
    graphql_is_dropped bool;
    BEGIN
    graphql_is_dropped = (
        SELECT ev.schema_name = 'graphql_public'
        FROM pg_event_trigger_dropped_objects() AS ev
        WHERE ev.schema_name = 'graphql_public'
    );

    IF graphql_is_dropped
    THEN
        create or replace function graphql_public.graphql(
            "operationName" text default null,
            query text default null,
            variables jsonb default null,
            extensions jsonb default null
        )
            returns jsonb
            language plpgsql
        as $$
            DECLARE
                server_version float;
            BEGIN
                server_version = (SELECT (SPLIT_PART((select version()), ' ', 2))::float);

                IF server_version >= 14 THEN
                    RETURN jsonb_build_object(
                        'errors', jsonb_build_array(
                            jsonb_build_object(
                                'message', 'pg_graphql extension is not enabled.'
                            )
                        )
                    );
                ELSE
                    RETURN jsonb_build_object(
                        'errors', jsonb_build_array(
                            jsonb_build_object(
                                'message', 'pg_graphql is only available on projects running Postgres 14 onwards.'
                            )
                        )
                    );
                END IF;
            END;
        $$;
    END IF;

    END;
$_$;


--
-- Name: FUNCTION set_graphql_placeholder(); Type: COMMENT; Schema: extensions; Owner: -
--

COMMENT ON FUNCTION extensions.set_graphql_placeholder() IS 'Reintroduces placeholder function for graphql_public.graphql';


--
-- Name: get_auth(text); Type: FUNCTION; Schema: pgbouncer; Owner: -
--

CREATE FUNCTION pgbouncer.get_auth(p_usename text) RETURNS TABLE(username text, password text)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $_$
begin
    raise debug 'PgBouncer auth request: %', p_usename;

    return query
    select 
        rolname::text, 
        case when rolvaliduntil < now() 
            then null 
            else rolpassword::text 
        end 
    from pg_authid 
    where rolname=$1 and rolcanlogin;
end;
$_$;


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
-- Name: fn_fish_autocreate_tank_v2(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_fish_autocreate_tank_v2() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
declare
  v_code text;
  v_suffix int;
  v_created_by uuid;
begin
  v_code := new.fish_code;
  if v_code is null or v_code = '' then return new; end if;

  if not exists (select 1 from public.tanks where fish_code = v_code) then
    v_suffix := public.fn_next_tank_suffix_by_code(v_code);
    v_created_by := case when new.created_by is null or new.created_by::text='' then null else new.created_by::uuid end;
    insert into public.tanks (tank_code, fish_code, status, rack, position, created_at, created_by)
    values ('TANK('||v_code||')#'||v_suffix, v_code, 'active', null, null, now(), v_created_by);
  end if;
  return new;
end $$;


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

CREATE FUNCTION public.gen_clutch_instance_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE y text := to_char(current_date,'YY'); n bigint;
BEGIN SELECT nextval('public.clutch_instance_code_seq') INTO n; RETURN format('CI-%s%05s', y, n); END;
$$;


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

CREATE FUNCTION public.upsert_fish_allele_from_csv(p_fish_id uuid, p_base_code text, p_allele_nickname text) RETURNS TABLE(ret_fish_id uuid, ret_transgene_base_code text, ret_allele_number integer)
    LANGUAGE plpgsql
    AS $$
DECLARE
  a_rec record;  -- (allele_number int, allele_name text, allele_nickname text)
BEGIN
  -- Reuse-or-mint allele for (base_code, nickname). Nickname is treated as STRING.
  SELECT * INTO a_rec
  FROM public.ensure_allele_from_csv(p_base_code, p_allele_nickname);

  -- Link to fish; if row exists for (fish_id, base), update the allele number.
  RETURN QUERY
  INSERT INTO public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number)
  VALUES (p_fish_id, p_base_code, a_rec.allele_number)
  ON CONFLICT (fish_id, transgene_base_code)
  DO UPDATE SET allele_number = EXCLUDED.allele_number
  RETURNING
    public.fish_transgene_alleles.fish_id,
    public.fish_transgene_alleles.transgene_base_code,
    public.fish_transgene_alleles.allele_number;
END
$$;


--
-- Name: upsert_fish_by_batch_name_dob(text, text, date, text, text, text, text, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.upsert_fish_by_batch_name_dob(p_seed_batch_id text, p_name text, p_date_birth date, p_genetic_background text DEFAULT NULL::text, p_nickname text DEFAULT NULL::text, p_line_building_stage text DEFAULT NULL::text, p_description text DEFAULT NULL::text, p_notes text DEFAULT NULL::text, p_created_by text DEFAULT NULL::text) RETURNS TABLE(fish_id uuid, fish_code text)
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE
  v_id   uuid;
  v_code text;
BEGIN
  -- try existing (batch, name, dob)
  SELECT f.id, f.fish_code
    INTO v_id, v_code
  FROM public.fish f
  JOIN public.fish_seed_batches_map m
    ON m.fish_id = f.id
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
     WHERE id = v_id;

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
  RETURNING id, public.fish.fish_code  -- disambiguate the column
  INTO v_id, v_code;

  -- map to batch (idempotent)
  INSERT INTO public.fish_seed_batches_map (fish_id, seed_batch_id)
  VALUES (v_id, p_seed_batch_id)
  ON CONFLICT DO NOTHING;

  RETURN QUERY SELECT v_id, v_code;
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


--
-- Name: apply_rls(jsonb, integer); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer DEFAULT (1024 * 1024)) RETURNS SETOF realtime.wal_rls
    LANGUAGE plpgsql
    AS $$
declare
-- Regclass of the table e.g. public.notes
entity_ regclass = (quote_ident(wal ->> 'schema') || '.' || quote_ident(wal ->> 'table'))::regclass;

-- I, U, D, T: insert, update ...
action realtime.action = (
    case wal ->> 'action'
        when 'I' then 'INSERT'
        when 'U' then 'UPDATE'
        when 'D' then 'DELETE'
        else 'ERROR'
    end
);

-- Is row level security enabled for the table
is_rls_enabled bool = relrowsecurity from pg_class where oid = entity_;

subscriptions realtime.subscription[] = array_agg(subs)
    from
        realtime.subscription subs
    where
        subs.entity = entity_;

-- Subscription vars
roles regrole[] = array_agg(distinct us.claims_role::text)
    from
        unnest(subscriptions) us;

working_role regrole;
claimed_role regrole;
claims jsonb;

subscription_id uuid;
subscription_has_access bool;
visible_to_subscription_ids uuid[] = '{}';

-- structured info for wal's columns
columns realtime.wal_column[];
-- previous identity values for update/delete
old_columns realtime.wal_column[];

error_record_exceeds_max_size boolean = octet_length(wal::text) > max_record_bytes;

-- Primary jsonb output for record
output jsonb;

begin
perform set_config('role', null, true);

columns =
    array_agg(
        (
            x->>'name',
            x->>'type',
            x->>'typeoid',
            realtime.cast(
                (x->'value') #>> '{}',
                coalesce(
                    (x->>'typeoid')::regtype, -- null when wal2json version <= 2.4
                    (x->>'type')::regtype
                )
            ),
            (pks ->> 'name') is not null,
            true
        )::realtime.wal_column
    )
    from
        jsonb_array_elements(wal -> 'columns') x
        left join jsonb_array_elements(wal -> 'pk') pks
            on (x ->> 'name') = (pks ->> 'name');

old_columns =
    array_agg(
        (
            x->>'name',
            x->>'type',
            x->>'typeoid',
            realtime.cast(
                (x->'value') #>> '{}',
                coalesce(
                    (x->>'typeoid')::regtype, -- null when wal2json version <= 2.4
                    (x->>'type')::regtype
                )
            ),
            (pks ->> 'name') is not null,
            true
        )::realtime.wal_column
    )
    from
        jsonb_array_elements(wal -> 'identity') x
        left join jsonb_array_elements(wal -> 'pk') pks
            on (x ->> 'name') = (pks ->> 'name');

for working_role in select * from unnest(roles) loop

    -- Update `is_selectable` for columns and old_columns
    columns =
        array_agg(
            (
                c.name,
                c.type_name,
                c.type_oid,
                c.value,
                c.is_pkey,
                pg_catalog.has_column_privilege(working_role, entity_, c.name, 'SELECT')
            )::realtime.wal_column
        )
        from
            unnest(columns) c;

    old_columns =
            array_agg(
                (
                    c.name,
                    c.type_name,
                    c.type_oid,
                    c.value,
                    c.is_pkey,
                    pg_catalog.has_column_privilege(working_role, entity_, c.name, 'SELECT')
                )::realtime.wal_column
            )
            from
                unnest(old_columns) c;

    if action <> 'DELETE' and count(1) = 0 from unnest(columns) c where c.is_pkey then
        return next (
            jsonb_build_object(
                'schema', wal ->> 'schema',
                'table', wal ->> 'table',
                'type', action
            ),
            is_rls_enabled,
            -- subscriptions is already filtered by entity
            (select array_agg(s.subscription_id) from unnest(subscriptions) as s where claims_role = working_role),
            array['Error 400: Bad Request, no primary key']
        )::realtime.wal_rls;

    -- The claims role does not have SELECT permission to the primary key of entity
    elsif action <> 'DELETE' and sum(c.is_selectable::int) <> count(1) from unnest(columns) c where c.is_pkey then
        return next (
            jsonb_build_object(
                'schema', wal ->> 'schema',
                'table', wal ->> 'table',
                'type', action
            ),
            is_rls_enabled,
            (select array_agg(s.subscription_id) from unnest(subscriptions) as s where claims_role = working_role),
            array['Error 401: Unauthorized']
        )::realtime.wal_rls;

    else
        output = jsonb_build_object(
            'schema', wal ->> 'schema',
            'table', wal ->> 'table',
            'type', action,
            'commit_timestamp', to_char(
                ((wal ->> 'timestamp')::timestamptz at time zone 'utc'),
                'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
            ),
            'columns', (
                select
                    jsonb_agg(
                        jsonb_build_object(
                            'name', pa.attname,
                            'type', pt.typname
                        )
                        order by pa.attnum asc
                    )
                from
                    pg_attribute pa
                    join pg_type pt
                        on pa.atttypid = pt.oid
                where
                    attrelid = entity_
                    and attnum > 0
                    and pg_catalog.has_column_privilege(working_role, entity_, pa.attname, 'SELECT')
            )
        )
        -- Add "record" key for insert and update
        || case
            when action in ('INSERT', 'UPDATE') then
                jsonb_build_object(
                    'record',
                    (
                        select
                            jsonb_object_agg(
                                -- if unchanged toast, get column name and value from old record
                                coalesce((c).name, (oc).name),
                                case
                                    when (c).name is null then (oc).value
                                    else (c).value
                                end
                            )
                        from
                            unnest(columns) c
                            full outer join unnest(old_columns) oc
                                on (c).name = (oc).name
                        where
                            coalesce((c).is_selectable, (oc).is_selectable)
                            and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                    )
                )
            else '{}'::jsonb
        end
        -- Add "old_record" key for update and delete
        || case
            when action = 'UPDATE' then
                jsonb_build_object(
                        'old_record',
                        (
                            select jsonb_object_agg((c).name, (c).value)
                            from unnest(old_columns) c
                            where
                                (c).is_selectable
                                and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                        )
                    )
            when action = 'DELETE' then
                jsonb_build_object(
                    'old_record',
                    (
                        select jsonb_object_agg((c).name, (c).value)
                        from unnest(old_columns) c
                        where
                            (c).is_selectable
                            and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                            and ( not is_rls_enabled or (c).is_pkey ) -- if RLS enabled, we can't secure deletes so filter to pkey
                    )
                )
            else '{}'::jsonb
        end;

        -- Create the prepared statement
        if is_rls_enabled and action <> 'DELETE' then
            if (select 1 from pg_prepared_statements where name = 'walrus_rls_stmt' limit 1) > 0 then
                deallocate walrus_rls_stmt;
            end if;
            execute realtime.build_prepared_statement_sql('walrus_rls_stmt', entity_, columns);
        end if;

        visible_to_subscription_ids = '{}';

        for subscription_id, claims in (
                select
                    subs.subscription_id,
                    subs.claims
                from
                    unnest(subscriptions) subs
                where
                    subs.entity = entity_
                    and subs.claims_role = working_role
                    and (
                        realtime.is_visible_through_filters(columns, subs.filters)
                        or (
                          action = 'DELETE'
                          and realtime.is_visible_through_filters(old_columns, subs.filters)
                        )
                    )
        ) loop

            if not is_rls_enabled or action = 'DELETE' then
                visible_to_subscription_ids = visible_to_subscription_ids || subscription_id;
            else
                -- Check if RLS allows the role to see the record
                perform
                    -- Trim leading and trailing quotes from working_role because set_config
                    -- doesn't recognize the role as valid if they are included
                    set_config('role', trim(both '"' from working_role::text), true),
                    set_config('request.jwt.claims', claims::text, true);

                execute 'execute walrus_rls_stmt' into subscription_has_access;

                if subscription_has_access then
                    visible_to_subscription_ids = visible_to_subscription_ids || subscription_id;
                end if;
            end if;
        end loop;

        perform set_config('role', null, true);

        return next (
            output,
            is_rls_enabled,
            visible_to_subscription_ids,
            case
                when error_record_exceeds_max_size then array['Error 413: Payload Too Large']
                else '{}'
            end
        )::realtime.wal_rls;

    end if;
end loop;

perform set_config('role', null, true);
end;
$$;


--
-- Name: broadcast_changes(text, text, text, text, text, record, record, text); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text DEFAULT 'ROW'::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    -- Declare a variable to hold the JSONB representation of the row
    row_data jsonb := '{}'::jsonb;
BEGIN
    IF level = 'STATEMENT' THEN
        RAISE EXCEPTION 'function can only be triggered for each row, not for each statement';
    END IF;
    -- Check the operation type and handle accordingly
    IF operation = 'INSERT' OR operation = 'UPDATE' OR operation = 'DELETE' THEN
        row_data := jsonb_build_object('old_record', OLD, 'record', NEW, 'operation', operation, 'table', table_name, 'schema', table_schema);
        PERFORM realtime.send (row_data, event_name, topic_name);
    ELSE
        RAISE EXCEPTION 'Unexpected operation type: %', operation;
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Failed to process the row: %', SQLERRM;
END;

$$;


--
-- Name: build_prepared_statement_sql(text, regclass, realtime.wal_column[]); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) RETURNS text
    LANGUAGE sql
    AS $$
      /*
      Builds a sql string that, if executed, creates a prepared statement to
      tests retrive a row from *entity* by its primary key columns.
      Example
          select realtime.build_prepared_statement_sql('public.notes', '{"id"}'::text[], '{"bigint"}'::text[])
      */
          select
      'prepare ' || prepared_statement_name || ' as
          select
              exists(
                  select
                      1
                  from
                      ' || entity || '
                  where
                      ' || string_agg(quote_ident(pkc.name) || '=' || quote_nullable(pkc.value #>> '{}') , ' and ') || '
              )'
          from
              unnest(columns) pkc
          where
              pkc.is_pkey
          group by
              entity
      $$;


--
-- Name: cast(text, regtype); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime."cast"(val text, type_ regtype) RETURNS jsonb
    LANGUAGE plpgsql IMMUTABLE
    AS $$
    declare
      res jsonb;
    begin
      execute format('select to_jsonb(%L::'|| type_::text || ')', val)  into res;
      return res;
    end
    $$;


--
-- Name: check_equality_op(realtime.equality_op, regtype, text, text); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE
    AS $$
      /*
      Casts *val_1* and *val_2* as type *type_* and check the *op* condition for truthiness
      */
      declare
          op_symbol text = (
              case
                  when op = 'eq' then '='
                  when op = 'neq' then '!='
                  when op = 'lt' then '<'
                  when op = 'lte' then '<='
                  when op = 'gt' then '>'
                  when op = 'gte' then '>='
                  when op = 'in' then '= any'
                  else 'UNKNOWN OP'
              end
          );
          res boolean;
      begin
          execute format(
              'select %L::'|| type_::text || ' ' || op_symbol
              || ' ( %L::'
              || (
                  case
                      when op = 'in' then type_::text || '[]'
                      else type_::text end
              )
              || ')', val_1, val_2) into res;
          return res;
      end;
      $$;


--
-- Name: is_visible_through_filters(realtime.wal_column[], realtime.user_defined_filter[]); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    AS $_$
    /*
    Should the record be visible (true) or filtered out (false) after *filters* are applied
    */
        select
            -- Default to allowed when no filters present
            $2 is null -- no filters. this should not happen because subscriptions has a default
            or array_length($2, 1) is null -- array length of an empty array is null
            or bool_and(
                coalesce(
                    realtime.check_equality_op(
                        op:=f.op,
                        type_:=coalesce(
                            col.type_oid::regtype, -- null when wal2json version <= 2.4
                            col.type_name::regtype
                        ),
                        -- cast jsonb to text
                        val_1:=col.value #>> '{}',
                        val_2:=f.value
                    ),
                    false -- if null, filter does not match
                )
            )
        from
            unnest(filters) f
            join unnest(columns) col
                on f.column_name = col.name;
    $_$;


--
-- Name: list_changes(name, name, integer, integer); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) RETURNS SETOF realtime.wal_rls
    LANGUAGE sql
    AS $$
      with pub as (
        select
          concat_ws(
            ',',
            case when bool_or(pubinsert) then 'insert' else null end,
            case when bool_or(pubupdate) then 'update' else null end,
            case when bool_or(pubdelete) then 'delete' else null end
          ) as w2j_actions,
          coalesce(
            string_agg(
              realtime.quote_wal2json(format('%I.%I', schemaname, tablename)::regclass),
              ','
            ) filter (where ppt.tablename is not null and ppt.tablename not like '% %'),
            ''
          ) w2j_add_tables
        from
          pg_publication pp
          left join pg_publication_tables ppt
            on pp.pubname = ppt.pubname
        where
          pp.pubname = publication
        group by
          pp.pubname
        limit 1
      ),
      w2j as (
        select
          x.*, pub.w2j_add_tables
        from
          pub,
          pg_logical_slot_get_changes(
            slot_name, null, max_changes,
            'include-pk', 'true',
            'include-transaction', 'false',
            'include-timestamp', 'true',
            'include-type-oids', 'true',
            'format-version', '2',
            'actions', pub.w2j_actions,
            'add-tables', pub.w2j_add_tables
          ) x
      )
      select
        xyz.wal,
        xyz.is_rls_enabled,
        xyz.subscription_ids,
        xyz.errors
      from
        w2j,
        realtime.apply_rls(
          wal := w2j.data::jsonb,
          max_record_bytes := max_record_bytes
        ) xyz(wal, is_rls_enabled, subscription_ids, errors)
      where
        w2j.w2j_add_tables <> ''
        and xyz.subscription_ids[1] is not null
    $$;


--
-- Name: quote_wal2json(regclass); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.quote_wal2json(entity regclass) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT
    AS $$
      select
        (
          select string_agg('' || ch,'')
          from unnest(string_to_array(nsp.nspname::text, null)) with ordinality x(ch, idx)
          where
            not (x.idx = 1 and x.ch = '"')
            and not (
              x.idx = array_length(string_to_array(nsp.nspname::text, null), 1)
              and x.ch = '"'
            )
        )
        || '.'
        || (
          select string_agg('' || ch,'')
          from unnest(string_to_array(pc.relname::text, null)) with ordinality x(ch, idx)
          where
            not (x.idx = 1 and x.ch = '"')
            and not (
              x.idx = array_length(string_to_array(nsp.nspname::text, null), 1)
              and x.ch = '"'
            )
          )
      from
        pg_class pc
        join pg_namespace nsp
          on pc.relnamespace = nsp.oid
      where
        pc.oid = entity
    $$;


--
-- Name: send(jsonb, text, text, boolean); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean DEFAULT true) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  BEGIN
    -- Set the topic configuration
    EXECUTE format('SET LOCAL realtime.topic TO %L', topic);

    -- Attempt to insert the message
    INSERT INTO realtime.messages (payload, event, topic, private, extension)
    VALUES (payload, event, topic, private, 'broadcast');
  EXCEPTION
    WHEN OTHERS THEN
      -- Capture and notify the error
      RAISE WARNING 'ErrorSendingBroadcastMessage: %', SQLERRM;
  END;
END;
$$;


--
-- Name: subscription_check_filters(); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.subscription_check_filters() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    /*
    Validates that the user defined filters for a subscription:
    - refer to valid columns that the claimed role may access
    - values are coercable to the correct column type
    */
    declare
        col_names text[] = coalesce(
                array_agg(c.column_name order by c.ordinal_position),
                '{}'::text[]
            )
            from
                information_schema.columns c
            where
                format('%I.%I', c.table_schema, c.table_name)::regclass = new.entity
                and pg_catalog.has_column_privilege(
                    (new.claims ->> 'role'),
                    format('%I.%I', c.table_schema, c.table_name)::regclass,
                    c.column_name,
                    'SELECT'
                );
        filter realtime.user_defined_filter;
        col_type regtype;

        in_val jsonb;
    begin
        for filter in select * from unnest(new.filters) loop
            -- Filtered column is valid
            if not filter.column_name = any(col_names) then
                raise exception 'invalid column for filter %', filter.column_name;
            end if;

            -- Type is sanitized and safe for string interpolation
            col_type = (
                select atttypid::regtype
                from pg_catalog.pg_attribute
                where attrelid = new.entity
                      and attname = filter.column_name
            );
            if col_type is null then
                raise exception 'failed to lookup type for column %', filter.column_name;
            end if;

            -- Set maximum number of entries for in filter
            if filter.op = 'in'::realtime.equality_op then
                in_val = realtime.cast(filter.value, (col_type::text || '[]')::regtype);
                if coalesce(jsonb_array_length(in_val), 0) > 100 then
                    raise exception 'too many values for `in` filter. Maximum 100';
                end if;
            else
                -- raises an exception if value is not coercable to type
                perform realtime.cast(filter.value, col_type);
            end if;

        end loop;

        -- Apply consistent order to filters so the unique constraint on
        -- (subscription_id, entity, filters) can't be tricked by a different filter order
        new.filters = coalesce(
            array_agg(f order by f.column_name, f.op, f.value),
            '{}'
        ) from unnest(new.filters) f;

        return new;
    end;
    $$;


--
-- Name: to_regrole(text); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.to_regrole(role_name text) RETURNS regrole
    LANGUAGE sql IMMUTABLE
    AS $$ select role_name::regrole $$;


--
-- Name: topic(); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.topic() RETURNS text
    LANGUAGE sql STABLE
    AS $$
select nullif(current_setting('realtime.topic', true), '')::text;
$$;


--
-- Name: add_prefixes(text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.add_prefixes(_bucket_id text, _name text) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    prefixes text[];
BEGIN
    prefixes := "storage"."get_prefixes"("_name");

    IF array_length(prefixes, 1) > 0 THEN
        INSERT INTO storage.prefixes (name, bucket_id)
        SELECT UNNEST(prefixes) as name, "_bucket_id" ON CONFLICT DO NOTHING;
    END IF;
END;
$$;


--
-- Name: can_insert_object(text, text, uuid, jsonb); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.can_insert_object(bucketid text, name text, owner uuid, metadata jsonb) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  INSERT INTO "storage"."objects" ("bucket_id", "name", "owner", "metadata") VALUES (bucketid, name, owner, metadata);
  -- hack to rollback the successful insert
  RAISE sqlstate 'PT200' using
  message = 'ROLLBACK',
  detail = 'rollback successful insert';
END
$$;


--
-- Name: delete_leaf_prefixes(text[], text[]); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.delete_leaf_prefixes(bucket_ids text[], names text[]) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_rows_deleted integer;
BEGIN
    LOOP
        WITH candidates AS (
            SELECT DISTINCT
                t.bucket_id,
                unnest(storage.get_prefixes(t.name)) AS name
            FROM unnest(bucket_ids, names) AS t(bucket_id, name)
        ),
        uniq AS (
             SELECT
                 bucket_id,
                 name,
                 storage.get_level(name) AS level
             FROM candidates
             WHERE name <> ''
             GROUP BY bucket_id, name
        ),
        leaf AS (
             SELECT
                 p.bucket_id,
                 p.name,
                 p.level
             FROM storage.prefixes AS p
                  JOIN uniq AS u
                       ON u.bucket_id = p.bucket_id
                           AND u.name = p.name
                           AND u.level = p.level
             WHERE NOT EXISTS (
                 SELECT 1
                 FROM storage.objects AS o
                 WHERE o.bucket_id = p.bucket_id
                   AND o.level = p.level + 1
                   AND o.name COLLATE "C" LIKE p.name || '/%'
             )
             AND NOT EXISTS (
                 SELECT 1
                 FROM storage.prefixes AS c
                 WHERE c.bucket_id = p.bucket_id
                   AND c.level = p.level + 1
                   AND c.name COLLATE "C" LIKE p.name || '/%'
             )
        )
        DELETE
        FROM storage.prefixes AS p
            USING leaf AS l
        WHERE p.bucket_id = l.bucket_id
          AND p.name = l.name
          AND p.level = l.level;

        GET DIAGNOSTICS v_rows_deleted = ROW_COUNT;
        EXIT WHEN v_rows_deleted = 0;
    END LOOP;
END;
$$;


--
-- Name: delete_prefix(text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.delete_prefix(_bucket_id text, _name text) RETURNS boolean
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    -- Check if we can delete the prefix
    IF EXISTS(
        SELECT FROM "storage"."prefixes"
        WHERE "prefixes"."bucket_id" = "_bucket_id"
          AND level = "storage"."get_level"("_name") + 1
          AND "prefixes"."name" COLLATE "C" LIKE "_name" || '/%'
        LIMIT 1
    )
    OR EXISTS(
        SELECT FROM "storage"."objects"
        WHERE "objects"."bucket_id" = "_bucket_id"
          AND "storage"."get_level"("objects"."name") = "storage"."get_level"("_name") + 1
          AND "objects"."name" COLLATE "C" LIKE "_name" || '/%'
        LIMIT 1
    ) THEN
    -- There are sub-objects, skip deletion
    RETURN false;
    ELSE
        DELETE FROM "storage"."prefixes"
        WHERE "prefixes"."bucket_id" = "_bucket_id"
          AND level = "storage"."get_level"("_name")
          AND "prefixes"."name" = "_name";
        RETURN true;
    END IF;
END;
$$;


--
-- Name: delete_prefix_hierarchy_trigger(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.delete_prefix_hierarchy_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    prefix text;
BEGIN
    prefix := "storage"."get_prefix"(OLD."name");

    IF coalesce(prefix, '') != '' THEN
        PERFORM "storage"."delete_prefix"(OLD."bucket_id", prefix);
    END IF;

    RETURN OLD;
END;
$$;


--
-- Name: enforce_bucket_name_length(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.enforce_bucket_name_length() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
    if length(new.name) > 100 then
        raise exception 'bucket name "%" is too long (% characters). Max is 100.', new.name, length(new.name);
    end if;
    return new;
end;
$$;


--
-- Name: extension(text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.extension(name text) RETURNS text
    LANGUAGE plpgsql IMMUTABLE
    AS $$
DECLARE
    _parts text[];
    _filename text;
BEGIN
    SELECT string_to_array(name, '/') INTO _parts;
    SELECT _parts[array_length(_parts,1)] INTO _filename;
    RETURN reverse(split_part(reverse(_filename), '.', 1));
END
$$;


--
-- Name: filename(text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.filename(name text) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
_parts text[];
BEGIN
	select string_to_array(name, '/') into _parts;
	return _parts[array_length(_parts,1)];
END
$$;


--
-- Name: foldername(text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.foldername(name text) RETURNS text[]
    LANGUAGE plpgsql IMMUTABLE
    AS $$
DECLARE
    _parts text[];
BEGIN
    -- Split on "/" to get path segments
    SELECT string_to_array(name, '/') INTO _parts;
    -- Return everything except the last segment
    RETURN _parts[1 : array_length(_parts,1) - 1];
END
$$;


--
-- Name: get_level(text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.get_level(name text) RETURNS integer
    LANGUAGE sql IMMUTABLE STRICT
    AS $$
SELECT array_length(string_to_array("name", '/'), 1);
$$;


--
-- Name: get_prefix(text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.get_prefix(name text) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT
    AS $_$
SELECT
    CASE WHEN strpos("name", '/') > 0 THEN
             regexp_replace("name", '[\/]{1}[^\/]+\/?$', '')
         ELSE
             ''
        END;
$_$;


--
-- Name: get_prefixes(text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.get_prefixes(name text) RETURNS text[]
    LANGUAGE plpgsql IMMUTABLE STRICT
    AS $$
DECLARE
    parts text[];
    prefixes text[];
    prefix text;
BEGIN
    -- Split the name into parts by '/'
    parts := string_to_array("name", '/');
    prefixes := '{}';

    -- Construct the prefixes, stopping one level below the last part
    FOR i IN 1..array_length(parts, 1) - 1 LOOP
            prefix := array_to_string(parts[1:i], '/');
            prefixes := array_append(prefixes, prefix);
    END LOOP;

    RETURN prefixes;
END;
$$;


--
-- Name: get_size_by_bucket(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.get_size_by_bucket() RETURNS TABLE(size bigint, bucket_id text)
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    return query
        select sum((metadata->>'size')::bigint) as size, obj.bucket_id
        from "storage".objects as obj
        group by obj.bucket_id;
END
$$;


--
-- Name: list_multipart_uploads_with_delimiter(text, text, text, integer, text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.list_multipart_uploads_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer DEFAULT 100, next_key_token text DEFAULT ''::text, next_upload_token text DEFAULT ''::text) RETURNS TABLE(key text, id text, created_at timestamp with time zone)
    LANGUAGE plpgsql
    AS $_$
BEGIN
    RETURN QUERY EXECUTE
        'SELECT DISTINCT ON(key COLLATE "C") * from (
            SELECT
                CASE
                    WHEN position($2 IN substring(key from length($1) + 1)) > 0 THEN
                        substring(key from 1 for length($1) + position($2 IN substring(key from length($1) + 1)))
                    ELSE
                        key
                END AS key, id, created_at
            FROM
                storage.s3_multipart_uploads
            WHERE
                bucket_id = $5 AND
                key ILIKE $1 || ''%'' AND
                CASE
                    WHEN $4 != '''' AND $6 = '''' THEN
                        CASE
                            WHEN position($2 IN substring(key from length($1) + 1)) > 0 THEN
                                substring(key from 1 for length($1) + position($2 IN substring(key from length($1) + 1))) COLLATE "C" > $4
                            ELSE
                                key COLLATE "C" > $4
                            END
                    ELSE
                        true
                END AND
                CASE
                    WHEN $6 != '''' THEN
                        id COLLATE "C" > $6
                    ELSE
                        true
                    END
            ORDER BY
                key COLLATE "C" ASC, created_at ASC) as e order by key COLLATE "C" LIMIT $3'
        USING prefix_param, delimiter_param, max_keys, next_key_token, bucket_id, next_upload_token;
END;
$_$;


--
-- Name: list_objects_with_delimiter(text, text, text, integer, text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.list_objects_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer DEFAULT 100, start_after text DEFAULT ''::text, next_token text DEFAULT ''::text) RETURNS TABLE(name text, id uuid, metadata jsonb, updated_at timestamp with time zone)
    LANGUAGE plpgsql
    AS $_$
BEGIN
    RETURN QUERY EXECUTE
        'SELECT DISTINCT ON(name COLLATE "C") * from (
            SELECT
                CASE
                    WHEN position($2 IN substring(name from length($1) + 1)) > 0 THEN
                        substring(name from 1 for length($1) + position($2 IN substring(name from length($1) + 1)))
                    ELSE
                        name
                END AS name, id, metadata, updated_at
            FROM
                storage.objects
            WHERE
                bucket_id = $5 AND
                name ILIKE $1 || ''%'' AND
                CASE
                    WHEN $6 != '''' THEN
                    name COLLATE "C" > $6
                ELSE true END
                AND CASE
                    WHEN $4 != '''' THEN
                        CASE
                            WHEN position($2 IN substring(name from length($1) + 1)) > 0 THEN
                                substring(name from 1 for length($1) + position($2 IN substring(name from length($1) + 1))) COLLATE "C" > $4
                            ELSE
                                name COLLATE "C" > $4
                            END
                    ELSE
                        true
                END
            ORDER BY
                name COLLATE "C" ASC) as e order by name COLLATE "C" LIMIT $3'
        USING prefix_param, delimiter_param, max_keys, next_token, bucket_id, start_after;
END;
$_$;


--
-- Name: lock_top_prefixes(text[], text[]); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.lock_top_prefixes(bucket_ids text[], names text[]) RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_bucket text;
    v_top text;
BEGIN
    FOR v_bucket, v_top IN
        SELECT DISTINCT t.bucket_id,
            split_part(t.name, '/', 1) AS top
        FROM unnest(bucket_ids, names) AS t(bucket_id, name)
        WHERE t.name <> ''
        ORDER BY 1, 2
        LOOP
            PERFORM pg_advisory_xact_lock(hashtextextended(v_bucket || '/' || v_top, 0));
        END LOOP;
END;
$$;


--
-- Name: objects_delete_cleanup(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.objects_delete_cleanup() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_bucket_ids text[];
    v_names      text[];
BEGIN
    IF current_setting('storage.gc.prefixes', true) = '1' THEN
        RETURN NULL;
    END IF;

    PERFORM set_config('storage.gc.prefixes', '1', true);

    SELECT COALESCE(array_agg(d.bucket_id), '{}'),
           COALESCE(array_agg(d.name), '{}')
    INTO v_bucket_ids, v_names
    FROM deleted AS d
    WHERE d.name <> '';

    PERFORM storage.lock_top_prefixes(v_bucket_ids, v_names);
    PERFORM storage.delete_leaf_prefixes(v_bucket_ids, v_names);

    RETURN NULL;
END;
$$;


--
-- Name: objects_insert_prefix_trigger(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.objects_insert_prefix_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    PERFORM "storage"."add_prefixes"(NEW."bucket_id", NEW."name");
    NEW.level := "storage"."get_level"(NEW."name");

    RETURN NEW;
END;
$$;


--
-- Name: objects_update_cleanup(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.objects_update_cleanup() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    -- NEW - OLD (destinations to create prefixes for)
    v_add_bucket_ids text[];
    v_add_names      text[];

    -- OLD - NEW (sources to prune)
    v_src_bucket_ids text[];
    v_src_names      text[];
BEGIN
    IF TG_OP <> 'UPDATE' THEN
        RETURN NULL;
    END IF;

    -- 1) Compute NEW−OLD (added paths) and OLD−NEW (moved-away paths)
    WITH added AS (
        SELECT n.bucket_id, n.name
        FROM new_rows n
        WHERE n.name <> '' AND position('/' in n.name) > 0
        EXCEPT
        SELECT o.bucket_id, o.name FROM old_rows o WHERE o.name <> ''
    ),
    moved AS (
         SELECT o.bucket_id, o.name
         FROM old_rows o
         WHERE o.name <> ''
         EXCEPT
         SELECT n.bucket_id, n.name FROM new_rows n WHERE n.name <> ''
    )
    SELECT
        -- arrays for ADDED (dest) in stable order
        COALESCE( (SELECT array_agg(a.bucket_id ORDER BY a.bucket_id, a.name) FROM added a), '{}' ),
        COALESCE( (SELECT array_agg(a.name      ORDER BY a.bucket_id, a.name) FROM added a), '{}' ),
        -- arrays for MOVED (src) in stable order
        COALESCE( (SELECT array_agg(m.bucket_id ORDER BY m.bucket_id, m.name) FROM moved m), '{}' ),
        COALESCE( (SELECT array_agg(m.name      ORDER BY m.bucket_id, m.name) FROM moved m), '{}' )
    INTO v_add_bucket_ids, v_add_names, v_src_bucket_ids, v_src_names;

    -- Nothing to do?
    IF (array_length(v_add_bucket_ids, 1) IS NULL) AND (array_length(v_src_bucket_ids, 1) IS NULL) THEN
        RETURN NULL;
    END IF;

    -- 2) Take per-(bucket, top) locks: ALL prefixes in consistent global order to prevent deadlocks
    DECLARE
        v_all_bucket_ids text[];
        v_all_names text[];
    BEGIN
        -- Combine source and destination arrays for consistent lock ordering
        v_all_bucket_ids := COALESCE(v_src_bucket_ids, '{}') || COALESCE(v_add_bucket_ids, '{}');
        v_all_names := COALESCE(v_src_names, '{}') || COALESCE(v_add_names, '{}');

        -- Single lock call ensures consistent global ordering across all transactions
        IF array_length(v_all_bucket_ids, 1) IS NOT NULL THEN
            PERFORM storage.lock_top_prefixes(v_all_bucket_ids, v_all_names);
        END IF;
    END;

    -- 3) Create destination prefixes (NEW−OLD) BEFORE pruning sources
    IF array_length(v_add_bucket_ids, 1) IS NOT NULL THEN
        WITH candidates AS (
            SELECT DISTINCT t.bucket_id, unnest(storage.get_prefixes(t.name)) AS name
            FROM unnest(v_add_bucket_ids, v_add_names) AS t(bucket_id, name)
            WHERE name <> ''
        )
        INSERT INTO storage.prefixes (bucket_id, name)
        SELECT c.bucket_id, c.name
        FROM candidates c
        ON CONFLICT DO NOTHING;
    END IF;

    -- 4) Prune source prefixes bottom-up for OLD−NEW
    IF array_length(v_src_bucket_ids, 1) IS NOT NULL THEN
        -- re-entrancy guard so DELETE on prefixes won't recurse
        IF current_setting('storage.gc.prefixes', true) <> '1' THEN
            PERFORM set_config('storage.gc.prefixes', '1', true);
        END IF;

        PERFORM storage.delete_leaf_prefixes(v_src_bucket_ids, v_src_names);
    END IF;

    RETURN NULL;
END;
$$;


--
-- Name: objects_update_level_trigger(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.objects_update_level_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Ensure this is an update operation and the name has changed
    IF TG_OP = 'UPDATE' AND (NEW."name" <> OLD."name" OR NEW."bucket_id" <> OLD."bucket_id") THEN
        -- Set the new level
        NEW."level" := "storage"."get_level"(NEW."name");
    END IF;
    RETURN NEW;
END;
$$;


--
-- Name: objects_update_prefix_trigger(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.objects_update_prefix_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    old_prefixes TEXT[];
BEGIN
    -- Ensure this is an update operation and the name has changed
    IF TG_OP = 'UPDATE' AND (NEW."name" <> OLD."name" OR NEW."bucket_id" <> OLD."bucket_id") THEN
        -- Retrieve old prefixes
        old_prefixes := "storage"."get_prefixes"(OLD."name");

        -- Remove old prefixes that are only used by this object
        WITH all_prefixes as (
            SELECT unnest(old_prefixes) as prefix
        ),
        can_delete_prefixes as (
             SELECT prefix
             FROM all_prefixes
             WHERE NOT EXISTS (
                 SELECT 1 FROM "storage"."objects"
                 WHERE "bucket_id" = OLD."bucket_id"
                   AND "name" <> OLD."name"
                   AND "name" LIKE (prefix || '%')
             )
         )
        DELETE FROM "storage"."prefixes" WHERE name IN (SELECT prefix FROM can_delete_prefixes);

        -- Add new prefixes
        PERFORM "storage"."add_prefixes"(NEW."bucket_id", NEW."name");
    END IF;
    -- Set the new level
    NEW."level" := "storage"."get_level"(NEW."name");

    RETURN NEW;
END;
$$;


--
-- Name: operation(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.operation() RETURNS text
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    RETURN current_setting('storage.operation', true);
END;
$$;


--
-- Name: prefixes_delete_cleanup(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.prefixes_delete_cleanup() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
DECLARE
    v_bucket_ids text[];
    v_names      text[];
BEGIN
    IF current_setting('storage.gc.prefixes', true) = '1' THEN
        RETURN NULL;
    END IF;

    PERFORM set_config('storage.gc.prefixes', '1', true);

    SELECT COALESCE(array_agg(d.bucket_id), '{}'),
           COALESCE(array_agg(d.name), '{}')
    INTO v_bucket_ids, v_names
    FROM deleted AS d
    WHERE d.name <> '';

    PERFORM storage.lock_top_prefixes(v_bucket_ids, v_names);
    PERFORM storage.delete_leaf_prefixes(v_bucket_ids, v_names);

    RETURN NULL;
END;
$$;


--
-- Name: prefixes_insert_trigger(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.prefixes_insert_trigger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    PERFORM "storage"."add_prefixes"(NEW."bucket_id", NEW."name");
    RETURN NEW;
END;
$$;


--
-- Name: search(text, text, integer, integer, integer, text, text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.search(prefix text, bucketname text, limits integer DEFAULT 100, levels integer DEFAULT 1, offsets integer DEFAULT 0, search text DEFAULT ''::text, sortcolumn text DEFAULT 'name'::text, sortorder text DEFAULT 'asc'::text) RETURNS TABLE(name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql
    AS $$
declare
    can_bypass_rls BOOLEAN;
begin
    SELECT rolbypassrls
    INTO can_bypass_rls
    FROM pg_roles
    WHERE rolname = coalesce(nullif(current_setting('role', true), 'none'), current_user);

    IF can_bypass_rls THEN
        RETURN QUERY SELECT * FROM storage.search_v1_optimised(prefix, bucketname, limits, levels, offsets, search, sortcolumn, sortorder);
    ELSE
        RETURN QUERY SELECT * FROM storage.search_legacy_v1(prefix, bucketname, limits, levels, offsets, search, sortcolumn, sortorder);
    END IF;
end;
$$;


--
-- Name: search_legacy_v1(text, text, integer, integer, integer, text, text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.search_legacy_v1(prefix text, bucketname text, limits integer DEFAULT 100, levels integer DEFAULT 1, offsets integer DEFAULT 0, search text DEFAULT ''::text, sortcolumn text DEFAULT 'name'::text, sortorder text DEFAULT 'asc'::text) RETURNS TABLE(name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql STABLE
    AS $_$
declare
    v_order_by text;
    v_sort_order text;
begin
    case
        when sortcolumn = 'name' then
            v_order_by = 'name';
        when sortcolumn = 'updated_at' then
            v_order_by = 'updated_at';
        when sortcolumn = 'created_at' then
            v_order_by = 'created_at';
        when sortcolumn = 'last_accessed_at' then
            v_order_by = 'last_accessed_at';
        else
            v_order_by = 'name';
        end case;

    case
        when sortorder = 'asc' then
            v_sort_order = 'asc';
        when sortorder = 'desc' then
            v_sort_order = 'desc';
        else
            v_sort_order = 'asc';
        end case;

    v_order_by = v_order_by || ' ' || v_sort_order;

    return query execute
        'with folders as (
           select path_tokens[$1] as folder
           from storage.objects
             where objects.name ilike $2 || $3 || ''%''
               and bucket_id = $4
               and array_length(objects.path_tokens, 1) <> $1
           group by folder
           order by folder ' || v_sort_order || '
     )
     (select folder as "name",
            null as id,
            null as updated_at,
            null as created_at,
            null as last_accessed_at,
            null as metadata from folders)
     union all
     (select path_tokens[$1] as "name",
            id,
            updated_at,
            created_at,
            last_accessed_at,
            metadata
     from storage.objects
     where objects.name ilike $2 || $3 || ''%''
       and bucket_id = $4
       and array_length(objects.path_tokens, 1) = $1
     order by ' || v_order_by || ')
     limit $5
     offset $6' using levels, prefix, search, bucketname, limits, offsets;
end;
$_$;


--
-- Name: search_v1_optimised(text, text, integer, integer, integer, text, text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.search_v1_optimised(prefix text, bucketname text, limits integer DEFAULT 100, levels integer DEFAULT 1, offsets integer DEFAULT 0, search text DEFAULT ''::text, sortcolumn text DEFAULT 'name'::text, sortorder text DEFAULT 'asc'::text) RETURNS TABLE(name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql STABLE
    AS $_$
declare
    v_order_by text;
    v_sort_order text;
begin
    case
        when sortcolumn = 'name' then
            v_order_by = 'name';
        when sortcolumn = 'updated_at' then
            v_order_by = 'updated_at';
        when sortcolumn = 'created_at' then
            v_order_by = 'created_at';
        when sortcolumn = 'last_accessed_at' then
            v_order_by = 'last_accessed_at';
        else
            v_order_by = 'name';
        end case;

    case
        when sortorder = 'asc' then
            v_sort_order = 'asc';
        when sortorder = 'desc' then
            v_sort_order = 'desc';
        else
            v_sort_order = 'asc';
        end case;

    v_order_by = v_order_by || ' ' || v_sort_order;

    return query execute
        'with folders as (
           select (string_to_array(name, ''/''))[level] as name
           from storage.prefixes
             where lower(prefixes.name) like lower($2 || $3) || ''%''
               and bucket_id = $4
               and level = $1
           order by name ' || v_sort_order || '
     )
     (select name,
            null as id,
            null as updated_at,
            null as created_at,
            null as last_accessed_at,
            null as metadata from folders)
     union all
     (select path_tokens[level] as "name",
            id,
            updated_at,
            created_at,
            last_accessed_at,
            metadata
     from storage.objects
     where lower(objects.name) like lower($2 || $3) || ''%''
       and bucket_id = $4
       and level = $1
     order by ' || v_order_by || ')
     limit $5
     offset $6' using levels, prefix, search, bucketname, limits, offsets;
end;
$_$;


--
-- Name: search_v2(text, text, integer, integer, text, text, text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.search_v2(prefix text, bucket_name text, limits integer DEFAULT 100, levels integer DEFAULT 1, start_after text DEFAULT ''::text, sort_order text DEFAULT 'asc'::text, sort_column text DEFAULT 'name'::text, sort_column_after text DEFAULT ''::text) RETURNS TABLE(key text, name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql STABLE
    AS $_$
DECLARE
    sort_col text;
    sort_ord text;
    cursor_op text;
    cursor_expr text;
    sort_expr text;
BEGIN
    -- Validate sort_order
    sort_ord := lower(sort_order);
    IF sort_ord NOT IN ('asc', 'desc') THEN
        sort_ord := 'asc';
    END IF;

    -- Determine cursor comparison operator
    IF sort_ord = 'asc' THEN
        cursor_op := '>';
    ELSE
        cursor_op := '<';
    END IF;
    
    sort_col := lower(sort_column);
    -- Validate sort column  
    IF sort_col IN ('updated_at', 'created_at') THEN
        cursor_expr := format(
            '($5 = '''' OR ROW(date_trunc(''milliseconds'', %I), name COLLATE "C") %s ROW(COALESCE(NULLIF($6, '''')::timestamptz, ''epoch''::timestamptz), $5))',
            sort_col, cursor_op
        );
        sort_expr := format(
            'COALESCE(date_trunc(''milliseconds'', %I), ''epoch''::timestamptz) %s, name COLLATE "C" %s',
            sort_col, sort_ord, sort_ord
        );
    ELSE
        cursor_expr := format('($5 = '''' OR name COLLATE "C" %s $5)', cursor_op);
        sort_expr := format('name COLLATE "C" %s', sort_ord);
    END IF;

    RETURN QUERY EXECUTE format(
        $sql$
        SELECT * FROM (
            (
                SELECT
                    split_part(name, '/', $4) AS key,
                    name,
                    NULL::uuid AS id,
                    updated_at,
                    created_at,
                    NULL::timestamptz AS last_accessed_at,
                    NULL::jsonb AS metadata
                FROM storage.prefixes
                WHERE name COLLATE "C" LIKE $1 || '%%'
                    AND bucket_id = $2
                    AND level = $4
                    AND %s
                ORDER BY %s
                LIMIT $3
            )
            UNION ALL
            (
                SELECT
                    split_part(name, '/', $4) AS key,
                    name,
                    id,
                    updated_at,
                    created_at,
                    last_accessed_at,
                    metadata
                FROM storage.objects
                WHERE name COLLATE "C" LIKE $1 || '%%'
                    AND bucket_id = $2
                    AND level = $4
                    AND %s
                ORDER BY %s
                LIMIT $3
            )
        ) obj
        ORDER BY %s
        LIMIT $3
        $sql$,
        cursor_expr,    -- prefixes WHERE
        sort_expr,      -- prefixes ORDER BY
        cursor_expr,    -- objects WHERE
        sort_expr,      -- objects ORDER BY
        sort_expr       -- final ORDER BY
    )
    USING prefix, bucket_name, limits, levels, start_after, sort_column_after;
END;
$_$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW; 
END;
$$;


--
-- Name: http_request(); Type: FUNCTION; Schema: supabase_functions; Owner: -
--

CREATE FUNCTION supabase_functions.http_request() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'supabase_functions'
    AS $$
  DECLARE
    request_id bigint;
    payload jsonb;
    url text := TG_ARGV[0]::text;
    method text := TG_ARGV[1]::text;
    headers jsonb DEFAULT '{}'::jsonb;
    params jsonb DEFAULT '{}'::jsonb;
    timeout_ms integer DEFAULT 1000;
  BEGIN
    IF url IS NULL OR url = 'null' THEN
      RAISE EXCEPTION 'url argument is missing';
    END IF;

    IF method IS NULL OR method = 'null' THEN
      RAISE EXCEPTION 'method argument is missing';
    END IF;

    IF TG_ARGV[2] IS NULL OR TG_ARGV[2] = 'null' THEN
      headers = '{"Content-Type": "application/json"}'::jsonb;
    ELSE
      headers = TG_ARGV[2]::jsonb;
    END IF;

    IF TG_ARGV[3] IS NULL OR TG_ARGV[3] = 'null' THEN
      params = '{}'::jsonb;
    ELSE
      params = TG_ARGV[3]::jsonb;
    END IF;

    IF TG_ARGV[4] IS NULL OR TG_ARGV[4] = 'null' THEN
      timeout_ms = 1000;
    ELSE
      timeout_ms = TG_ARGV[4]::integer;
    END IF;

    CASE
      WHEN method = 'GET' THEN
        SELECT http_get INTO request_id FROM net.http_get(
          url,
          params,
          headers,
          timeout_ms
        );
      WHEN method = 'POST' THEN
        payload = jsonb_build_object(
          'old_record', OLD,
          'record', NEW,
          'type', TG_OP,
          'table', TG_TABLE_NAME,
          'schema', TG_TABLE_SCHEMA
        );

        SELECT http_post INTO request_id FROM net.http_post(
          url,
          payload,
          params,
          headers,
          timeout_ms
        );
      ELSE
        RAISE EXCEPTION 'method argument % is invalid', method;
    END CASE;

    INSERT INTO supabase_functions.hooks
      (hook_table_id, hook_name, request_id)
    VALUES
      (TG_RELID, TG_NAME, request_id);

    RETURN NEW;
  END
$$;


--
-- Name: _to_base36(bigint, integer); Type: FUNCTION; Schema: util_mig; Owner: -
--

CREATE FUNCTION util_mig._to_base36(n bigint, width integer DEFAULT 4) RETURNS text
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
--

    id uuid NOT NULL,
    type text,
    settings jsonb,
    tenant_external_id text,
    inserted_at timestamp(0) without time zone NOT NULL,
    updated_at timestamp(0) without time zone NOT NULL
);


--
--

    version bigint NOT NULL,
    inserted_at timestamp(0) without time zone
);


--
--

    id uuid NOT NULL,
    name text,
    external_id text,
    jwt_secret text,
    max_concurrent_users integer DEFAULT 200 NOT NULL,
    inserted_at timestamp(0) without time zone NOT NULL,
    updated_at timestamp(0) without time zone NOT NULL,
    max_events_per_second integer DEFAULT 100 NOT NULL,
    postgres_cdc_default text DEFAULT 'postgres_cdc_rls'::text,
    max_bytes_per_second integer DEFAULT 100000 NOT NULL,
    max_channels_per_client integer DEFAULT 100 NOT NULL,
    max_joins_per_second integer DEFAULT 500 NOT NULL,
    suspend boolean DEFAULT false,
    jwt_jwks jsonb,
    notify_private_alpha boolean DEFAULT false,
    private_only boolean DEFAULT false NOT NULL,
    migrations_ran integer DEFAULT 0,
    broadcast_adapter character varying(255) DEFAULT 'gen_rpc'::character varying,
    max_presence_events_per_second integer DEFAULT 10000,
    max_payload_size_in_kb integer DEFAULT 3000
);


--
-- Name: writes; Type: TABLE; Schema: audit; Owner: -
--

CREATE TABLE audit.writes (
    id bigint NOT NULL,
    at timestamp with time zone DEFAULT now() NOT NULL,
    table_name text NOT NULL,
    op text NOT NULL,
    user_name text DEFAULT SESSION_USER NOT NULL,
    client_addr inet,
    row_pk text,
    new_row jsonb,
    old_row jsonb,
    app_user text
);


--
-- Name: writes_id_seq; Type: SEQUENCE; Schema: audit; Owner: -
--

CREATE SEQUENCE audit.writes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: writes_id_seq; Type: SEQUENCE OWNED BY; Schema: audit; Owner: -
--

ALTER SEQUENCE audit.writes_id_seq OWNED BY audit.writes.id;


--
-- Name: audit_log_entries; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.audit_log_entries (
    instance_id uuid,
    id uuid NOT NULL,
    payload json,
    created_at timestamp with time zone,
    ip_address character varying(64) DEFAULT ''::character varying NOT NULL
);


--
-- Name: TABLE audit_log_entries; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.audit_log_entries IS 'Auth: Audit trail for user actions.';


--
-- Name: flow_state; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.flow_state (
    id uuid NOT NULL,
    user_id uuid,
    auth_code text NOT NULL,
    code_challenge_method auth.code_challenge_method NOT NULL,
    code_challenge text NOT NULL,
    provider_type text NOT NULL,
    provider_access_token text,
    provider_refresh_token text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    authentication_method text NOT NULL,
    auth_code_issued_at timestamp with time zone
);


--
-- Name: TABLE flow_state; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.flow_state IS 'stores metadata for pkce logins';


--
-- Name: identities; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.identities (
    provider_id text NOT NULL,
    user_id uuid NOT NULL,
    identity_data jsonb NOT NULL,
    provider text NOT NULL,
    last_sign_in_at timestamp with time zone,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    email text GENERATED ALWAYS AS (lower((identity_data ->> 'email'::text))) STORED,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: TABLE identities; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.identities IS 'Auth: Stores identities associated to a user.';


--
-- Name: COLUMN identities.email; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON COLUMN auth.identities.email IS 'Auth: Email is a generated column that references the optional email property in the identity_data';


--
-- Name: instances; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.instances (
    id uuid NOT NULL,
    uuid uuid,
    raw_base_config text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


--
-- Name: TABLE instances; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.instances IS 'Auth: Manages users across multiple sites.';


--
-- Name: mfa_amr_claims; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.mfa_amr_claims (
    session_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    authentication_method text NOT NULL,
    id uuid NOT NULL
);


--
-- Name: TABLE mfa_amr_claims; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.mfa_amr_claims IS 'auth: stores authenticator method reference claims for multi factor authentication';


--
-- Name: mfa_challenges; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.mfa_challenges (
    id uuid NOT NULL,
    factor_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    verified_at timestamp with time zone,
    ip_address inet NOT NULL,
    otp_code text,
    web_authn_session_data jsonb
);


--
-- Name: TABLE mfa_challenges; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.mfa_challenges IS 'auth: stores metadata about challenge requests made';


--
-- Name: mfa_factors; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.mfa_factors (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    friendly_name text,
    factor_type auth.factor_type NOT NULL,
    status auth.factor_status NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    secret text,
    phone text,
    last_challenged_at timestamp with time zone,
    web_authn_credential jsonb,
    web_authn_aaguid uuid
);


--
-- Name: TABLE mfa_factors; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.mfa_factors IS 'auth: stores metadata about factors';


--
-- Name: oauth_authorizations; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.oauth_authorizations (
    id uuid NOT NULL,
    authorization_id text NOT NULL,
    client_id uuid NOT NULL,
    user_id uuid,
    redirect_uri text NOT NULL,
    scope text NOT NULL,
    state text,
    resource text,
    code_challenge text,
    code_challenge_method auth.code_challenge_method,
    response_type auth.oauth_response_type DEFAULT 'code'::auth.oauth_response_type NOT NULL,
    status auth.oauth_authorization_status DEFAULT 'pending'::auth.oauth_authorization_status NOT NULL,
    authorization_code text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone DEFAULT (now() + '00:03:00'::interval) NOT NULL,
    approved_at timestamp with time zone,
    CONSTRAINT oauth_authorizations_authorization_code_length CHECK ((char_length(authorization_code) <= 255)),
    CONSTRAINT oauth_authorizations_code_challenge_length CHECK ((char_length(code_challenge) <= 128)),
    CONSTRAINT oauth_authorizations_expires_at_future CHECK ((expires_at > created_at)),
    CONSTRAINT oauth_authorizations_redirect_uri_length CHECK ((char_length(redirect_uri) <= 2048)),
    CONSTRAINT oauth_authorizations_resource_length CHECK ((char_length(resource) <= 2048)),
    CONSTRAINT oauth_authorizations_scope_length CHECK ((char_length(scope) <= 4096)),
    CONSTRAINT oauth_authorizations_state_length CHECK ((char_length(state) <= 4096))
);


--
-- Name: oauth_clients; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.oauth_clients (
    id uuid NOT NULL,
    client_secret_hash text,
    registration_type auth.oauth_registration_type NOT NULL,
    redirect_uris text NOT NULL,
    grant_types text NOT NULL,
    client_name text,
    client_uri text,
    logo_uri text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    client_type auth.oauth_client_type DEFAULT 'confidential'::auth.oauth_client_type NOT NULL,
    CONSTRAINT oauth_clients_client_name_length CHECK ((char_length(client_name) <= 1024)),
    CONSTRAINT oauth_clients_client_uri_length CHECK ((char_length(client_uri) <= 2048)),
    CONSTRAINT oauth_clients_logo_uri_length CHECK ((char_length(logo_uri) <= 2048))
);


--
-- Name: oauth_consents; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.oauth_consents (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    client_id uuid NOT NULL,
    scopes text NOT NULL,
    granted_at timestamp with time zone DEFAULT now() NOT NULL,
    revoked_at timestamp with time zone,
    CONSTRAINT oauth_consents_revoked_after_granted CHECK (((revoked_at IS NULL) OR (revoked_at >= granted_at))),
    CONSTRAINT oauth_consents_scopes_length CHECK ((char_length(scopes) <= 2048)),
    CONSTRAINT oauth_consents_scopes_not_empty CHECK ((char_length(TRIM(BOTH FROM scopes)) > 0))
);


--
-- Name: one_time_tokens; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.one_time_tokens (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    token_type auth.one_time_token_type NOT NULL,
    token_hash text NOT NULL,
    relates_to text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT one_time_tokens_token_hash_check CHECK ((char_length(token_hash) > 0))
);


--
-- Name: refresh_tokens; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.refresh_tokens (
    instance_id uuid,
    id bigint NOT NULL,
    token character varying(255),
    user_id character varying(255),
    revoked boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    parent character varying(255),
    session_id uuid
);


--
-- Name: TABLE refresh_tokens; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.refresh_tokens IS 'Auth: Store of tokens used to refresh JWT tokens once they expire.';


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE; Schema: auth; Owner: -
--

CREATE SEQUENCE auth.refresh_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: auth; Owner: -
--

ALTER SEQUENCE auth.refresh_tokens_id_seq OWNED BY auth.refresh_tokens.id;


--
-- Name: saml_providers; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.saml_providers (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    entity_id text NOT NULL,
    metadata_xml text NOT NULL,
    metadata_url text,
    attribute_mapping jsonb,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    name_id_format text,
    CONSTRAINT "entity_id not empty" CHECK ((char_length(entity_id) > 0)),
    CONSTRAINT "metadata_url not empty" CHECK (((metadata_url = NULL::text) OR (char_length(metadata_url) > 0))),
    CONSTRAINT "metadata_xml not empty" CHECK ((char_length(metadata_xml) > 0))
);


--
-- Name: TABLE saml_providers; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.saml_providers IS 'Auth: Manages SAML Identity Provider connections.';


--
-- Name: saml_relay_states; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.saml_relay_states (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    request_id text NOT NULL,
    for_email text,
    redirect_to text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    flow_state_id uuid,
    CONSTRAINT "request_id not empty" CHECK ((char_length(request_id) > 0))
);


--
-- Name: TABLE saml_relay_states; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.saml_relay_states IS 'Auth: Contains SAML Relay State information for each Service Provider initiated login.';


--
-- Name: schema_migrations; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.schema_migrations (
    version character varying(255) NOT NULL
);


--
-- Name: TABLE schema_migrations; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.schema_migrations IS 'Auth: Manages updates to the auth system.';


--
-- Name: sessions; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.sessions (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    factor_id uuid,
    aal auth.aal_level,
    not_after timestamp with time zone,
    refreshed_at timestamp without time zone,
    user_agent text,
    ip inet,
    tag text,
    oauth_client_id uuid
);


--
-- Name: TABLE sessions; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.sessions IS 'Auth: Stores session data associated to a user.';


--
-- Name: COLUMN sessions.not_after; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON COLUMN auth.sessions.not_after IS 'Auth: Not after is a nullable column that contains a timestamp after which the session should be regarded as expired.';


--
-- Name: sso_domains; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.sso_domains (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    domain text NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    CONSTRAINT "domain not empty" CHECK ((char_length(domain) > 0))
);


--
-- Name: TABLE sso_domains; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.sso_domains IS 'Auth: Manages SSO email address domain mapping to an SSO Identity Provider.';


--
-- Name: sso_providers; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.sso_providers (
    id uuid NOT NULL,
    resource_id text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    disabled boolean,
    CONSTRAINT "resource_id not empty" CHECK (((resource_id = NULL::text) OR (char_length(resource_id) > 0)))
);


--
-- Name: TABLE sso_providers; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.sso_providers IS 'Auth: Manages SSO identity provider information; see saml_providers for SAML.';


--
-- Name: COLUMN sso_providers.resource_id; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON COLUMN auth.sso_providers.resource_id IS 'Auth: Uniquely identifies a SSO provider according to a user-chosen resource ID (case insensitive), useful in infrastructure as code.';


--
-- Name: users; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.users (
    instance_id uuid,
    id uuid NOT NULL,
    aud character varying(255),
    role character varying(255),
    email character varying(255),
    encrypted_password character varying(255),
    email_confirmed_at timestamp with time zone,
    invited_at timestamp with time zone,
    confirmation_token character varying(255),
    confirmation_sent_at timestamp with time zone,
    recovery_token character varying(255),
    recovery_sent_at timestamp with time zone,
    email_change_token_new character varying(255),
    email_change character varying(255),
    email_change_sent_at timestamp with time zone,
    last_sign_in_at timestamp with time zone,
    raw_app_meta_data jsonb,
    raw_user_meta_data jsonb,
    is_super_admin boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    phone text DEFAULT NULL::character varying,
    phone_confirmed_at timestamp with time zone,
    phone_change text DEFAULT ''::character varying,
    phone_change_token character varying(255) DEFAULT ''::character varying,
    phone_change_sent_at timestamp with time zone,
    confirmed_at timestamp with time zone GENERATED ALWAYS AS (LEAST(email_confirmed_at, phone_confirmed_at)) STORED,
    email_change_token_current character varying(255) DEFAULT ''::character varying,
    email_change_confirm_status smallint DEFAULT 0,
    banned_until timestamp with time zone,
    reauthentication_token character varying(255) DEFAULT ''::character varying,
    reauthentication_sent_at timestamp with time zone,
    is_sso_user boolean DEFAULT false NOT NULL,
    deleted_at timestamp with time zone,
    is_anonymous boolean DEFAULT false NOT NULL,
    CONSTRAINT users_email_change_confirm_status_check CHECK (((email_change_confirm_status >= 0) AND (email_change_confirm_status <= 2)))
);


--
-- Name: TABLE users; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.users IS 'Auth: Stores user login data within a secure schema.';


--
-- Name: COLUMN users.is_sso_user; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON COLUMN auth.users.is_sso_user IS 'Auth: Set this column to true when the account comes from SSO. These accounts can have duplicate emails.';


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
    clutch_instance_code text
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
    fish_pair_code text
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
    tank_id bigint NOT NULL,
    status public.tank_status NOT NULL,
    reason text,
    changed_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    changed_by uuid DEFAULT auth.uid(),
    tsh_id bigint NOT NULL
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
    status text DEFAULT 'active'::text,
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
-- Name: v_cross_runs; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_cross_runs AS
 SELECT cr_code,
    tp_code,
    fp_code,
    created_at
   FROM public.v_crosses;


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
 SELECT f.id AS fish_id,
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
-- Name: v_fish_standard_clean; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_fish_standard_clean AS
 WITH per_allele AS (
         SELECT f.fish_code,
            f.name,
            f.nickname,
            f.genetic_background,
            COALESCE(f.line_building_stage, ''::text) AS line_building_stage,
            f.date_birth,
            f.created_at,
            f.created_by,
            fta.transgene_base_code,
            ta.allele_number,
            ta.allele_name,
            ta.allele_nickname,
            ((('Tg('::text || fta.transgene_base_code) || ')'::text) || COALESCE(ta.allele_nickname, ''::text)) AS transgene_pretty_nickname,
            ((('Tg('::text || fta.transgene_base_code) || ')'::text) || COALESCE(ta.allele_name, ''::text)) AS transgene_pretty_name
           FROM ((public.fish f
             LEFT JOIN public.fish_transgene_alleles fta ON ((fta.fish_id = f.id)))
             LEFT JOIN public.transgene_alleles ta ON (((ta.transgene_base_code = fta.transgene_base_code) AND (ta.allele_number = fta.allele_number))))
        ), geno_roll AS (
         SELECT per_allele.fish_code,
            string_agg(DISTINCT per_allele.transgene_pretty_name, '; '::text ORDER BY per_allele.transgene_pretty_name) AS genotype
           FROM per_allele
          GROUP BY per_allele.fish_code
        )
 SELECT p.fish_code,
    p.name,
    p.nickname,
    p.genetic_background,
    p.line_building_stage,
    p.date_birth,
    p.created_at,
    p.created_by,
    p.transgene_base_code,
    p.allele_number,
    p.allele_name,
    p.allele_nickname,
    p.transgene_pretty_nickname,
    p.transgene_pretty_name,
    g.genotype
   FROM (per_allele p
     LEFT JOIN geno_roll g USING (fish_code))
  ORDER BY p.created_at DESC NULLS LAST, p.fish_code;


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
-- Name: v_overview_clutches_cx; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_overview_clutches_cx AS
 SELECT cli.clutch_instance_code AS cl_inst_code,
    ci.cross_run_code AS cr_code,
    cli.tank_pair_code AS tp_code,
    tp.fish_pair_code AS fp_code,
    c.id AS cross_id,
    cl.id AS clutch_id,
    cl.clutch_code AS cl_code,
    cli.created_at AS cl_inst_created_at,
    cl.created_at AS cl_created_at
   FROM ((((public.clutch_instances cli
     LEFT JOIN public.cross_instances ci ON ((ci.tank_pair_code = cli.tank_pair_code)))
     LEFT JOIN public.tank_pairs tp ON ((tp.tank_pair_code = cli.tank_pair_code)))
     LEFT JOIN public.crosses c ON ((c.id = ci.cross_id)))
     LEFT JOIN public.clutches cl ON ((cl.cross_id = c.id)));


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
             LEFT JOIN public.fish fm ON ((fm.id = fp_1.mom_fish_id)))
             LEFT JOIN public.fish fd ON ((fd.id = fp_1.dad_fish_id)))
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
-- Name: v_tanks; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_tanks AS
 SELECT t.tank_code,
    t.fish_code,
    f.id AS fish_id,
    t.tank_uuid,
    t.status,
    t.rack,
    t."position",
    t.created_at,
    t.created_by
   FROM (public.tanks t
     LEFT JOIN public.fish f ON ((f.fish_code = t.fish_code)));


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
-- Name: fish_csv; Type: TABLE; Schema: raw; Owner: -
--

CREATE TABLE raw.fish_csv (
    fish_name text,
    mother text,
    date_of_birth text,
    status text,
    strain text,
    alive text,
    breeding_pairing text,
    fish_code text,
    archived text,
    died text,
    who text
);


--
-- Name: fish_links_has_transgenes_csv; Type: TABLE; Schema: raw; Owner: -
--

CREATE TABLE raw.fish_links_has_transgenes_csv (
    fish_name text,
    transgene_name text,
    allele_name text,
    zygosity text,
    new_allele_note text
);


--
-- Name: fish_links_has_treatment_dye_csv; Type: TABLE; Schema: raw; Owner: -
--

CREATE TABLE raw.fish_links_has_treatment_dye_csv (
    fish_name text,
    dye_name text,
    operator text,
    performed_at text,
    description text,
    notes text
);


--
-- Name: fish_links_has_treatment_injected_plasmid_csv; Type: TABLE; Schema: raw; Owner: -
--

CREATE TABLE raw.fish_links_has_treatment_injected_plasmid_csv (
    fish_name text,
    plasmid_name text,
    operator text,
    performed_at text,
    batch_label text,
    injection_mix text,
    injection_notes text,
    enzyme text
);


--
-- Name: fish_links_has_treatment_injected_rna_csv; Type: TABLE; Schema: raw; Owner: -
--

CREATE TABLE raw.fish_links_has_treatment_injected_rna_csv (
    fish_name text,
    rna_name text,
    operator text,
    performed_at text,
    description text,
    notes text
);


--
-- Name: wide_fish_upload; Type: TABLE; Schema: raw; Owner: -
--

CREATE TABLE raw.wide_fish_upload (
    seed_batch_id text NOT NULL,
    fish_name text NOT NULL,
    nickname text,
    birth_date date,
    background_strain text,
    strain text,
    batch_label text,
    line_building_stage text,
    description text,
    notes text,
    transgene_base_code text,
    allele_number integer,
    allele_label_legacy text,
    zygosity text,
    created_by text,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: messages; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.messages (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
)
PARTITION BY RANGE (inserted_at);


--
-- Name: messages_2025_09_20; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.messages_2025_09_20 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: messages_2025_09_21; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.messages_2025_09_21 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: messages_2025_09_22; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.messages_2025_09_22 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: messages_2025_09_23; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.messages_2025_09_23 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: messages_2025_09_24; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.messages_2025_09_24 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: schema_migrations; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.schema_migrations (
    version bigint NOT NULL,
    inserted_at timestamp(0) without time zone
);


--
-- Name: subscription; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.subscription (
    id bigint NOT NULL,
    subscription_id uuid NOT NULL,
    entity regclass NOT NULL,
    filters realtime.user_defined_filter[] DEFAULT '{}'::realtime.user_defined_filter[] NOT NULL,
    claims jsonb NOT NULL,
    claims_role regrole GENERATED ALWAYS AS (realtime.to_regrole((claims ->> 'role'::text))) STORED NOT NULL,
    created_at timestamp without time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);


--
-- Name: subscription_id_seq; Type: SEQUENCE; Schema: realtime; Owner: -
--

ALTER TABLE realtime.subscription ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME realtime.subscription_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: _dye_csv; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging._dye_csv (
    fish_name text,
    performed_at text,
    dye_code text,
    treatment text,
    operator text,
    notes text
);


--
-- Name: _dye_treatments_raw; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging._dye_treatments_raw (
    fish_name text,
    dye_code text,
    performed_at text,
    operator text,
    dose_value text,
    dose_unit text,
    notes text
);


--
-- Name: _dyes_raw; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging._dyes_raw (
    line text
);


--
-- Name: _plasmid_csv; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging._plasmid_csv (
    fish_name text,
    performed_at text,
    plasmid_code text,
    treatment text,
    operator text,
    notes text
);


--
-- Name: _plasmid_treatments_raw; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging._plasmid_treatments_raw (
    fish_name text,
    plasmid_code text,
    performed_at text,
    operator text,
    dose_value text,
    dose_unit text,
    enzyme text,
    notes text
);


--
-- Name: _plasmids_raw; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging._plasmids_raw (
    line text
);


--
-- Name: _rna_csv; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging._rna_csv (
    fish_name text,
    performed_at text,
    rna_code text,
    treatment text,
    operator text,
    notes text
);


--
-- Name: _rna_treatments_raw; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging._rna_treatments_raw (
    fish_name text,
    rna_code text,
    performed_at text,
    operator text,
    dose_value text,
    dose_unit text,
    notes text
);


--
-- Name: _rnas_raw; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging._rnas_raw (
    line text
);


--
-- Name: dyes; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.dyes (
    dye_code text,
    description text
);


--
-- Name: fish; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.fish (
    name text
);


--
-- Name: fish_transgene_alleles; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.fish_transgene_alleles (
    fish_name text,
    transgene_base_code text,
    allele_number text,
    zygosity text
);


--
-- Name: plasmids; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.plasmids (
    plasmid_code text,
    description text
);


--
-- Name: rnas; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.rnas (
    rna_code text,
    description text
);


--
-- Name: transgene_alleles; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.transgene_alleles (
    transgene_base_code text,
    allele_number text,
    description text
);


--
-- Name: transgenes; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.transgenes (
    transgene_base_code text,
    description text
);


--
-- Name: transgenes_raw; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.transgenes_raw (
    line text
);


--
-- Name: treatments_unified; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.treatments_unified (
    fish_name text,
    treatment_type text,
    material_code text,
    performed_at timestamp with time zone,
    operator text,
    dose_value text,
    dose_unit text,
    enzyme text,
    notes text
);


--
-- Name: treatments_unified_raw; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.treatments_unified_raw (
    fish_name text,
    treatment_type text,
    material_code text,
    performed_at text,
    operator text,
    dose_value text,
    dose_unit text,
    enzyme text,
    notes text
);


--
-- Name: v_all_treatments_text; Type: VIEW; Schema: staging; Owner: -
--

CREATE VIEW staging.v_all_treatments_text AS
 SELECT lower(TRIM(BOTH FROM _plasmid_csv.fish_name)) AS fish_name_lc,
    'plasmid'::text AS treatment_type,
    TRIM(BOTH FROM _plasmid_csv.plasmid_code) AS material_code,
    TRIM(BOTH FROM _plasmid_csv.performed_at) AS performed_at,
    NULLIF(TRIM(BOTH FROM _plasmid_csv.operator), ''::text) AS operator,
    NULL::text AS dose_value,
    NULL::text AS dose_unit,
    NULL::text AS enzyme,
    NULLIF(TRIM(BOTH FROM _plasmid_csv.notes), ''::text) AS notes
   FROM staging._plasmid_csv
UNION ALL
 SELECT lower(TRIM(BOTH FROM _rna_csv.fish_name)) AS fish_name_lc,
    'rna'::text AS treatment_type,
    TRIM(BOTH FROM _rna_csv.rna_code) AS material_code,
    TRIM(BOTH FROM _rna_csv.performed_at) AS performed_at,
    NULLIF(TRIM(BOTH FROM _rna_csv.operator), ''::text) AS operator,
    NULL::text AS dose_value,
    NULL::text AS dose_unit,
    NULL::text AS enzyme,
    NULLIF(TRIM(BOTH FROM _rna_csv.notes), ''::text) AS notes
   FROM staging._rna_csv
UNION ALL
 SELECT lower(TRIM(BOTH FROM _dye_csv.fish_name)) AS fish_name_lc,
    'dye'::text AS treatment_type,
    TRIM(BOTH FROM _dye_csv.dye_code) AS material_code,
    TRIM(BOTH FROM _dye_csv.performed_at) AS performed_at,
    NULLIF(TRIM(BOTH FROM _dye_csv.operator), ''::text) AS operator,
    NULL::text AS dose_value,
    NULL::text AS dose_unit,
    NULL::text AS enzyme,
    NULLIF(TRIM(BOTH FROM _dye_csv.notes), ''::text) AS notes
   FROM staging._dye_csv;


--
-- Name: v_all_treatments; Type: VIEW; Schema: staging; Owner: -
--

CREATE VIEW staging.v_all_treatments AS
 SELECT fish_name_lc,
    treatment_type,
    material_code,
        CASE
            WHEN (performed_at ~ '^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$$'::text) THEN (((performed_at ||
            CASE
                WHEN ((POSITION(('T'::text) IN (performed_at)) = 0) AND (length(performed_at) = 10)) THEN ' 00:00:00'::text
                ELSE ''::text
            END))::timestamp without time zone)::timestamp with time zone
            WHEN (performed_at ~ '^\d{1,2}/\d{1,2}/\d{2,4}(\s+\d{1,2}:\d{2}(:\d{2})?\s*(am|pm)?)?$$'::text) THEN to_timestamp(performed_at, 'MM/DD/YYYY HH12:MI:SS am'::text)
            ELSE NULL::timestamp with time zone
        END AS performed_at,
    operator,
    dose_value,
    dose_unit,
    enzyme,
    notes
   FROM staging.v_all_treatments_text;


--
-- Name: buckets; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.buckets (
    id text NOT NULL,
    name text NOT NULL,
    owner uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    public boolean DEFAULT false,
    avif_autodetection boolean DEFAULT false,
    file_size_limit bigint,
    allowed_mime_types text[],
    owner_id text,
    type storage.buckettype DEFAULT 'STANDARD'::storage.buckettype NOT NULL
);


--
-- Name: COLUMN buckets.owner; Type: COMMENT; Schema: storage; Owner: -
--

COMMENT ON COLUMN storage.buckets.owner IS 'Field is deprecated, use owner_id instead';


--
--

    id text NOT NULL,
    type storage.buckettype DEFAULT 'ANALYTICS'::storage.buckettype NOT NULL,
    format text DEFAULT 'ICEBERG'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: migrations; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.migrations (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    hash character varying(40) NOT NULL,
    executed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: objects; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.objects (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    bucket_id text,
    name text,
    owner uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    last_accessed_at timestamp with time zone DEFAULT now(),
    metadata jsonb,
    path_tokens text[] GENERATED ALWAYS AS (string_to_array(name, '/'::text)) STORED,
    version text,
    owner_id text,
    user_metadata jsonb,
    level integer
);


--
-- Name: COLUMN objects.owner; Type: COMMENT; Schema: storage; Owner: -
--

COMMENT ON COLUMN storage.objects.owner IS 'Field is deprecated, use owner_id instead';


--
-- Name: prefixes; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.prefixes (
    bucket_id text NOT NULL,
    name text NOT NULL COLLATE pg_catalog."C",
    level integer GENERATED ALWAYS AS (storage.get_level(name)) STORED NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: s3_multipart_uploads; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.s3_multipart_uploads (
    id text NOT NULL,
    in_progress_size bigint DEFAULT 0 NOT NULL,
    upload_signature text NOT NULL,
    bucket_id text NOT NULL,
    key text NOT NULL COLLATE pg_catalog."C",
    version text NOT NULL,
    owner_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    user_metadata jsonb
);


--
-- Name: s3_multipart_uploads_parts; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.s3_multipart_uploads_parts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    upload_id text NOT NULL,
    size bigint DEFAULT 0 NOT NULL,
    part_number integer NOT NULL,
    bucket_id text NOT NULL,
    key text NOT NULL COLLATE pg_catalog."C",
    etag text NOT NULL,
    owner_id text,
    version text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: hooks; Type: TABLE; Schema: supabase_functions; Owner: -
--

CREATE TABLE supabase_functions.hooks (
    id bigint NOT NULL,
    hook_table_id integer NOT NULL,
    hook_name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    request_id bigint
);


--
-- Name: TABLE hooks; Type: COMMENT; Schema: supabase_functions; Owner: -
--

COMMENT ON TABLE supabase_functions.hooks IS 'Supabase Functions Hooks: Audit trail for triggered hooks.';


--
-- Name: hooks_id_seq; Type: SEQUENCE; Schema: supabase_functions; Owner: -
--

CREATE SEQUENCE supabase_functions.hooks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hooks_id_seq; Type: SEQUENCE OWNED BY; Schema: supabase_functions; Owner: -
--

ALTER SEQUENCE supabase_functions.hooks_id_seq OWNED BY supabase_functions.hooks.id;


--
-- Name: migrations; Type: TABLE; Schema: supabase_functions; Owner: -
--

CREATE TABLE supabase_functions.migrations (
    version text NOT NULL,
    inserted_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: reverted_versions; Type: TABLE; Schema: supabase_migrations; Owner: -
--

CREATE TABLE supabase_migrations.reverted_versions (
    version text NOT NULL,
    noted_at timestamp with time zone DEFAULT now()
);


--
-- Name: schema_migrations; Type: TABLE; Schema: supabase_migrations; Owner: -
--

CREATE TABLE supabase_migrations.schema_migrations (
    version text NOT NULL,
    statements text[],
    name text
);


--
-- Name: seed_files; Type: TABLE; Schema: supabase_migrations; Owner: -
--

CREATE TABLE supabase_migrations.seed_files (
    path text NOT NULL,
    hash text NOT NULL
);


--
-- Name: messages_2025_09_20; Type: TABLE ATTACH; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_09_20 FOR VALUES FROM ('2025-09-20 00:00:00') TO ('2025-09-21 00:00:00');


--
-- Name: messages_2025_09_21; Type: TABLE ATTACH; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_09_21 FOR VALUES FROM ('2025-09-21 00:00:00') TO ('2025-09-22 00:00:00');


--
-- Name: messages_2025_09_22; Type: TABLE ATTACH; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_09_22 FOR VALUES FROM ('2025-09-22 00:00:00') TO ('2025-09-23 00:00:00');


--
-- Name: messages_2025_09_23; Type: TABLE ATTACH; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_09_23 FOR VALUES FROM ('2025-09-23 00:00:00') TO ('2025-09-24 00:00:00');


--
-- Name: messages_2025_09_24; Type: TABLE ATTACH; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_09_24 FOR VALUES FROM ('2025-09-24 00:00:00') TO ('2025-09-25 00:00:00');


--
-- Name: writes id; Type: DEFAULT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.writes ALTER COLUMN id SET DEFAULT nextval('audit.writes_id_seq'::regclass);


--
-- Name: refresh_tokens id; Type: DEFAULT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.refresh_tokens ALTER COLUMN id SET DEFAULT nextval('auth.refresh_tokens_id_seq'::regclass);


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
-- Name: hooks id; Type: DEFAULT; Schema: supabase_functions; Owner: -
--

ALTER TABLE ONLY supabase_functions.hooks ALTER COLUMN id SET DEFAULT nextval('supabase_functions.hooks_id_seq'::regclass);


--
--

    ADD CONSTRAINT extensions_pkey PRIMARY KEY (id);


--
--

    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
--

    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: writes writes_pkey; Type: CONSTRAINT; Schema: audit; Owner: -
--

ALTER TABLE ONLY audit.writes
    ADD CONSTRAINT writes_pkey PRIMARY KEY (id);


--
-- Name: mfa_amr_claims amr_id_pk; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT amr_id_pk PRIMARY KEY (id);


--
-- Name: audit_log_entries audit_log_entries_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.audit_log_entries
    ADD CONSTRAINT audit_log_entries_pkey PRIMARY KEY (id);


--
-- Name: flow_state flow_state_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.flow_state
    ADD CONSTRAINT flow_state_pkey PRIMARY KEY (id);


--
-- Name: identities identities_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_pkey PRIMARY KEY (id);


--
-- Name: identities identities_provider_id_provider_unique; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_provider_id_provider_unique UNIQUE (provider_id, provider);


--
-- Name: instances instances_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.instances
    ADD CONSTRAINT instances_pkey PRIMARY KEY (id);


--
-- Name: mfa_amr_claims mfa_amr_claims_session_id_authentication_method_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT mfa_amr_claims_session_id_authentication_method_pkey UNIQUE (session_id, authentication_method);


--
-- Name: mfa_challenges mfa_challenges_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_challenges
    ADD CONSTRAINT mfa_challenges_pkey PRIMARY KEY (id);


--
-- Name: mfa_factors mfa_factors_last_challenged_at_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_last_challenged_at_key UNIQUE (last_challenged_at);


--
-- Name: mfa_factors mfa_factors_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_pkey PRIMARY KEY (id);


--
-- Name: oauth_authorizations oauth_authorizations_authorization_code_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_authorization_code_key UNIQUE (authorization_code);


--
-- Name: oauth_authorizations oauth_authorizations_authorization_id_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_authorization_id_key UNIQUE (authorization_id);


--
-- Name: oauth_authorizations oauth_authorizations_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_pkey PRIMARY KEY (id);


--
-- Name: oauth_clients oauth_clients_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_clients
    ADD CONSTRAINT oauth_clients_pkey PRIMARY KEY (id);


--
-- Name: oauth_consents oauth_consents_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_pkey PRIMARY KEY (id);


--
-- Name: oauth_consents oauth_consents_user_client_unique; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_user_client_unique UNIQUE (user_id, client_id);


--
-- Name: one_time_tokens one_time_tokens_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.one_time_tokens
    ADD CONSTRAINT one_time_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_token_unique; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_token_unique UNIQUE (token);


--
-- Name: saml_providers saml_providers_entity_id_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_entity_id_key UNIQUE (entity_id);


--
-- Name: saml_providers saml_providers_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_pkey PRIMARY KEY (id);


--
-- Name: saml_relay_states saml_relay_states_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: sso_domains sso_domains_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sso_domains
    ADD CONSTRAINT sso_domains_pkey PRIMARY KEY (id);


--
-- Name: sso_providers sso_providers_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sso_providers
    ADD CONSTRAINT sso_providers_pkey PRIMARY KEY (id);


--
-- Name: users users_phone_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_phone_key UNIQUE (phone);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


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
    ADD CONSTRAINT tanks_pkey PRIMARY KEY (tank_id);


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
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_09_20 messages_2025_09_20_pkey; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages_2025_09_20
    ADD CONSTRAINT messages_2025_09_20_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_09_21 messages_2025_09_21_pkey; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages_2025_09_21
    ADD CONSTRAINT messages_2025_09_21_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_09_22 messages_2025_09_22_pkey; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages_2025_09_22
    ADD CONSTRAINT messages_2025_09_22_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_09_23 messages_2025_09_23_pkey; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages_2025_09_23
    ADD CONSTRAINT messages_2025_09_23_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_09_24 messages_2025_09_24_pkey; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages_2025_09_24
    ADD CONSTRAINT messages_2025_09_24_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: subscription pk_subscription; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.subscription
    ADD CONSTRAINT pk_subscription PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
--



--
-- Name: buckets buckets_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.buckets
    ADD CONSTRAINT buckets_pkey PRIMARY KEY (id);


--
-- Name: migrations migrations_name_key; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.migrations
    ADD CONSTRAINT migrations_name_key UNIQUE (name);


--
-- Name: migrations migrations_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.migrations
    ADD CONSTRAINT migrations_pkey PRIMARY KEY (id);


--
-- Name: objects objects_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.objects
    ADD CONSTRAINT objects_pkey PRIMARY KEY (id);


--
-- Name: prefixes prefixes_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.prefixes
    ADD CONSTRAINT prefixes_pkey PRIMARY KEY (bucket_id, level, name);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_pkey PRIMARY KEY (id);


--
-- Name: s3_multipart_uploads s3_multipart_uploads_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.s3_multipart_uploads
    ADD CONSTRAINT s3_multipart_uploads_pkey PRIMARY KEY (id);


--
-- Name: hooks hooks_pkey; Type: CONSTRAINT; Schema: supabase_functions; Owner: -
--

ALTER TABLE ONLY supabase_functions.hooks
    ADD CONSTRAINT hooks_pkey PRIMARY KEY (id);


--
-- Name: migrations migrations_pkey; Type: CONSTRAINT; Schema: supabase_functions; Owner: -
--

ALTER TABLE ONLY supabase_functions.migrations
    ADD CONSTRAINT migrations_pkey PRIMARY KEY (version);


--
-- Name: reverted_versions reverted_versions_pkey; Type: CONSTRAINT; Schema: supabase_migrations; Owner: -
--

ALTER TABLE ONLY supabase_migrations.reverted_versions
    ADD CONSTRAINT reverted_versions_pkey PRIMARY KEY (version);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: supabase_migrations; Owner: -
--

ALTER TABLE ONLY supabase_migrations.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: seed_files seed_files_pkey; Type: CONSTRAINT; Schema: supabase_migrations; Owner: -
--

ALTER TABLE ONLY supabase_migrations.seed_files
    ADD CONSTRAINT seed_files_pkey PRIMARY KEY (path);


--
--



--
--



--
--



--
-- Name: audit_logs_instance_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX audit_logs_instance_id_idx ON auth.audit_log_entries USING btree (instance_id);


--
-- Name: confirmation_token_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX confirmation_token_idx ON auth.users USING btree (confirmation_token) WHERE ((confirmation_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: email_change_token_current_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX email_change_token_current_idx ON auth.users USING btree (email_change_token_current) WHERE ((email_change_token_current)::text !~ '^[0-9 ]*$'::text);


--
-- Name: email_change_token_new_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX email_change_token_new_idx ON auth.users USING btree (email_change_token_new) WHERE ((email_change_token_new)::text !~ '^[0-9 ]*$'::text);


--
-- Name: factor_id_created_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX factor_id_created_at_idx ON auth.mfa_factors USING btree (user_id, created_at);


--
-- Name: flow_state_created_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX flow_state_created_at_idx ON auth.flow_state USING btree (created_at DESC);


--
-- Name: identities_email_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX identities_email_idx ON auth.identities USING btree (email text_pattern_ops);


--
-- Name: INDEX identities_email_idx; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON INDEX auth.identities_email_idx IS 'Auth: Ensures indexed queries on the email column';


--
-- Name: identities_user_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX identities_user_id_idx ON auth.identities USING btree (user_id);


--
-- Name: idx_auth_code; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_auth_code ON auth.flow_state USING btree (auth_code);


--
-- Name: idx_user_id_auth_method; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_user_id_auth_method ON auth.flow_state USING btree (user_id, authentication_method);


--
-- Name: mfa_challenge_created_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX mfa_challenge_created_at_idx ON auth.mfa_challenges USING btree (created_at DESC);


--
-- Name: mfa_factors_user_friendly_name_unique; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX mfa_factors_user_friendly_name_unique ON auth.mfa_factors USING btree (friendly_name, user_id) WHERE (TRIM(BOTH FROM friendly_name) <> ''::text);


--
-- Name: mfa_factors_user_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX mfa_factors_user_id_idx ON auth.mfa_factors USING btree (user_id);


--
-- Name: oauth_auth_pending_exp_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX oauth_auth_pending_exp_idx ON auth.oauth_authorizations USING btree (expires_at) WHERE (status = 'pending'::auth.oauth_authorization_status);


--
-- Name: oauth_clients_deleted_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX oauth_clients_deleted_at_idx ON auth.oauth_clients USING btree (deleted_at);


--
-- Name: oauth_consents_active_client_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX oauth_consents_active_client_idx ON auth.oauth_consents USING btree (client_id) WHERE (revoked_at IS NULL);


--
-- Name: oauth_consents_active_user_client_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX oauth_consents_active_user_client_idx ON auth.oauth_consents USING btree (user_id, client_id) WHERE (revoked_at IS NULL);


--
-- Name: oauth_consents_user_order_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX oauth_consents_user_order_idx ON auth.oauth_consents USING btree (user_id, granted_at DESC);


--
-- Name: one_time_tokens_relates_to_hash_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX one_time_tokens_relates_to_hash_idx ON auth.one_time_tokens USING hash (relates_to);


--
-- Name: one_time_tokens_token_hash_hash_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX one_time_tokens_token_hash_hash_idx ON auth.one_time_tokens USING hash (token_hash);


--
-- Name: one_time_tokens_user_id_token_type_key; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX one_time_tokens_user_id_token_type_key ON auth.one_time_tokens USING btree (user_id, token_type);


--
-- Name: reauthentication_token_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX reauthentication_token_idx ON auth.users USING btree (reauthentication_token) WHERE ((reauthentication_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: recovery_token_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX recovery_token_idx ON auth.users USING btree (recovery_token) WHERE ((recovery_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: refresh_tokens_instance_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX refresh_tokens_instance_id_idx ON auth.refresh_tokens USING btree (instance_id);


--
-- Name: refresh_tokens_instance_id_user_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX refresh_tokens_instance_id_user_id_idx ON auth.refresh_tokens USING btree (instance_id, user_id);


--
-- Name: refresh_tokens_parent_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX refresh_tokens_parent_idx ON auth.refresh_tokens USING btree (parent);


--
-- Name: refresh_tokens_session_id_revoked_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX refresh_tokens_session_id_revoked_idx ON auth.refresh_tokens USING btree (session_id, revoked);


--
-- Name: refresh_tokens_updated_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX refresh_tokens_updated_at_idx ON auth.refresh_tokens USING btree (updated_at DESC);


--
-- Name: saml_providers_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX saml_providers_sso_provider_id_idx ON auth.saml_providers USING btree (sso_provider_id);


--
-- Name: saml_relay_states_created_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX saml_relay_states_created_at_idx ON auth.saml_relay_states USING btree (created_at DESC);


--
-- Name: saml_relay_states_for_email_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX saml_relay_states_for_email_idx ON auth.saml_relay_states USING btree (for_email);


--
-- Name: saml_relay_states_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX saml_relay_states_sso_provider_id_idx ON auth.saml_relay_states USING btree (sso_provider_id);


--
-- Name: sessions_not_after_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX sessions_not_after_idx ON auth.sessions USING btree (not_after DESC);


--
-- Name: sessions_oauth_client_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX sessions_oauth_client_id_idx ON auth.sessions USING btree (oauth_client_id);


--
-- Name: sessions_user_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX sessions_user_id_idx ON auth.sessions USING btree (user_id);


--
-- Name: sso_domains_domain_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX sso_domains_domain_idx ON auth.sso_domains USING btree (lower(domain));


--
-- Name: sso_domains_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX sso_domains_sso_provider_id_idx ON auth.sso_domains USING btree (sso_provider_id);


--
-- Name: sso_providers_resource_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX sso_providers_resource_id_idx ON auth.sso_providers USING btree (lower(resource_id));


--
-- Name: sso_providers_resource_id_pattern_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX sso_providers_resource_id_pattern_idx ON auth.sso_providers USING btree (resource_id text_pattern_ops);


--
-- Name: unique_phone_factor_per_user; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX unique_phone_factor_per_user ON auth.mfa_factors USING btree (user_id, phone);


--
-- Name: user_id_created_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX user_id_created_at_idx ON auth.sessions USING btree (user_id, created_at);


--
-- Name: users_email_partial_key; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX users_email_partial_key ON auth.users USING btree (email) WHERE (is_sso_user = false);


--
-- Name: INDEX users_email_partial_key; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON INDEX auth.users_email_partial_key IS 'Auth: A partial unique index that applies only when is_sso_user is false';


--
-- Name: users_instance_id_email_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX users_instance_id_email_idx ON auth.users USING btree (instance_id, lower((email)::text));


--
-- Name: users_instance_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX users_instance_id_idx ON auth.users USING btree (instance_id);


--
-- Name: users_is_anonymous_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX users_is_anonymous_idx ON auth.users USING btree (is_anonymous);


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
-- Name: ix_plasmids_v_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_plasmids_v_code ON public.plasmids USING btree (code);


--
-- Name: ix_registry_base_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_registry_base_code ON public.transgene_allele_registry USING btree (base_code);


--
-- Name: ix_tsh_tank_id_changed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tsh_tank_id_changed_at ON public.tank_status_history USING btree (tank_id, changed_at DESC);


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

CREATE UNIQUE INDEX uq_fish_pairs_code ON public.fish_pairs USING btree (fish_pair_code) WHERE (fish_pair_code IS NOT NULL);


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

CREATE UNIQUE INDEX uq_tank_pairs_code ON public.tank_pairs USING btree (tank_pair_code) WHERE (tank_pair_code IS NOT NULL);


--
-- Name: uq_tar_base_number; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_tar_base_number ON public.transgene_allele_registry USING btree (transgene_base_code, allele_number);


--
-- Name: ux_fish_pairs_mom_dad; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_fish_pairs_mom_dad ON public.fish_pairs USING btree (mom_fish_id, dad_fish_id);


--
-- Name: ux_fta_fish_base; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_fta_fish_base ON public.fish_transgene_alleles USING btree (fish_id, transgene_base_code);


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
--



--
-- Name: messages_inserted_at_topic_index; Type: INDEX; Schema: realtime; Owner: -
--

CREATE INDEX messages_inserted_at_topic_index ON ONLY realtime.messages USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2025_09_20_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: -
--

CREATE INDEX messages_2025_09_20_inserted_at_topic_idx ON realtime.messages_2025_09_20 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2025_09_21_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: -
--

CREATE INDEX messages_2025_09_21_inserted_at_topic_idx ON realtime.messages_2025_09_21 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2025_09_22_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: -
--

CREATE INDEX messages_2025_09_22_inserted_at_topic_idx ON realtime.messages_2025_09_22 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2025_09_23_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: -
--

CREATE INDEX messages_2025_09_23_inserted_at_topic_idx ON realtime.messages_2025_09_23 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: messages_2025_09_24_inserted_at_topic_idx; Type: INDEX; Schema: realtime; Owner: -
--

CREATE INDEX messages_2025_09_24_inserted_at_topic_idx ON realtime.messages_2025_09_24 USING btree (inserted_at DESC, topic) WHERE ((extension = 'broadcast'::text) AND (private IS TRUE));


--
-- Name: subscription_subscription_id_entity_filters_key; Type: INDEX; Schema: realtime; Owner: -
--

CREATE UNIQUE INDEX subscription_subscription_id_entity_filters_key ON realtime.subscription USING btree (subscription_id, entity, filters);


--
-- Name: bname; Type: INDEX; Schema: storage; Owner: -
--

CREATE UNIQUE INDEX bname ON storage.buckets USING btree (name);


--
-- Name: bucketid_objname; Type: INDEX; Schema: storage; Owner: -
--

CREATE UNIQUE INDEX bucketid_objname ON storage.objects USING btree (bucket_id, name);


--
-- Name: idx_multipart_uploads_list; Type: INDEX; Schema: storage; Owner: -
--

CREATE INDEX idx_multipart_uploads_list ON storage.s3_multipart_uploads USING btree (bucket_id, key, created_at);


--
-- Name: idx_name_bucket_level_unique; Type: INDEX; Schema: storage; Owner: -
--

CREATE UNIQUE INDEX idx_name_bucket_level_unique ON storage.objects USING btree (name COLLATE "C", bucket_id, level);


--
-- Name: idx_objects_bucket_id_name; Type: INDEX; Schema: storage; Owner: -
--

CREATE INDEX idx_objects_bucket_id_name ON storage.objects USING btree (bucket_id, name COLLATE "C");


--
-- Name: idx_objects_lower_name; Type: INDEX; Schema: storage; Owner: -
--

CREATE INDEX idx_objects_lower_name ON storage.objects USING btree ((path_tokens[level]), lower(name) text_pattern_ops, bucket_id, level);


--
-- Name: idx_prefixes_lower_name; Type: INDEX; Schema: storage; Owner: -
--

CREATE INDEX idx_prefixes_lower_name ON storage.prefixes USING btree (bucket_id, level, ((string_to_array(name, '/'::text))[level]), lower(name) text_pattern_ops);


--
-- Name: name_prefix_search; Type: INDEX; Schema: storage; Owner: -
--

CREATE INDEX name_prefix_search ON storage.objects USING btree (name text_pattern_ops);


--
-- Name: objects_bucket_id_level_idx; Type: INDEX; Schema: storage; Owner: -
--

CREATE UNIQUE INDEX objects_bucket_id_level_idx ON storage.objects USING btree (bucket_id, level, name COLLATE "C");


--
-- Name: supabase_functions_hooks_h_table_id_h_name_idx; Type: INDEX; Schema: supabase_functions; Owner: -
--

CREATE INDEX supabase_functions_hooks_h_table_id_h_name_idx ON supabase_functions.hooks USING btree (hook_table_id, hook_name);


--
-- Name: supabase_functions_hooks_request_id_idx; Type: INDEX; Schema: supabase_functions; Owner: -
--

CREATE INDEX supabase_functions_hooks_request_id_idx ON supabase_functions.hooks USING btree (request_id);


--
-- Name: messages_2025_09_20_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2025_09_20_inserted_at_topic_idx;


--
-- Name: messages_2025_09_20_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_09_20_pkey;


--
-- Name: messages_2025_09_21_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2025_09_21_inserted_at_topic_idx;


--
-- Name: messages_2025_09_21_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_09_21_pkey;


--
-- Name: messages_2025_09_22_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2025_09_22_inserted_at_topic_idx;


--
-- Name: messages_2025_09_22_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_09_22_pkey;


--
-- Name: messages_2025_09_23_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2025_09_23_inserted_at_topic_idx;


--
-- Name: messages_2025_09_23_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_09_23_pkey;


--
-- Name: messages_2025_09_24_inserted_at_topic_idx; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_inserted_at_topic_index ATTACH PARTITION realtime.messages_2025_09_24_inserted_at_topic_idx;


--
-- Name: messages_2025_09_24_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_09_24_pkey;


--
-- Name: fish bi_set_fish_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER bi_set_fish_code BEFORE INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.fish_bi_set_fish_code();


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

CREATE TRIGGER trg_clutch_instances_set_code BEFORE INSERT ON public.clutch_instances FOR EACH ROW EXECUTE FUNCTION public.trg_clutch_instances_set_code();


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
-- Name: fish trg_fish_autotank; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_fish_autotank AFTER INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.fn_fish_autocreate_tank_v2();


--
-- Name: fish trg_fish_before_insert_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_fish_before_insert_code BEFORE INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.fish_before_insert_code();


--
-- Name: fish_pairs trg_fish_pairs_code_autogen; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_fish_pairs_code_autogen BEFORE INSERT ON public.fish_pairs FOR EACH ROW EXECUTE FUNCTION public.fish_pairs_code_autogen();


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
-- Name: tank_pairs trg_tank_pairs_set_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_tank_pairs_set_code BEFORE INSERT ON public.tank_pairs FOR EACH ROW EXECUTE FUNCTION public.trg_tank_pairs_set_code();


--
-- Name: crosses zz_bi_normalize_cross_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER zz_bi_normalize_cross_code BEFORE INSERT OR UPDATE ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_cross_code_normalize();


--
-- Name: subscription tr_check_filters; Type: TRIGGER; Schema: realtime; Owner: -
--

CREATE TRIGGER tr_check_filters BEFORE INSERT OR UPDATE ON realtime.subscription FOR EACH ROW EXECUTE FUNCTION realtime.subscription_check_filters();


--
-- Name: buckets enforce_bucket_name_length_trigger; Type: TRIGGER; Schema: storage; Owner: -
--

CREATE TRIGGER enforce_bucket_name_length_trigger BEFORE INSERT OR UPDATE OF name ON storage.buckets FOR EACH ROW EXECUTE FUNCTION storage.enforce_bucket_name_length();


--
-- Name: objects objects_delete_delete_prefix; Type: TRIGGER; Schema: storage; Owner: -
--

CREATE TRIGGER objects_delete_delete_prefix AFTER DELETE ON storage.objects FOR EACH ROW EXECUTE FUNCTION storage.delete_prefix_hierarchy_trigger();


--
-- Name: objects objects_insert_create_prefix; Type: TRIGGER; Schema: storage; Owner: -
--

CREATE TRIGGER objects_insert_create_prefix BEFORE INSERT ON storage.objects FOR EACH ROW EXECUTE FUNCTION storage.objects_insert_prefix_trigger();


--
-- Name: objects objects_update_create_prefix; Type: TRIGGER; Schema: storage; Owner: -
--

CREATE TRIGGER objects_update_create_prefix BEFORE UPDATE ON storage.objects FOR EACH ROW WHEN (((new.name <> old.name) OR (new.bucket_id <> old.bucket_id))) EXECUTE FUNCTION storage.objects_update_prefix_trigger();


--
-- Name: prefixes prefixes_create_hierarchy; Type: TRIGGER; Schema: storage; Owner: -
--

CREATE TRIGGER prefixes_create_hierarchy BEFORE INSERT ON storage.prefixes FOR EACH ROW WHEN ((pg_trigger_depth() < 1)) EXECUTE FUNCTION storage.prefixes_insert_trigger();


--
-- Name: prefixes prefixes_delete_hierarchy; Type: TRIGGER; Schema: storage; Owner: -
--

CREATE TRIGGER prefixes_delete_hierarchy AFTER DELETE ON storage.prefixes FOR EACH ROW EXECUTE FUNCTION storage.delete_prefix_hierarchy_trigger();


--
-- Name: objects update_objects_updated_at; Type: TRIGGER; Schema: storage; Owner: -
--

CREATE TRIGGER update_objects_updated_at BEFORE UPDATE ON storage.objects FOR EACH ROW EXECUTE FUNCTION storage.update_updated_at_column();


--
--



--
-- Name: identities identities_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: mfa_amr_claims mfa_amr_claims_session_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT mfa_amr_claims_session_id_fkey FOREIGN KEY (session_id) REFERENCES auth.sessions(id) ON DELETE CASCADE;


--
-- Name: mfa_challenges mfa_challenges_auth_factor_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_challenges
    ADD CONSTRAINT mfa_challenges_auth_factor_id_fkey FOREIGN KEY (factor_id) REFERENCES auth.mfa_factors(id) ON DELETE CASCADE;


--
-- Name: mfa_factors mfa_factors_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: oauth_authorizations oauth_authorizations_client_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_client_id_fkey FOREIGN KEY (client_id) REFERENCES auth.oauth_clients(id) ON DELETE CASCADE;


--
-- Name: oauth_authorizations oauth_authorizations_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_authorizations
    ADD CONSTRAINT oauth_authorizations_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: oauth_consents oauth_consents_client_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_client_id_fkey FOREIGN KEY (client_id) REFERENCES auth.oauth_clients(id) ON DELETE CASCADE;


--
-- Name: oauth_consents oauth_consents_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_consents
    ADD CONSTRAINT oauth_consents_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: one_time_tokens one_time_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.one_time_tokens
    ADD CONSTRAINT one_time_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens refresh_tokens_session_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_session_id_fkey FOREIGN KEY (session_id) REFERENCES auth.sessions(id) ON DELETE CASCADE;


--
-- Name: saml_providers saml_providers_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: saml_relay_states saml_relay_states_flow_state_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_flow_state_id_fkey FOREIGN KEY (flow_state_id) REFERENCES auth.flow_state(id) ON DELETE CASCADE;


--
-- Name: saml_relay_states saml_relay_states_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: sessions sessions_oauth_client_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_oauth_client_id_fkey FOREIGN KEY (oauth_client_id) REFERENCES auth.oauth_clients(id) ON DELETE CASCADE;


--
-- Name: sessions sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: sso_domains sso_domains_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sso_domains
    ADD CONSTRAINT sso_domains_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


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
-- Name: fish_pairs fish_pairs_dad_fish_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_pairs
    ADD CONSTRAINT fish_pairs_dad_fish_id_fkey FOREIGN KEY (dad_fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;


--
-- Name: fish_pairs fish_pairs_mom_fish_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_pairs
    ADD CONSTRAINT fish_pairs_mom_fish_id_fkey FOREIGN KEY (mom_fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;


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
-- Name: fish_pairs fk_fish_pairs_dad_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_pairs
    ADD CONSTRAINT fk_fish_pairs_dad_id FOREIGN KEY (dad_fish_id) REFERENCES public.fish(id) ON DELETE RESTRICT;


--
-- Name: fish_pairs fk_fish_pairs_mom_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_pairs
    ADD CONSTRAINT fk_fish_pairs_mom_id FOREIGN KEY (mom_fish_id) REFERENCES public.fish(id) ON DELETE RESTRICT;


--
-- Name: fish_seed_batches_map fk_fsbm_fish; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_seed_batches_map
    ADD CONSTRAINT fk_fsbm_fish FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;


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
-- Name: tank_status_history tank_status_history_tank_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_status_history
    ADD CONSTRAINT tank_status_history_tank_id_fkey FOREIGN KEY (tank_id) REFERENCES public.tanks(tank_id) ON DELETE CASCADE;


--
-- Name: objects objects_bucketId_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.objects
    ADD CONSTRAINT "objects_bucketId_fkey" FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: prefixes prefixes_bucketId_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.prefixes
    ADD CONSTRAINT "prefixes_bucketId_fkey" FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads s3_multipart_uploads_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.s3_multipart_uploads
    ADD CONSTRAINT s3_multipart_uploads_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_upload_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES storage.s3_multipart_uploads(id) ON DELETE CASCADE;


--
-- Name: audit_log_entries; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.audit_log_entries ENABLE ROW LEVEL SECURITY;

--
-- Name: flow_state; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.flow_state ENABLE ROW LEVEL SECURITY;

--
-- Name: identities; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.identities ENABLE ROW LEVEL SECURITY;

--
-- Name: instances; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.instances ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_amr_claims; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.mfa_amr_claims ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_challenges; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.mfa_challenges ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_factors; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.mfa_factors ENABLE ROW LEVEL SECURITY;

--
-- Name: one_time_tokens; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.one_time_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: refresh_tokens; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.refresh_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: saml_providers; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.saml_providers ENABLE ROW LEVEL SECURITY;

--
-- Name: saml_relay_states; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.saml_relay_states ENABLE ROW LEVEL SECURITY;

--
-- Name: schema_migrations; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.schema_migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: sessions; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.sessions ENABLE ROW LEVEL SECURITY;

--
-- Name: sso_domains; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.sso_domains ENABLE ROW LEVEL SECURITY;

--
-- Name: sso_providers; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.sso_providers ENABLE ROW LEVEL SECURITY;

--
-- Name: users; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.users ENABLE ROW LEVEL SECURITY;

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
-- Name: messages; Type: ROW SECURITY; Schema: realtime; Owner: -
--

ALTER TABLE realtime.messages ENABLE ROW LEVEL SECURITY;

--
-- Name: buckets; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.buckets ENABLE ROW LEVEL SECURITY;

--
--


--
-- Name: migrations; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: objects; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

--
-- Name: prefixes; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.prefixes ENABLE ROW LEVEL SECURITY;

--
-- Name: s3_multipart_uploads; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.s3_multipart_uploads ENABLE ROW LEVEL SECURITY;

--
-- Name: s3_multipart_uploads_parts; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.s3_multipart_uploads_parts ENABLE ROW LEVEL SECURITY;

--
--



--
-- Name: issue_graphql_placeholder; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER issue_graphql_placeholder ON sql_drop
         WHEN TAG IN ('DROP EXTENSION')
   EXECUTE FUNCTION extensions.set_graphql_placeholder();


--
-- Name: issue_pg_cron_access; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER issue_pg_cron_access ON ddl_command_end
         WHEN TAG IN ('CREATE EXTENSION')
   EXECUTE FUNCTION extensions.grant_pg_cron_access();


--
-- Name: issue_pg_graphql_access; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER issue_pg_graphql_access ON ddl_command_end
         WHEN TAG IN ('CREATE FUNCTION')
   EXECUTE FUNCTION extensions.grant_pg_graphql_access();


--
-- Name: issue_pg_net_access; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER issue_pg_net_access ON ddl_command_end
         WHEN TAG IN ('CREATE EXTENSION')
   EXECUTE FUNCTION extensions.grant_pg_net_access();


--
-- Name: pgrst_ddl_watch; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER pgrst_ddl_watch ON ddl_command_end
   EXECUTE FUNCTION extensions.pgrst_ddl_watch();


--
-- Name: pgrst_drop_watch; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER pgrst_drop_watch ON sql_drop
   EXECUTE FUNCTION extensions.pgrst_drop_watch();


--
-- PostgreSQL database dump complete
--

\unrestrict vnE7Kr2qQUFYM7DfULg0xTFbKjtg4PM2LxT4CTnEPMQsGHlcKALCAi05FPQGuzR

