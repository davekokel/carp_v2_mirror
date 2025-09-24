--
-- PostgreSQL database dump
--

\restrict KJxVpFJ92EqOWvEgZT7RoNEB9bJJzoRaMnJoHjQGe2wATCiYg9Dwowhs14ihGxx

-- Dumped from database version 17.4
-- Dumped by pg_dump version 17.6

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
-- Name: _realtime; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA _realtime;


ALTER SCHEMA _realtime OWNER TO postgres;

--
-- Name: auth; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA auth;


ALTER SCHEMA auth OWNER TO supabase_admin;

--
-- Name: extensions; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA extensions;


ALTER SCHEMA extensions OWNER TO postgres;

--
-- Name: graphql; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA graphql;


ALTER SCHEMA graphql OWNER TO supabase_admin;

--
-- Name: graphql_public; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA graphql_public;


ALTER SCHEMA graphql_public OWNER TO supabase_admin;

--
-- Name: pg_net; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions;


--
-- Name: EXTENSION pg_net; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_net IS 'Async HTTP';


--
-- Name: pgbouncer; Type: SCHEMA; Schema: -; Owner: pgbouncer
--

CREATE SCHEMA pgbouncer;


ALTER SCHEMA pgbouncer OWNER TO pgbouncer;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: postgres
--

-- *not* creating schema, since initdb creates it


ALTER SCHEMA public OWNER TO postgres;

--
-- Name: raw; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA raw;


ALTER SCHEMA raw OWNER TO postgres;

--
-- Name: realtime; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA realtime;


ALTER SCHEMA realtime OWNER TO supabase_admin;

--
-- Name: staging; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA staging;


ALTER SCHEMA staging OWNER TO postgres;

--
-- Name: storage; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA storage;


ALTER SCHEMA storage OWNER TO supabase_admin;

--
-- Name: supabase_functions; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA supabase_functions;


ALTER SCHEMA supabase_functions OWNER TO supabase_admin;

--
-- Name: supabase_migrations; Type: SCHEMA; Schema: -; Owner: postgres
--

CREATE SCHEMA supabase_migrations;


ALTER SCHEMA supabase_migrations OWNER TO postgres;

--
-- Name: vault; Type: SCHEMA; Schema: -; Owner: supabase_admin
--

CREATE SCHEMA vault;


ALTER SCHEMA vault OWNER TO supabase_admin;

--
-- Name: pg_graphql; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_graphql WITH SCHEMA graphql;


--
-- Name: EXTENSION pg_graphql; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_graphql IS 'pg_graphql: GraphQL support';


--
-- Name: pg_stat_statements; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA extensions;


--
-- Name: EXTENSION pg_stat_statements; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pg_stat_statements IS 'track planning and execution statistics of all SQL statements executed';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: supabase_vault; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS supabase_vault WITH SCHEMA vault;


--
-- Name: EXTENSION supabase_vault; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION supabase_vault IS 'Supabase Vault Extension';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA extensions;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: aal_level; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.aal_level AS ENUM (
    'aal1',
    'aal2',
    'aal3'
);


ALTER TYPE auth.aal_level OWNER TO supabase_auth_admin;

--
-- Name: code_challenge_method; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.code_challenge_method AS ENUM (
    's256',
    'plain'
);


ALTER TYPE auth.code_challenge_method OWNER TO supabase_auth_admin;

--
-- Name: factor_status; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.factor_status AS ENUM (
    'unverified',
    'verified'
);


ALTER TYPE auth.factor_status OWNER TO supabase_auth_admin;

--
-- Name: factor_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.factor_type AS ENUM (
    'totp',
    'webauthn',
    'phone'
);


ALTER TYPE auth.factor_type OWNER TO supabase_auth_admin;

--
-- Name: oauth_registration_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.oauth_registration_type AS ENUM (
    'dynamic',
    'manual'
);


ALTER TYPE auth.oauth_registration_type OWNER TO supabase_auth_admin;

--
-- Name: one_time_token_type; Type: TYPE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TYPE auth.one_time_token_type AS ENUM (
    'confirmation_token',
    'reauthentication_token',
    'recovery_token',
    'email_change_token_new',
    'email_change_token_current',
    'phone_change_token'
);


ALTER TYPE auth.one_time_token_type OWNER TO supabase_auth_admin;

--
-- Name: tank_status; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.tank_status AS ENUM (
    'inactive',
    'alive',
    'to_kill',
    'dead'
);


ALTER TYPE public.tank_status OWNER TO postgres;

--
-- Name: treatment_type_enum; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.treatment_type_enum AS ENUM (
    'injected_plasmid',
    'injected_rna',
    'dye',
    'dye_labeling'
);


ALTER TYPE public.treatment_type_enum OWNER TO postgres;

--
-- Name: action; Type: TYPE; Schema: realtime; Owner: supabase_admin
--

CREATE TYPE realtime.action AS ENUM (
    'INSERT',
    'UPDATE',
    'DELETE',
    'TRUNCATE',
    'ERROR'
);


ALTER TYPE realtime.action OWNER TO supabase_admin;

--
-- Name: equality_op; Type: TYPE; Schema: realtime; Owner: supabase_admin
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


ALTER TYPE realtime.equality_op OWNER TO supabase_admin;

--
-- Name: user_defined_filter; Type: TYPE; Schema: realtime; Owner: supabase_admin
--

CREATE TYPE realtime.user_defined_filter AS (
	column_name text,
	op realtime.equality_op,
	value text
);


ALTER TYPE realtime.user_defined_filter OWNER TO supabase_admin;

--
-- Name: wal_column; Type: TYPE; Schema: realtime; Owner: supabase_admin
--

CREATE TYPE realtime.wal_column AS (
	name text,
	type_name text,
	type_oid oid,
	value jsonb,
	is_pkey boolean,
	is_selectable boolean
);


ALTER TYPE realtime.wal_column OWNER TO supabase_admin;

--
-- Name: wal_rls; Type: TYPE; Schema: realtime; Owner: supabase_admin
--

CREATE TYPE realtime.wal_rls AS (
	wal jsonb,
	is_rls_enabled boolean,
	subscription_ids uuid[],
	errors text[]
);


ALTER TYPE realtime.wal_rls OWNER TO supabase_admin;

--
-- Name: email(); Type: FUNCTION; Schema: auth; Owner: supabase_auth_admin
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


ALTER FUNCTION auth.email() OWNER TO supabase_auth_admin;

--
-- Name: FUNCTION email(); Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON FUNCTION auth.email() IS 'Deprecated. Use auth.jwt() -> ''email'' instead.';


--
-- Name: jwt(); Type: FUNCTION; Schema: auth; Owner: supabase_auth_admin
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


ALTER FUNCTION auth.jwt() OWNER TO supabase_auth_admin;

--
-- Name: role(); Type: FUNCTION; Schema: auth; Owner: supabase_auth_admin
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


ALTER FUNCTION auth.role() OWNER TO supabase_auth_admin;

--
-- Name: FUNCTION role(); Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON FUNCTION auth.role() IS 'Deprecated. Use auth.jwt() -> ''role'' instead.';


--
-- Name: uid(); Type: FUNCTION; Schema: auth; Owner: supabase_auth_admin
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


ALTER FUNCTION auth.uid() OWNER TO supabase_auth_admin;

--
-- Name: FUNCTION uid(); Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON FUNCTION auth.uid() IS 'Deprecated. Use auth.jwt() -> ''sub'' instead.';


--
-- Name: grant_pg_cron_access(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
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


ALTER FUNCTION extensions.grant_pg_cron_access() OWNER TO supabase_admin;

--
-- Name: FUNCTION grant_pg_cron_access(); Type: COMMENT; Schema: extensions; Owner: supabase_admin
--

COMMENT ON FUNCTION extensions.grant_pg_cron_access() IS 'Grants access to pg_cron';


--
-- Name: grant_pg_graphql_access(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
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


ALTER FUNCTION extensions.grant_pg_graphql_access() OWNER TO supabase_admin;

--
-- Name: FUNCTION grant_pg_graphql_access(); Type: COMMENT; Schema: extensions; Owner: supabase_admin
--

COMMENT ON FUNCTION extensions.grant_pg_graphql_access() IS 'Grants access to pg_graphql';


--
-- Name: grant_pg_net_access(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
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
    GRANT USAGE ON SCHEMA net TO supabase_functions_admin, postgres, anon, authenticated, service_role;

    ALTER function net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) SECURITY DEFINER;
    ALTER function net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) SECURITY DEFINER;

    ALTER function net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) SET search_path = net;
    ALTER function net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) SET search_path = net;

    REVOKE ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;
    REVOKE ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;

    GRANT EXECUTE ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin, postgres, anon, authenticated, service_role;
    GRANT EXECUTE ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin, postgres, anon, authenticated, service_role;
  END IF;
END;
$$;


ALTER FUNCTION extensions.grant_pg_net_access() OWNER TO supabase_admin;

--
-- Name: FUNCTION grant_pg_net_access(); Type: COMMENT; Schema: extensions; Owner: supabase_admin
--

COMMENT ON FUNCTION extensions.grant_pg_net_access() IS 'Grants access to pg_net';


--
-- Name: pgrst_ddl_watch(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
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


ALTER FUNCTION extensions.pgrst_ddl_watch() OWNER TO supabase_admin;

--
-- Name: pgrst_drop_watch(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
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


ALTER FUNCTION extensions.pgrst_drop_watch() OWNER TO supabase_admin;

--
-- Name: set_graphql_placeholder(); Type: FUNCTION; Schema: extensions; Owner: supabase_admin
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


ALTER FUNCTION extensions.set_graphql_placeholder() OWNER TO supabase_admin;

--
-- Name: FUNCTION set_graphql_placeholder(); Type: COMMENT; Schema: extensions; Owner: supabase_admin
--

COMMENT ON FUNCTION extensions.set_graphql_placeholder() IS 'Reintroduces placeholder function for graphql_public.graphql';


--
-- Name: get_auth(text); Type: FUNCTION; Schema: pgbouncer; Owner: supabase_admin
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


ALTER FUNCTION pgbouncer.get_auth(p_usename text) OWNER TO supabase_admin;

--
-- Name: _next_tank_code(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public._next_tank_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
declare y int := extract(year from now())::int;
        n int;
begin
  select nextval('public.seq_tank_code')::int into n;
  return format('TANK-%s-%04s', public._tank_code_year(y), n);
end;
$$;


ALTER FUNCTION public._next_tank_code() OWNER TO postgres;

--
-- Name: _tank_code_year(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public._tank_code_year(y integer) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$ select lpad((y % 100)::text, 2, '0') $$;


ALTER FUNCTION public._tank_code_year(y integer) OWNER TO postgres;

--
-- Name: assert_treatment_type(text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.assert_treatment_type(expected text, tid uuid) RETURNS void
    LANGUAGE plpgsql
    AS $$
declare
  actual text;
  exp text := lower(expected);
  ok text[];
begin
  select lower(treatment_type::text) into actual
  from public.treatments
  where id_uuid = tid;

  if actual is null then
    raise exception 'Treatment % not found', tid;
  end if;

  -- Accept common aliases
  if exp in ('plasmid_injection','injected_plasmid') then
    ok := array['plasmid_injection','injected_plasmid'];
  elsif exp in ('rna_injection','injected_rna') then
    ok := array['rna_injection','injected_rna'];
  elsif exp in ('dye_injection','injected_dye') then
    ok := array['dye_injection','injected_dye'];
  else
    ok := array[exp];
  end if;

  if actual <> all(ok) and actual <> any(ok) = false then
    -- (defensive, but the previous line is sufficient in PG 12+)
    null;
  end if;

  if not (actual = any(ok)) then
    raise exception 'Treatment % must have type % (found %)', tid, exp, actual;
  end if;
end;
$$;


ALTER FUNCTION public.assert_treatment_type(expected text, tid uuid) OWNER TO postgres;

--
-- Name: assert_unique_batch_key(uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.assert_unique_batch_key(p_treatment_id uuid) RETURNS void
    LANGUAGE plpgsql
    AS $$
declare
  v_type text;
  v_performed_at timestamptz;
  v_operator text;
begin
  select lower(treatment_type::text), performed_at, operator
    into v_type, v_performed_at, v_operator
  from public.treatments
  where id_uuid = p_treatment_id;

  if v_type is null then
    perform public.pg_raise('batch_incomplete', 'treatment not found');
    return;
  end if;

  -- Require date & operator regardless of exact enum spelling
  if v_performed_at is null or coalesce(nullif(btrim(v_operator), ''), '') = '' then
    perform public.pg_raise('batch_incomplete', 'treatment is missing type/date/operator');
    return;
  end if;

  return;
end;
$$;


ALTER FUNCTION public.assert_unique_batch_key(p_treatment_id uuid) OWNER TO postgres;

--
-- Name: assign_auto_fish_code(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.assign_auto_fish_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.auto_fish_code IS NULL OR NEW.auto_fish_code = '' THEN
    NEW.auto_fish_code := public.next_auto_fish_code();
  END IF;
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.assign_auto_fish_code() OWNER TO postgres;

--
-- Name: assign_tank_label(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.assign_tank_label() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  pref text;
  code text;
BEGIN
  IF NEW.tank_label IS NULL OR NEW.tank_label = '' THEN
    pref := public.tank_prefix_for_fish(NEW.fish_id);
    code := public.next_tank_code(pref);
    NEW.tank_label := pref || '-' || code;
  END IF;
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.assign_tank_label() OWNER TO postgres;

--
-- Name: assign_tank_on_insert(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.assign_tank_on_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  prefix text;
BEGIN
  -- Only assign if there isn't already an assignment (defensive)
  IF NOT EXISTS (SELECT 1 FROM public.tank_assignments WHERE fish_id = NEW.id) THEN
    prefix := CASE
      WHEN CURRENT_DATE - COALESCE(NEW.date_of_birth::date, CURRENT_DATE) < 30 THEN 'NURSERY-'
      ELSE 'TANK-'
    END;

    INSERT INTO public.tank_assignments(fish_id, tank_label, status)
    VALUES (NEW.id, public.next_tank_code(prefix), 'inactive')
    ON CONFLICT (fish_id) DO NOTHING;
  END IF;

  RETURN NEW;
END$$;


ALTER FUNCTION public.assign_tank_on_insert() OWNER TO postgres;

--
-- Name: auto_assign_tank(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.auto_assign_tank() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  prefix text;
BEGIN
  -- choose prefix by age (fallback to TODAY if dob is null)
  IF (CURRENT_DATE - COALESCE(NEW.date_of_birth::date, CURRENT_DATE)) < 30 THEN
    prefix := 'NURSERY-';
  ELSE
    prefix := 'TANK-';
  END IF;

  -- upsert default tank (inactive). If caller already set one, keep it.
  INSERT INTO public.tank_assignments(fish_id, tank_label, status)
  VALUES (NEW.id, public.next_tank_code(prefix), 'inactive')
  ON CONFLICT (fish_id) DO NOTHING;

  RETURN NEW;
END;
$$;


ALTER FUNCTION public.auto_assign_tank() OWNER TO postgres;

--
-- Name: base36_encode(integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.base36_encode(n integer) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
  digits constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  v integer := n;
  out text := '';
  rem integer;
BEGIN
  IF v IS NULL OR v < 0 THEN
    RAISE EXCEPTION 'base36_encode expects nonnegative integer';
  END IF;
  IF v = 0 THEN
    RETURN '0';
  END IF;
  WHILE v > 0 LOOP
    rem := v % 36;
    out := substr(digits, rem+1, 1) || out;
    v := v / 36;
  END LOOP;
  RETURN out;
END;
$$;


ALTER FUNCTION public.base36_encode(n integer) OWNER TO postgres;

--
-- Name: detail_type_guard_v2(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.detail_type_guard_v2() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  actual text;
  ok     boolean := false;
BEGIN
  -- look up the base treatment_type as text
  SELECT treatment_type::text INTO actual
  FROM public.treatments
  WHERE id = NEW.treatment_id;

  IF TG_TABLE_NAME = 'injected_plasmid_treatments' THEN
    ok := (actual = 'injected_plasmid');

  ELSIF TG_TABLE_NAME = 'injected_rna_treatments' THEN
    ok := (actual = 'injected_rna');

  ELSIF TG_TABLE_NAME = 'dye_treatments' THEN
    -- accept either legacy 'dye' or current 'dye_labeling'
    ok := (actual IN ('dye','dye_labeling'));
  END IF;

  IF NOT ok THEN
    RAISE EXCEPTION 'treatment % has type %, expected %',
      NEW.treatment_id, actual, CASE
        WHEN TG_TABLE_NAME='injected_plasmid_treatments' THEN 'injected_plasmid'
        WHEN TG_TABLE_NAME='injected_rna_treatments'     THEN 'injected_rna'
        ELSE 'dye'
      END;
  END IF;

  RETURN NEW;
END
$$;


ALTER FUNCTION public.detail_type_guard_v2() OWNER TO postgres;

--
-- Name: dye_code_autofill(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.dye_code_autofill() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin if new.dye_code is null or btrim(new.dye_code)='' then new.dye_code:=public.gen_dye_code(); end if; return new; end $$;


ALTER FUNCTION public.dye_code_autofill() OWNER TO postgres;

--
-- Name: fish_code_autofill(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.fish_code_autofill() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin if new.fish_code is null or btrim(new.fish_code)='' then new.fish_code := public.gen_fish_code(coalesce(new.created_at, now())); end if; return new; end $$;


ALTER FUNCTION public.fish_code_autofill() OWNER TO postgres;

--
-- Name: gen_dye_code(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.gen_dye_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
declare k int;
begin update public.dye_counters set n=n+1 returning n into k; return format('DYE-%04s', k); end $$;


ALTER FUNCTION public.gen_dye_code() OWNER TO postgres;

--
-- Name: gen_fish_code(timestamp with time zone); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.gen_fish_code(p_ts timestamp with time zone DEFAULT now()) RETURNS text
    LANGUAGE plpgsql
    AS $$
declare y int := extract(year from p_ts);
declare k int;
begin insert into public.fish_year_counters(year,n) values (y,0) on conflict (year) do nothing;
update public.fish_year_counters set n=n+1 where year=y returning n into k;
return format('FSH-%s-%04s', y, k);
end $$;


ALTER FUNCTION public.gen_fish_code(p_ts timestamp with time zone) OWNER TO postgres;

--
-- Name: gen_plasmid_code(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.gen_plasmid_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
declare k int;
begin update public.plasmid_counters set n=n+1 returning n into k;
return format('PLM-%04s', k);
end $$;


ALTER FUNCTION public.gen_plasmid_code() OWNER TO postgres;

--
-- Name: gen_rna_code(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.gen_rna_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
declare k int;
begin update public.rna_counters set n=n+1 returning n into k; return format('RNA-%04s', k); end $$;


ALTER FUNCTION public.gen_rna_code() OWNER TO postgres;

--
-- Name: gen_tank_code(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.gen_tank_code() RETURNS text
    LANGUAGE sql
    AS $$
          select 'TANK-' || to_char(now(),'YYYY') || '-' ||
                 lpad(nextval('public.tank_counters')::text, 4, '0');
        $$;


ALTER FUNCTION public.gen_tank_code() OWNER TO postgres;

--
-- Name: make_auto_fish_code(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.make_auto_fish_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
  n bigint := nextval('fish_code_seq');
BEGIN
  RETURN 'F' || to_char(now(), 'YY') || '-' || to_char(now(), 'MMDD') || '-' || lpad(n::text, 4, '0');
END;
$$;


ALTER FUNCTION public.make_auto_fish_code() OWNER TO postgres;

--
-- Name: next_auto_fish_code(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.next_auto_fish_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
  yr_small  int  := (extract(year from current_date))::int % 100;
  yy        text := lpad(yr_small::text, 2, '0');
  seq       int;
  code      text;
BEGIN
  LOOP
    INSERT INTO public.fish_code_counters(year_small, next_seq)
    VALUES (yr_small, 1)
    ON CONFLICT (year_small) DO NOTHING;

    SELECT next_seq INTO seq
    FROM public.fish_code_counters
    WHERE year_small = yr_small
    FOR UPDATE;

    UPDATE public.fish_code_counters
    SET next_seq = seq + 1
    WHERE year_small = yr_small;

    EXIT;
  END LOOP;

  -- Format: F<yy>-<base36(seq)>, zero-padded to 3 (e.g., F25-00A)
  code := 'F' || yy || '-' || lpad(public.base36_encode(seq), 3, '0');
  RETURN code;
END;
$$;


ALTER FUNCTION public.next_auto_fish_code() OWNER TO postgres;

--
-- Name: next_tank_code(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.next_tank_code(p_prefix text) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
  yr_small int;
  yy       text;
  seq      int;
  code     text;
BEGIN
  yr_small := extract(year from current_date)::int % 100;
  yy := lpad(yr_small::text, 2, '0');

  LOOP
    -- ensure row for this prefix+year
    INSERT INTO public.tank_code_counters(prefix, year_small, next_seq)
    VALUES (p_prefix, yr_small, 1)
    ON CONFLICT (prefix, year_small) DO NOTHING;

    -- lock & read
    SELECT next_seq INTO seq
    FROM public.tank_code_counters
    WHERE prefix = p_prefix AND year_small = yr_small
    FOR UPDATE;

    -- bump
    UPDATE public.tank_code_counters
    SET next_seq = seq + 1
    WHERE prefix = p_prefix AND year_small = yr_small;

    EXIT;
  END LOOP;

  -- e.g., TANK-25A7 or NURSERY-2500A (prefix controls the literal)
  code := p_prefix || yy || lpad(public.base36_encode(seq), 3, '0');
  RETURN code;
END;
$$;


ALTER FUNCTION public.next_tank_code(p_prefix text) OWNER TO postgres;

--
-- Name: no_update_auto_fish_code(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.no_update_auto_fish_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.auto_fish_code IS DISTINCT FROM OLD.auto_fish_code THEN
    RAISE EXCEPTION 'auto_fish_code is generated and cannot be updated';
  END IF;
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.no_update_auto_fish_code() OWNER TO postgres;

--
-- Name: pg_raise(text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.pg_raise(name text, msg text) RETURNS void
    LANGUAGE plpgsql
    AS $$
begin
  raise exception using errcode = 'P0001', message = msg, constraint = name;
end $$;


ALTER FUNCTION public.pg_raise(name text, msg text) OWNER TO postgres;

--
-- Name: pg_raise(text, text, uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.pg_raise(name text, msg text, tid uuid) RETURNS void
    LANGUAGE plpgsql
    AS $$
begin
  raise exception using errcode = 'P0001', message = msg || ' ('||tid||')', constraint = name;
end $$;


ALTER FUNCTION public.pg_raise(name text, msg text, tid uuid) OWNER TO postgres;

--
-- Name: plasmid_code_autofill(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.plasmid_code_autofill() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin if new.plasmid_code is null or btrim(new.plasmid_code)='' then new.plasmid_code := public.gen_plasmid_code(); end if; return new; end $$;


ALTER FUNCTION public.plasmid_code_autofill() OWNER TO postgres;

--
-- Name: rna_code_autofill(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.rna_code_autofill() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin if new.rna_code is null or btrim(new.rna_code)='' then new.rna_code:=public.gen_rna_code(); end if; return new; end $$;


ALTER FUNCTION public.rna_code_autofill() OWNER TO postgres;

--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin new.updated_at=now(); return new; end $$;


ALTER FUNCTION public.set_updated_at() OWNER TO postgres;

--
-- Name: tank_prefix_for_fish(uuid); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.tank_prefix_for_fish(p_fish uuid) RETURNS text
    LANGUAGE sql
    AS $$
  SELECT CASE
           WHEN f.date_of_birth IS NOT NULL
                AND f.date_of_birth >= (CURRENT_DATE - INTERVAL '30 days')::date
             THEN 'NURSERY'
           ELSE 'TANK'
         END
  FROM public.fish f
  WHERE f.id = p_fish
$$;


ALTER FUNCTION public.tank_prefix_for_fish(p_fish uuid) OWNER TO postgres;

--
-- Name: treatment_batch_guard_v2(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.treatment_batch_guard_v2() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  tid_uuid uuid;
BEGIN
  IF TG_TABLE_NAME = 'treatments' THEN
    tid_uuid := NEW.id_uuid;
  ELSE
    -- detail tables now have treatment_id (→ treatments.id); look up its id_uuid
    SELECT id_uuid INTO tid_uuid
    FROM public.treatments
    WHERE id = NEW.treatment_id;
  END IF;

  PERFORM public.assert_unique_batch_key(tid_uuid);
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.treatment_batch_guard_v2() OWNER TO postgres;

--
-- Name: treatment_detail_mirror(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.treatment_detail_mirror() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  mat text;
BEGIN
  IF NEW.treatment_type = 'injected_plasmid' THEN
    -- remove any rows in other detail tables for this treatment
    DELETE FROM public.injected_rna_treatments WHERE treatment_id = NEW.id;
    DELETE FROM public.dye_treatments        WHERE treatment_id = NEW.id;

    mat := COALESCE(NULLIF(NEW.plasmid_code,''), NULL);
    IF mat IS NOT NULL THEN
      INSERT INTO public.injected_plasmid_treatments (treatment_id, plasmid_code)
      VALUES (NEW.id, mat)
      ON CONFLICT (treatment_id) DO UPDATE
        SET plasmid_code = EXCLUDED.plasmid_code;
    END IF;

  ELSIF NEW.treatment_type = 'injected_rna' THEN
    -- clean others; base table doesn’t store rna_code, detail load/refresh will populate
    DELETE FROM public.injected_plasmid_treatments WHERE treatment_id = NEW.id;
    DELETE FROM public.dye_treatments             WHERE treatment_id = NEW.id;

  ELSIF NEW.treatment_type = 'dye_labeling' THEN
    DELETE FROM public.injected_plasmid_treatments WHERE treatment_id = NEW.id;
    DELETE FROM public.injected_rna_treatments     WHERE treatment_id = NEW.id;
  END IF;

  RETURN NEW;
END
$$;


ALTER FUNCTION public.treatment_detail_mirror() OWNER TO postgres;

--
-- Name: trg_set_tank_code(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.trg_set_tank_code() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin
  if new.tank_code is null or btrim(new.tank_code) = '' then
    new.tank_code := public._next_tank_code();
  end if;
  return new;
end;
$$;


ALTER FUNCTION public.trg_set_tank_code() OWNER TO postgres;

--
-- Name: apply_rls(jsonb, integer); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
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


ALTER FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) OWNER TO supabase_admin;

--
-- Name: broadcast_changes(text, text, text, text, text, record, record, text); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
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


ALTER FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text) OWNER TO supabase_admin;

--
-- Name: build_prepared_statement_sql(text, regclass, realtime.wal_column[]); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
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


ALTER FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) OWNER TO supabase_admin;

--
-- Name: cast(text, regtype); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
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


ALTER FUNCTION realtime."cast"(val text, type_ regtype) OWNER TO supabase_admin;

--
-- Name: check_equality_op(realtime.equality_op, regtype, text, text); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
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


ALTER FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) OWNER TO supabase_admin;

--
-- Name: is_visible_through_filters(realtime.wal_column[], realtime.user_defined_filter[]); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
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


ALTER FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) OWNER TO supabase_admin;

--
-- Name: list_changes(name, name, integer, integer); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) RETURNS SETOF realtime.wal_rls
    LANGUAGE sql
    SET log_min_messages TO 'fatal'
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


ALTER FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) OWNER TO supabase_admin;

--
-- Name: quote_wal2json(regclass); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
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


ALTER FUNCTION realtime.quote_wal2json(entity regclass) OWNER TO supabase_admin;

--
-- Name: send(jsonb, text, text, boolean); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
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


ALTER FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean) OWNER TO supabase_admin;

--
-- Name: subscription_check_filters(); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
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


ALTER FUNCTION realtime.subscription_check_filters() OWNER TO supabase_admin;

--
-- Name: to_regrole(text); Type: FUNCTION; Schema: realtime; Owner: supabase_admin
--

CREATE FUNCTION realtime.to_regrole(role_name text) RETURNS regrole
    LANGUAGE sql IMMUTABLE
    AS $$ select role_name::regrole $$;


ALTER FUNCTION realtime.to_regrole(role_name text) OWNER TO supabase_admin;

--
-- Name: topic(); Type: FUNCTION; Schema: realtime; Owner: supabase_realtime_admin
--

CREATE FUNCTION realtime.topic() RETURNS text
    LANGUAGE sql STABLE
    AS $$
select nullif(current_setting('realtime.topic', true), '')::text;
$$;


ALTER FUNCTION realtime.topic() OWNER TO supabase_realtime_admin;

--
-- Name: can_insert_object(text, text, uuid, jsonb); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
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


ALTER FUNCTION storage.can_insert_object(bucketid text, name text, owner uuid, metadata jsonb) OWNER TO supabase_storage_admin;

--
-- Name: extension(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.extension(name text) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
_parts text[];
_filename text;
BEGIN
	select string_to_array(name, '/') into _parts;
	select _parts[array_length(_parts,1)] into _filename;
	-- @todo return the last part instead of 2
	return reverse(split_part(reverse(_filename), '.', 1));
END
$$;


ALTER FUNCTION storage.extension(name text) OWNER TO supabase_storage_admin;

--
-- Name: filename(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
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


ALTER FUNCTION storage.filename(name text) OWNER TO supabase_storage_admin;

--
-- Name: foldername(text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.foldername(name text) RETURNS text[]
    LANGUAGE plpgsql
    AS $$
DECLARE
_parts text[];
BEGIN
	select string_to_array(name, '/') into _parts;
	return _parts[1:array_length(_parts,1)-1];
END
$$;


ALTER FUNCTION storage.foldername(name text) OWNER TO supabase_storage_admin;

--
-- Name: get_size_by_bucket(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.get_size_by_bucket() RETURNS TABLE(size bigint, bucket_id text)
    LANGUAGE plpgsql
    AS $$
BEGIN
    return query
        select sum((metadata->>'size')::int) as size, obj.bucket_id
        from "storage".objects as obj
        group by obj.bucket_id;
END
$$;


ALTER FUNCTION storage.get_size_by_bucket() OWNER TO supabase_storage_admin;

--
-- Name: list_multipart_uploads_with_delimiter(text, text, text, integer, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
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


ALTER FUNCTION storage.list_multipart_uploads_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer, next_key_token text, next_upload_token text) OWNER TO supabase_storage_admin;

--
-- Name: list_objects_with_delimiter(text, text, text, integer, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
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


ALTER FUNCTION storage.list_objects_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer, start_after text, next_token text) OWNER TO supabase_storage_admin;

--
-- Name: operation(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.operation() RETURNS text
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    RETURN current_setting('storage.operation', true);
END;
$$;


ALTER FUNCTION storage.operation() OWNER TO supabase_storage_admin;

--
-- Name: search(text, text, integer, integer, integer, text, text, text); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.search(prefix text, bucketname text, limits integer DEFAULT 100, levels integer DEFAULT 1, offsets integer DEFAULT 0, search text DEFAULT ''::text, sortcolumn text DEFAULT 'name'::text, sortorder text DEFAULT 'asc'::text) RETURNS TABLE(name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
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


ALTER FUNCTION storage.search(prefix text, bucketname text, limits integer, levels integer, offsets integer, search text, sortcolumn text, sortorder text) OWNER TO supabase_storage_admin;

--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: storage; Owner: supabase_storage_admin
--

CREATE FUNCTION storage.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW; 
END;
$$;


ALTER FUNCTION storage.update_updated_at_column() OWNER TO supabase_storage_admin;

--
-- Name: http_request(); Type: FUNCTION; Schema: supabase_functions; Owner: supabase_functions_admin
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


ALTER FUNCTION supabase_functions.http_request() OWNER TO supabase_functions_admin;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: extensions; Type: TABLE; Schema: _realtime; Owner: postgres
--

CREATE TABLE _realtime.extensions (
    id uuid NOT NULL,
    type text,
    settings jsonb,
    tenant_external_id text,
    inserted_at timestamp(0) without time zone NOT NULL,
    updated_at timestamp(0) without time zone NOT NULL
);


ALTER TABLE _realtime.extensions OWNER TO postgres;

--
-- Name: schema_migrations; Type: TABLE; Schema: _realtime; Owner: postgres
--

CREATE TABLE _realtime.schema_migrations (
    version bigint NOT NULL,
    inserted_at timestamp(0) without time zone
);


ALTER TABLE _realtime.schema_migrations OWNER TO postgres;

--
-- Name: tenants; Type: TABLE; Schema: _realtime; Owner: supabase_admin
--

CREATE TABLE _realtime.tenants (
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


ALTER TABLE _realtime.tenants OWNER TO supabase_admin;

--
-- Name: audit_log_entries; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.audit_log_entries (
    instance_id uuid,
    id uuid NOT NULL,
    payload json,
    created_at timestamp with time zone,
    ip_address character varying(64) DEFAULT ''::character varying NOT NULL
);


ALTER TABLE auth.audit_log_entries OWNER TO supabase_auth_admin;

--
-- Name: TABLE audit_log_entries; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.audit_log_entries IS 'Auth: Audit trail for user actions.';


--
-- Name: flow_state; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
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


ALTER TABLE auth.flow_state OWNER TO supabase_auth_admin;

--
-- Name: TABLE flow_state; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.flow_state IS 'stores metadata for pkce logins';


--
-- Name: identities; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
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


ALTER TABLE auth.identities OWNER TO supabase_auth_admin;

--
-- Name: TABLE identities; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.identities IS 'Auth: Stores identities associated to a user.';


--
-- Name: COLUMN identities.email; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.identities.email IS 'Auth: Email is a generated column that references the optional email property in the identity_data';


--
-- Name: instances; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.instances (
    id uuid NOT NULL,
    uuid uuid,
    raw_base_config text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


ALTER TABLE auth.instances OWNER TO supabase_auth_admin;

--
-- Name: TABLE instances; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.instances IS 'Auth: Manages users across multiple sites.';


--
-- Name: mfa_amr_claims; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.mfa_amr_claims (
    session_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    authentication_method text NOT NULL,
    id uuid NOT NULL
);


ALTER TABLE auth.mfa_amr_claims OWNER TO supabase_auth_admin;

--
-- Name: TABLE mfa_amr_claims; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.mfa_amr_claims IS 'auth: stores authenticator method reference claims for multi factor authentication';


--
-- Name: mfa_challenges; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
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


ALTER TABLE auth.mfa_challenges OWNER TO supabase_auth_admin;

--
-- Name: TABLE mfa_challenges; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.mfa_challenges IS 'auth: stores metadata about challenge requests made';


--
-- Name: mfa_factors; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
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


ALTER TABLE auth.mfa_factors OWNER TO supabase_auth_admin;

--
-- Name: TABLE mfa_factors; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.mfa_factors IS 'auth: stores metadata about factors';


--
-- Name: oauth_clients; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.oauth_clients (
    id uuid NOT NULL,
    client_id text NOT NULL,
    client_secret_hash text NOT NULL,
    registration_type auth.oauth_registration_type NOT NULL,
    redirect_uris text NOT NULL,
    grant_types text NOT NULL,
    client_name text,
    client_uri text,
    logo_uri text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT oauth_clients_client_name_length CHECK ((char_length(client_name) <= 1024)),
    CONSTRAINT oauth_clients_client_uri_length CHECK ((char_length(client_uri) <= 2048)),
    CONSTRAINT oauth_clients_logo_uri_length CHECK ((char_length(logo_uri) <= 2048))
);


ALTER TABLE auth.oauth_clients OWNER TO supabase_auth_admin;

--
-- Name: one_time_tokens; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
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


ALTER TABLE auth.one_time_tokens OWNER TO supabase_auth_admin;

--
-- Name: refresh_tokens; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
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


ALTER TABLE auth.refresh_tokens OWNER TO supabase_auth_admin;

--
-- Name: TABLE refresh_tokens; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.refresh_tokens IS 'Auth: Store of tokens used to refresh JWT tokens once they expire.';


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE; Schema: auth; Owner: supabase_auth_admin
--

CREATE SEQUENCE auth.refresh_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE auth.refresh_tokens_id_seq OWNER TO supabase_auth_admin;

--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: auth; Owner: supabase_auth_admin
--

ALTER SEQUENCE auth.refresh_tokens_id_seq OWNED BY auth.refresh_tokens.id;


--
-- Name: saml_providers; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
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


ALTER TABLE auth.saml_providers OWNER TO supabase_auth_admin;

--
-- Name: TABLE saml_providers; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.saml_providers IS 'Auth: Manages SAML Identity Provider connections.';


--
-- Name: saml_relay_states; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
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


ALTER TABLE auth.saml_relay_states OWNER TO supabase_auth_admin;

--
-- Name: TABLE saml_relay_states; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.saml_relay_states IS 'Auth: Contains SAML Relay State information for each Service Provider initiated login.';


--
-- Name: schema_migrations; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.schema_migrations (
    version character varying(255) NOT NULL
);


ALTER TABLE auth.schema_migrations OWNER TO supabase_auth_admin;

--
-- Name: TABLE schema_migrations; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.schema_migrations IS 'Auth: Manages updates to the auth system.';


--
-- Name: sessions; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
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
    tag text
);


ALTER TABLE auth.sessions OWNER TO supabase_auth_admin;

--
-- Name: TABLE sessions; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.sessions IS 'Auth: Stores session data associated to a user.';


--
-- Name: COLUMN sessions.not_after; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.sessions.not_after IS 'Auth: Not after is a nullable column that contains a timestamp after which the session should be regarded as expired.';


--
-- Name: sso_domains; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.sso_domains (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    domain text NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    CONSTRAINT "domain not empty" CHECK ((char_length(domain) > 0))
);


ALTER TABLE auth.sso_domains OWNER TO supabase_auth_admin;

--
-- Name: TABLE sso_domains; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.sso_domains IS 'Auth: Manages SSO email address domain mapping to an SSO Identity Provider.';


--
-- Name: sso_providers; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
--

CREATE TABLE auth.sso_providers (
    id uuid NOT NULL,
    resource_id text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    disabled boolean,
    CONSTRAINT "resource_id not empty" CHECK (((resource_id = NULL::text) OR (char_length(resource_id) > 0)))
);


ALTER TABLE auth.sso_providers OWNER TO supabase_auth_admin;

--
-- Name: TABLE sso_providers; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.sso_providers IS 'Auth: Manages SSO identity provider information; see saml_providers for SAML.';


--
-- Name: COLUMN sso_providers.resource_id; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.sso_providers.resource_id IS 'Auth: Uniquely identifies a SSO provider according to a user-chosen resource ID (case insensitive), useful in infrastructure as code.';


--
-- Name: users; Type: TABLE; Schema: auth; Owner: supabase_auth_admin
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


ALTER TABLE auth.users OWNER TO supabase_auth_admin;

--
-- Name: TABLE users; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON TABLE auth.users IS 'Auth: Stores user login data within a secure schema.';


--
-- Name: COLUMN users.is_sso_user; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON COLUMN auth.users.is_sso_user IS 'Auth: Set this column to true when the account comes from SSO. These accounts can have duplicate emails.';


--
-- Name: _stag_fish_fix; Type: TABLE; Schema: public; Owner: postgres
--

CREATE UNLOGGED TABLE public._stag_fish_fix (
    name text,
    clutch text,
    started date,
    genotype text,
    background text,
    notes text
);


ALTER TABLE public._stag_fish_fix OWNER TO postgres;

--
-- Name: _stag_fish_tg_diag; Type: TABLE; Schema: public; Owner: postgres
--

CREATE UNLOGGED TABLE public._stag_fish_tg_diag (
    fish_code text,
    transgene_base_code text,
    allele_num text,
    notes text
);


ALTER TABLE public._stag_fish_tg_diag OWNER TO postgres;

--
-- Name: _staging_fish_load; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public._staging_fish_load (
    fish_name text NOT NULL,
    date_birth date,
    n_new_tanks integer DEFAULT 0 NOT NULL
);


ALTER TABLE public._staging_fish_load OWNER TO postgres;

--
-- Name: dye_counters; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.dye_counters (
    n integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.dye_counters OWNER TO postgres;

--
-- Name: dye_treatments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.dye_treatments (
    amount numeric,
    units text,
    route text,
    id uuid DEFAULT gen_random_uuid(),
    treatment_id uuid NOT NULL,
    dye_id uuid,
    dye_code text
);


ALTER TABLE public.dye_treatments OWNER TO postgres;

--
-- Name: dyes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.dyes (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    dye_code text,
    name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    description text
);


ALTER TABLE public.dyes OWNER TO postgres;

--
-- Name: fish; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.fish (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    fish_code text,
    name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    date_birth date,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    father_fish_id uuid,
    mother_fish_id uuid,
    date_of_birth date,
    line_building_stage text,
    strain text,
    description text,
    batch_label text,
    auto_fish_code text NOT NULL,
    nickname text,
    notes text,
    CONSTRAINT chk_auto_fish_code_format CHECK ((auto_fish_code ~ '^F[0-9]{2}-[0-9A-Z]{3}$'::text)),
    CONSTRAINT chk_fish_dob_not_future CHECK (((date_of_birth IS NULL) OR (date_of_birth <= CURRENT_DATE)))
);


ALTER TABLE public.fish OWNER TO postgres;

--
-- Name: fish_code_counters; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.fish_code_counters (
    year_small smallint NOT NULL,
    next_seq integer NOT NULL
);


ALTER TABLE public.fish_code_counters OWNER TO postgres;

--
-- Name: fish_code_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.fish_code_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.fish_code_seq OWNER TO postgres;

--
-- Name: fish_tanks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.fish_tanks (
    fish_name text NOT NULL,
    linked_at timestamp with time zone DEFAULT now() NOT NULL,
    fish_id uuid,
    tank_id uuid
);


ALTER TABLE public.fish_tanks OWNER TO postgres;

--
-- Name: fish_transgene_alleles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.fish_transgene_alleles (
    fish_id uuid NOT NULL,
    transgene_base_code text NOT NULL,
    allele_number text NOT NULL,
    zygosity text
);


ALTER TABLE public.fish_transgene_alleles OWNER TO postgres;

--
-- Name: fish_transgenes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.fish_transgenes (
    fish_id uuid NOT NULL,
    transgene_code text NOT NULL
);


ALTER TABLE public.fish_transgenes OWNER TO postgres;

--
-- Name: fish_treatments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.fish_treatments (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    applied_at timestamp with time zone,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_by text,
    fish_id uuid NOT NULL,
    treatment_id uuid NOT NULL
);


ALTER TABLE public.fish_treatments OWNER TO postgres;

--
-- Name: fish_year_counters; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.fish_year_counters (
    year integer NOT NULL,
    n integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.fish_year_counters OWNER TO postgres;

--
-- Name: genotypes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.genotypes (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    transgene_id_uuid uuid NOT NULL,
    zygosity text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    fish_id uuid,
    CONSTRAINT genotypes_zygosity_check CHECK ((zygosity = ANY (ARRAY['het'::text, 'hom'::text, 'wt'::text, 'unk'::text])))
);


ALTER TABLE public.genotypes OWNER TO postgres;

--
-- Name: injected_plasmid_treatments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.injected_plasmid_treatments (
    concentration_ng_per_ul numeric,
    volume_nl numeric,
    injection_stage text,
    vehicle text,
    enzyme text,
    id uuid DEFAULT gen_random_uuid(),
    treatment_id uuid NOT NULL,
    plasmid_id uuid,
    plasmid_code text
);


ALTER TABLE public.injected_plasmid_treatments OWNER TO postgres;

--
-- Name: injected_rna_treatments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.injected_rna_treatments (
    concentration_ng_per_ul numeric,
    volume_nl numeric,
    injection_stage text,
    vehicle text,
    id uuid DEFAULT gen_random_uuid(),
    treatment_id uuid NOT NULL,
    rna_id uuid,
    rna_code text
);


ALTER TABLE public.injected_rna_treatments OWNER TO postgres;

--
-- Name: plasmid_counters; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.plasmid_counters (
    n integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.plasmid_counters OWNER TO postgres;

--
-- Name: plasmids; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.plasmids (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    plasmid_code text,
    name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    description text
);


ALTER TABLE public.plasmids OWNER TO postgres;

--
-- Name: rna_counters; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.rna_counters (
    n integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.rna_counters OWNER TO postgres;

--
-- Name: rnas; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.rnas (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    rna_code text,
    name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    description text
);


ALTER TABLE public.rnas OWNER TO postgres;

--
-- Name: seed_fish_tmp; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.seed_fish_tmp (
    fish_name text,
    nickname double precision,
    date_birth text,
    line_building_stage text,
    strain text,
    has_transgene bigint,
    has_mutation bigint,
    has_treatment_injected_plasmid bigint,
    has_treatment_injected_rna bigint,
    has_treatment_dye bigint,
    n_new_tanks bigint,
    seed_batch_id text
);


ALTER TABLE public.seed_fish_tmp OWNER TO postgres;

--
-- Name: seed_transgenes_tmp; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.seed_transgenes_tmp (
    fish_name text,
    transgene_name text,
    allele_name text,
    zygosity text,
    new_allele_note double precision,
    seed_batch_id text
);


ALTER TABLE public.seed_transgenes_tmp OWNER TO postgres;

--
-- Name: seed_treatment_dye_tmp; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.seed_treatment_dye_tmp (
    fish_name text,
    dye_name text,
    operator text,
    performed_at text,
    description double precision,
    notes text,
    seed_batch_id text
);


ALTER TABLE public.seed_treatment_dye_tmp OWNER TO postgres;

--
-- Name: seed_treatment_injected_plasmid_tmp; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.seed_treatment_injected_plasmid_tmp (
    fish_name text,
    plasmid_name text,
    operator text,
    performed_at text,
    batch_label text,
    injection_mix text,
    injection_notes double precision,
    enzyme text,
    seed_batch_id text
);


ALTER TABLE public.seed_treatment_injected_plasmid_tmp OWNER TO postgres;

--
-- Name: seed_treatment_injected_rna_tmp; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.seed_treatment_injected_rna_tmp (
    fish_name text,
    rna_name text,
    operator text,
    performed_at text,
    description double precision,
    notes text,
    seed_batch_id text
);


ALTER TABLE public.seed_treatment_injected_rna_tmp OWNER TO postgres;

--
-- Name: seq_tank_code; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.seq_tank_code
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.seq_tank_code OWNER TO postgres;

--
-- Name: staging_links_dye; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.staging_links_dye (
    fish_code text,
    dye_code text,
    treatment_batch_id text,
    performed_at timestamp with time zone,
    operator text,
    amount numeric,
    units text,
    route text,
    notes text
);


ALTER TABLE public.staging_links_dye OWNER TO postgres;

--
-- Name: staging_links_dye_by_name; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.staging_links_dye_by_name (
    fish_name text,
    dye_name text,
    treatment_batch_id text,
    performed_at timestamp with time zone,
    operator text,
    amount numeric,
    units text,
    route text,
    notes text
);


ALTER TABLE public.staging_links_dye_by_name OWNER TO postgres;

--
-- Name: staging_links_injected_plasmid; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.staging_links_injected_plasmid (
    fish_code text,
    plasmid_code text,
    treatment_batch_id text,
    performed_at timestamp with time zone,
    operator text,
    concentration_ng_per_ul numeric,
    volume_nl numeric,
    injection_stage text,
    vehicle text,
    notes text
);


ALTER TABLE public.staging_links_injected_plasmid OWNER TO postgres;

--
-- Name: staging_links_injected_plasmid_by_name; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.staging_links_injected_plasmid_by_name (
    fish_name text,
    plasmid_name text,
    treatment_batch_id text,
    performed_at timestamp with time zone,
    operator text,
    concentration_ng_per_ul numeric,
    volume_nl numeric,
    injection_stage text,
    vehicle text,
    notes text,
    enzyme text
);


ALTER TABLE public.staging_links_injected_plasmid_by_name OWNER TO postgres;

--
-- Name: staging_links_injected_rna; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.staging_links_injected_rna (
    fish_code text,
    rna_code text,
    treatment_batch_id text,
    performed_at timestamp with time zone,
    operator text,
    concentration_ng_per_ul numeric,
    volume_nl numeric,
    injection_stage text,
    vehicle text,
    notes text
);


ALTER TABLE public.staging_links_injected_rna OWNER TO postgres;

--
-- Name: staging_links_injected_rna_by_name; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.staging_links_injected_rna_by_name (
    fish_name text,
    rna_name text,
    treatment_batch_id text,
    performed_at timestamp with time zone,
    operator text,
    concentration_ng_per_ul numeric,
    volume_nl numeric,
    injection_stage text,
    vehicle text,
    notes text
);


ALTER TABLE public.staging_links_injected_rna_by_name OWNER TO postgres;

--
-- Name: stg_dye; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.stg_dye (
    fish_name text,
    dye_name text,
    operator text,
    performed_at timestamp with time zone,
    notes text,
    source text
);


ALTER TABLE public.stg_dye OWNER TO postgres;

--
-- Name: stg_inj_plasmid; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.stg_inj_plasmid (
    fish_name text,
    plasmid_name text,
    operator text,
    performed_at text,
    batch_label text,
    injection_mix text,
    injection_notes text,
    enzyme text
);


ALTER TABLE public.stg_inj_plasmid OWNER TO postgres;

--
-- Name: stg_inj_rna; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.stg_inj_rna (
    fish_name text,
    rna_name text,
    operator text,
    performed_at timestamp with time zone,
    notes text,
    source text
);


ALTER TABLE public.stg_inj_rna OWNER TO postgres;

--
-- Name: tank_assignments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tank_assignments (
    fish_id uuid NOT NULL,
    tank_label text NOT NULL,
    status public.tank_status DEFAULT 'inactive'::public.tank_status NOT NULL
);


ALTER TABLE public.tank_assignments OWNER TO postgres;

--
-- Name: tank_code_counters; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tank_code_counters (
    prefix text NOT NULL,
    year_small integer NOT NULL,
    next_seq integer NOT NULL
);


ALTER TABLE public.tank_code_counters OWNER TO postgres;

--
-- Name: tank_counters; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tank_counters
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tank_counters OWNER TO postgres;

--
-- Name: tanks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tanks (
    id bigint NOT NULL,
    tank_code text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    id_uuid uuid
);


ALTER TABLE public.tanks OWNER TO postgres;

--
-- Name: tanks_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tanks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tanks_id_seq OWNER TO postgres;

--
-- Name: tanks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tanks_id_seq OWNED BY public.tanks.id;


--
-- Name: transgene_alleles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.transgene_alleles (
    transgene_base_code text NOT NULL,
    allele_number text NOT NULL,
    description text
);


ALTER TABLE public.transgene_alleles OWNER TO postgres;

--
-- Name: transgenes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.transgenes (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    allele_num text,
    transgene_base_code text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    name text,
    description text,
    code text
);


ALTER TABLE public.transgenes OWNER TO postgres;

--
-- Name: treatments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.treatments (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    treatment_type public.treatment_type_enum DEFAULT 'injected_plasmid'::public.treatment_type_enum NOT NULL,
    batch_id text,
    performed_at timestamp with time zone,
    operator text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    batch_label text,
    performed_on_date date GENERATED ALWAYS AS (((performed_at AT TIME ZONE 'America/Los_Angeles'::text))::date) STORED,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    treatment_code text,
    fish_id uuid,
    date date,
    method text,
    plasmid_code text,
    outcome text,
    code text
);


ALTER TABLE public.treatments OWNER TO postgres;

--
-- Name: v_dye_treatments; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_dye_treatments AS
 SELECT ft.fish_id,
    dt.treatment_id,
    d.name AS dye_name
   FROM ((public.fish_treatments ft
     JOIN public.dye_treatments dt ON ((dt.treatment_id = ft.treatment_id)))
     JOIN public.dyes d ON ((d.id_uuid = dt.dye_id)));


ALTER VIEW public.v_dye_treatments OWNER TO postgres;

--
-- Name: v_fish_links; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_fish_links AS
 SELECT f.fish_code,
    f.name,
    l.transgene_base_code,
    l.allele_number,
    COALESCE(l.zygosity, ''::text) AS zygosity
   FROM (public.fish_transgene_alleles l
     JOIN public.fish f ON ((f.id = l.fish_id)));


ALTER VIEW public.v_fish_links OWNER TO postgres;

--
-- Name: v_plasmid_treatments; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_plasmid_treatments AS
 SELECT ft.fish_id,
    ipt.treatment_id,
    p.name AS plasmid_name
   FROM ((public.fish_treatments ft
     JOIN public.injected_plasmid_treatments ipt ON ((ipt.treatment_id = ft.treatment_id)))
     JOIN public.plasmids p ON ((p.id_uuid = ipt.plasmid_id)));


ALTER VIEW public.v_plasmid_treatments OWNER TO postgres;

--
-- Name: v_rna_treatments; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_rna_treatments AS
 SELECT ft.fish_id,
    irt.treatment_id,
    r.name AS rna_name
   FROM ((public.fish_treatments ft
     JOIN public.injected_rna_treatments irt ON ((irt.treatment_id = ft.treatment_id)))
     JOIN public.rnas r ON ((r.id_uuid = irt.rna_id)));


ALTER VIEW public.v_rna_treatments OWNER TO postgres;

--
-- Name: v_treatments; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_treatments AS
 SELECT t.treatment_code,
    t.treatment_type,
    (t.performed_at)::date AS performed_on,
    f.fish_code,
    t.method,
    t.plasmid_code,
    COALESCE(t.outcome, ''::text) AS outcome
   FROM (public.treatments t
     JOIN public.fish f ON ((f.id = t.fish_id)));


ALTER VIEW public.v_treatments OWNER TO postgres;

--
-- Name: v_treatments_unified; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_treatments_unified AS
 SELECT t.treatment_code,
    t.treatment_type,
    (t.performed_at)::date AS performed_on,
    f.fish_code,
    t.method,
    split_part(t.treatment_code, ' | '::text, 3) AS material_code,
    COALESCE(t.outcome, ''::text) AS outcome
   FROM (public.treatments t
     JOIN public.fish f ON ((f.id = t.fish_id)));


ALTER VIEW public.v_treatments_unified OWNER TO postgres;

--
-- Name: v_treatments_dye; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_treatments_dye AS
 SELECT treatment_code,
    treatment_type,
    performed_on,
    fish_code,
    method,
    material_code,
    outcome
   FROM public.v_treatments_unified
  WHERE (treatment_type = 'dye_labeling'::public.treatment_type_enum);


ALTER VIEW public.v_treatments_dye OWNER TO postgres;

--
-- Name: v_treatments_expanded; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_treatments_expanded AS
 SELECT t.id,
    t.treatment_code,
    t.treatment_type,
    t.performed_at,
    t.date,
    f.fish_code,
    t.method,
    COALESCE(ip.plasmid_code, ir.rna_code, d.dye_code, t.plasmid_code) AS material_code,
    t.operator,
    t.notes,
    t.outcome
   FROM ((((public.treatments t
     JOIN public.fish f ON ((f.id = t.fish_id)))
     LEFT JOIN public.injected_plasmid_treatments ip ON ((ip.treatment_id = t.id)))
     LEFT JOIN public.injected_rna_treatments ir ON ((ir.treatment_id = t.id)))
     LEFT JOIN public.dye_treatments d ON ((d.treatment_id = t.id)));


ALTER VIEW public.v_treatments_expanded OWNER TO postgres;

--
-- Name: v_treatments_join; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_treatments_join AS
 SELECT t.treatment_code,
    t.treatment_type,
    t.performed_at,
    t.date,
    f.fish_code,
    t.plasmid_code,
    t.operator,
    t.method,
    t.outcome
   FROM (public.treatments t
     JOIN public.fish f ON ((f.id = t.fish_id)));


ALTER VIEW public.v_treatments_join OWNER TO postgres;

--
-- Name: v_treatments_plasmid; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_treatments_plasmid AS
 SELECT treatment_code,
    treatment_type,
    performed_on,
    fish_code,
    method,
    material_code,
    outcome
   FROM public.v_treatments_unified
  WHERE (treatment_type = 'injected_plasmid'::public.treatment_type_enum);


ALTER VIEW public.v_treatments_plasmid OWNER TO postgres;

--
-- Name: v_treatments_rna; Type: VIEW; Schema: public; Owner: postgres
--

CREATE VIEW public.v_treatments_rna AS
 SELECT treatment_code,
    treatment_type,
    performed_on,
    fish_code,
    method,
    material_code,
    outcome
   FROM public.v_treatments_unified
  WHERE (treatment_type = 'injected_rna'::public.treatment_type_enum);


ALTER VIEW public.v_treatments_rna OWNER TO postgres;

--
-- Name: fish_csv; Type: TABLE; Schema: raw; Owner: postgres
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


ALTER TABLE raw.fish_csv OWNER TO postgres;

--
-- Name: fish_links_has_transgenes_csv; Type: TABLE; Schema: raw; Owner: postgres
--

CREATE TABLE raw.fish_links_has_transgenes_csv (
    fish_name text,
    transgene_name text,
    allele_name text,
    zygosity text,
    new_allele_note text
);


ALTER TABLE raw.fish_links_has_transgenes_csv OWNER TO postgres;

--
-- Name: fish_links_has_treatment_dye_csv; Type: TABLE; Schema: raw; Owner: postgres
--

CREATE TABLE raw.fish_links_has_treatment_dye_csv (
    fish_name text,
    dye_name text,
    operator text,
    performed_at text,
    description text,
    notes text
);


ALTER TABLE raw.fish_links_has_treatment_dye_csv OWNER TO postgres;

--
-- Name: fish_links_has_treatment_injected_plasmid_csv; Type: TABLE; Schema: raw; Owner: postgres
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


ALTER TABLE raw.fish_links_has_treatment_injected_plasmid_csv OWNER TO postgres;

--
-- Name: fish_links_has_treatment_injected_rna_csv; Type: TABLE; Schema: raw; Owner: postgres
--

CREATE TABLE raw.fish_links_has_treatment_injected_rna_csv (
    fish_name text,
    rna_name text,
    operator text,
    performed_at text,
    description text,
    notes text
);


ALTER TABLE raw.fish_links_has_treatment_injected_rna_csv OWNER TO postgres;

--
-- Name: messages; Type: TABLE; Schema: realtime; Owner: supabase_realtime_admin
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


ALTER TABLE realtime.messages OWNER TO supabase_realtime_admin;

--
-- Name: messages_2025_09_21; Type: TABLE; Schema: realtime; Owner: postgres
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


ALTER TABLE realtime.messages_2025_09_21 OWNER TO postgres;

--
-- Name: messages_2025_09_22; Type: TABLE; Schema: realtime; Owner: postgres
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


ALTER TABLE realtime.messages_2025_09_22 OWNER TO postgres;

--
-- Name: messages_2025_09_23; Type: TABLE; Schema: realtime; Owner: postgres
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


ALTER TABLE realtime.messages_2025_09_23 OWNER TO postgres;

--
-- Name: messages_2025_09_24; Type: TABLE; Schema: realtime; Owner: postgres
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


ALTER TABLE realtime.messages_2025_09_24 OWNER TO postgres;

--
-- Name: messages_2025_09_25; Type: TABLE; Schema: realtime; Owner: postgres
--

CREATE TABLE realtime.messages_2025_09_25 (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


ALTER TABLE realtime.messages_2025_09_25 OWNER TO postgres;

--
-- Name: schema_migrations; Type: TABLE; Schema: realtime; Owner: supabase_admin
--

CREATE TABLE realtime.schema_migrations (
    version bigint NOT NULL,
    inserted_at timestamp(0) without time zone
);


ALTER TABLE realtime.schema_migrations OWNER TO supabase_admin;

--
-- Name: subscription; Type: TABLE; Schema: realtime; Owner: supabase_admin
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


ALTER TABLE realtime.subscription OWNER TO supabase_admin;

--
-- Name: subscription_id_seq; Type: SEQUENCE; Schema: realtime; Owner: supabase_admin
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
-- Name: _dye_csv; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging._dye_csv (
    fish_name text,
    treatment_date date,
    material_code text,
    treatment_type text,
    operator text,
    notes text
);


ALTER TABLE staging._dye_csv OWNER TO postgres;

--
-- Name: _fish_csv; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging._fish_csv (
    name text
);


ALTER TABLE staging._fish_csv OWNER TO postgres;

--
-- Name: _fish_names; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging._fish_names (
    name text
);


ALTER TABLE staging._fish_names OWNER TO postgres;

--
-- Name: _fish_raw; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging._fish_raw (
    col1 text,
    col2 text,
    col3 text,
    col4 text,
    col5 text,
    col6 text
);


ALTER TABLE staging._fish_raw OWNER TO postgres;

--
-- Name: _plasmid_csv; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging._plasmid_csv (
    fish_name text,
    treatment_date date,
    material_code text,
    treatment_type text,
    operator text,
    notes text
);


ALTER TABLE staging._plasmid_csv OWNER TO postgres;

--
-- Name: _rna_csv; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging._rna_csv (
    fish_name text,
    treatment_date date,
    material_code text,
    treatment_type text,
    operator text,
    notes text
);


ALTER TABLE staging._rna_csv OWNER TO postgres;

--
-- Name: core_dye_treatments_csv; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.core_dye_treatments_csv (
    fish_code text,
    treatment_date text,
    dye_code text,
    method text,
    operator text,
    notes text
);


ALTER TABLE staging.core_dye_treatments_csv OWNER TO postgres;

--
-- Name: core_dyes_csv; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.core_dyes_csv (
    dye_code text,
    name text,
    description text
);


ALTER TABLE staging.core_dyes_csv OWNER TO postgres;

--
-- Name: core_fish_csv; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.core_fish_csv (
    fish_code text,
    name text,
    date_of_birth text,
    line_building_stage text,
    strain text,
    description text
);


ALTER TABLE staging.core_fish_csv OWNER TO postgres;

--
-- Name: core_fish_transgene_alleles_csv; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.core_fish_transgene_alleles_csv (
    fish_code text,
    transgene_base_code text,
    allele_number text,
    zygosity text
);


ALTER TABLE staging.core_fish_transgene_alleles_csv OWNER TO postgres;

--
-- Name: core_plasmids_csv; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.core_plasmids_csv (
    plasmid_code text,
    name text,
    description text
);


ALTER TABLE staging.core_plasmids_csv OWNER TO postgres;

--
-- Name: core_rna_treatments_csv; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.core_rna_treatments_csv (
    fish_code text,
    treatment_date text,
    rna_code text,
    method text,
    operator text,
    notes text
);


ALTER TABLE staging.core_rna_treatments_csv OWNER TO postgres;

--
-- Name: core_rnas_csv; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.core_rnas_csv (
    rna_code text,
    name text,
    description text
);


ALTER TABLE staging.core_rnas_csv OWNER TO postgres;

--
-- Name: core_transgene_alleles_csv; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.core_transgene_alleles_csv (
    transgene_base_code text,
    allele_number text,
    description text
);


ALTER TABLE staging.core_transgene_alleles_csv OWNER TO postgres;

--
-- Name: core_transgenes_csv; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.core_transgenes_csv (
    transgene_base_code text,
    name text,
    description text
);


ALTER TABLE staging.core_transgenes_csv OWNER TO postgres;

--
-- Name: core_treatments_csv; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.core_treatments_csv (
    fish_code text,
    treatment_date text,
    material text,
    plasmid_code text,
    method text,
    operator text,
    notes text
);


ALTER TABLE staging.core_treatments_csv OWNER TO postgres;

--
-- Name: core_treatments_unified_csv; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.core_treatments_unified_csv (
    fish_code text,
    treatment_date text,
    treatment_type text,
    material_code text,
    method text,
    operator text,
    notes text
);


ALTER TABLE staging.core_treatments_unified_csv OWNER TO postgres;

--
-- Name: fish_transgene_alleles; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.fish_transgene_alleles (
    fish_name text,
    transgene_base_code text,
    allele_number integer,
    zygosity text
);


ALTER TABLE staging.fish_transgene_alleles OWNER TO postgres;

--
-- Name: links_fish_transgene_alleles; Type: TABLE; Schema: staging; Owner: postgres
--

CREATE TABLE staging.links_fish_transgene_alleles (
    fish_name text,
    transgene_base_code text,
    allele_number integer,
    zygosity text
);


ALTER TABLE staging.links_fish_transgene_alleles OWNER TO postgres;

--
-- Name: v_all_treatments_text; Type: VIEW; Schema: staging; Owner: postgres
--

CREATE VIEW staging.v_all_treatments_text AS
 SELECT lower(TRIM(BOTH FROM _plasmid_csv.fish_name)) AS fish_name_lc,
    lower(TRIM(BOTH FROM _plasmid_csv.treatment_type)) AS treatment_type,
    TRIM(BOTH FROM _plasmid_csv.material_code) AS material_code,
    (_plasmid_csv.treatment_date)::text AS performed_at_txt,
    NULLIF(TRIM(BOTH FROM _plasmid_csv.operator), ''::text) AS operator,
    NULLIF(TRIM(BOTH FROM _plasmid_csv.notes), ''::text) AS notes
   FROM staging._plasmid_csv
UNION ALL
 SELECT lower(TRIM(BOTH FROM _rna_csv.fish_name)) AS fish_name_lc,
    lower(TRIM(BOTH FROM _rna_csv.treatment_type)) AS treatment_type,
    TRIM(BOTH FROM _rna_csv.material_code) AS material_code,
    (_rna_csv.treatment_date)::text AS performed_at_txt,
    NULLIF(TRIM(BOTH FROM _rna_csv.operator), ''::text) AS operator,
    NULLIF(TRIM(BOTH FROM _rna_csv.notes), ''::text) AS notes
   FROM staging._rna_csv
UNION ALL
 SELECT lower(TRIM(BOTH FROM _dye_csv.fish_name)) AS fish_name_lc,
    lower(TRIM(BOTH FROM _dye_csv.treatment_type)) AS treatment_type,
    TRIM(BOTH FROM _dye_csv.material_code) AS material_code,
    (_dye_csv.treatment_date)::text AS performed_at_txt,
    NULLIF(TRIM(BOTH FROM _dye_csv.operator), ''::text) AS operator,
    NULLIF(TRIM(BOTH FROM _dye_csv.notes), ''::text) AS notes
   FROM staging._dye_csv;


ALTER VIEW staging.v_all_treatments_text OWNER TO postgres;

--
-- Name: v_all_treatments; Type: VIEW; Schema: staging; Owner: postgres
--

CREATE VIEW staging.v_all_treatments AS
 SELECT fish_name_lc,
    treatment_type,
    material_code,
    ((performed_at_txt || ' 00:00:00+00'::text))::timestamp with time zone AS performed_at,
    operator,
    notes
   FROM staging.v_all_treatments_text;


ALTER VIEW staging.v_all_treatments OWNER TO postgres;

--
-- Name: buckets; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
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
    owner_id text
);


ALTER TABLE storage.buckets OWNER TO supabase_storage_admin;

--
-- Name: COLUMN buckets.owner; Type: COMMENT; Schema: storage; Owner: supabase_storage_admin
--

COMMENT ON COLUMN storage.buckets.owner IS 'Field is deprecated, use owner_id instead';


--
-- Name: migrations; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
--

CREATE TABLE storage.migrations (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    hash character varying(40) NOT NULL,
    executed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE storage.migrations OWNER TO supabase_storage_admin;

--
-- Name: objects; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
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
    user_metadata jsonb
);


ALTER TABLE storage.objects OWNER TO supabase_storage_admin;

--
-- Name: COLUMN objects.owner; Type: COMMENT; Schema: storage; Owner: supabase_storage_admin
--

COMMENT ON COLUMN storage.objects.owner IS 'Field is deprecated, use owner_id instead';


--
-- Name: s3_multipart_uploads; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
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


ALTER TABLE storage.s3_multipart_uploads OWNER TO supabase_storage_admin;

--
-- Name: s3_multipart_uploads_parts; Type: TABLE; Schema: storage; Owner: supabase_storage_admin
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


ALTER TABLE storage.s3_multipart_uploads_parts OWNER TO supabase_storage_admin;

--
-- Name: hooks; Type: TABLE; Schema: supabase_functions; Owner: supabase_functions_admin
--

CREATE TABLE supabase_functions.hooks (
    id bigint NOT NULL,
    hook_table_id integer NOT NULL,
    hook_name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    request_id bigint
);


ALTER TABLE supabase_functions.hooks OWNER TO supabase_functions_admin;

--
-- Name: TABLE hooks; Type: COMMENT; Schema: supabase_functions; Owner: supabase_functions_admin
--

COMMENT ON TABLE supabase_functions.hooks IS 'Supabase Functions Hooks: Audit trail for triggered hooks.';


--
-- Name: hooks_id_seq; Type: SEQUENCE; Schema: supabase_functions; Owner: supabase_functions_admin
--

CREATE SEQUENCE supabase_functions.hooks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE supabase_functions.hooks_id_seq OWNER TO supabase_functions_admin;

--
-- Name: hooks_id_seq; Type: SEQUENCE OWNED BY; Schema: supabase_functions; Owner: supabase_functions_admin
--

ALTER SEQUENCE supabase_functions.hooks_id_seq OWNED BY supabase_functions.hooks.id;


--
-- Name: migrations; Type: TABLE; Schema: supabase_functions; Owner: supabase_functions_admin
--

CREATE TABLE supabase_functions.migrations (
    version text NOT NULL,
    inserted_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE supabase_functions.migrations OWNER TO supabase_functions_admin;

--
-- Name: schema_migrations; Type: TABLE; Schema: supabase_migrations; Owner: postgres
--

CREATE TABLE supabase_migrations.schema_migrations (
    version text NOT NULL,
    statements text[],
    name text
);


ALTER TABLE supabase_migrations.schema_migrations OWNER TO postgres;

--
-- Name: seed_files; Type: TABLE; Schema: supabase_migrations; Owner: postgres
--

CREATE TABLE supabase_migrations.seed_files (
    path text NOT NULL,
    hash text NOT NULL
);


ALTER TABLE supabase_migrations.seed_files OWNER TO postgres;

--
-- Name: messages_2025_09_21; Type: TABLE ATTACH; Schema: realtime; Owner: postgres
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_09_21 FOR VALUES FROM ('2025-09-21 00:00:00') TO ('2025-09-22 00:00:00');


--
-- Name: messages_2025_09_22; Type: TABLE ATTACH; Schema: realtime; Owner: postgres
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_09_22 FOR VALUES FROM ('2025-09-22 00:00:00') TO ('2025-09-23 00:00:00');


--
-- Name: messages_2025_09_23; Type: TABLE ATTACH; Schema: realtime; Owner: postgres
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_09_23 FOR VALUES FROM ('2025-09-23 00:00:00') TO ('2025-09-24 00:00:00');


--
-- Name: messages_2025_09_24; Type: TABLE ATTACH; Schema: realtime; Owner: postgres
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_09_24 FOR VALUES FROM ('2025-09-24 00:00:00') TO ('2025-09-25 00:00:00');


--
-- Name: messages_2025_09_25; Type: TABLE ATTACH; Schema: realtime; Owner: postgres
--

ALTER TABLE ONLY realtime.messages ATTACH PARTITION realtime.messages_2025_09_25 FOR VALUES FROM ('2025-09-25 00:00:00') TO ('2025-09-26 00:00:00');


--
-- Name: refresh_tokens id; Type: DEFAULT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.refresh_tokens ALTER COLUMN id SET DEFAULT nextval('auth.refresh_tokens_id_seq'::regclass);


--
-- Name: tanks id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tanks ALTER COLUMN id SET DEFAULT nextval('public.tanks_id_seq'::regclass);


--
-- Name: hooks id; Type: DEFAULT; Schema: supabase_functions; Owner: supabase_functions_admin
--

ALTER TABLE ONLY supabase_functions.hooks ALTER COLUMN id SET DEFAULT nextval('supabase_functions.hooks_id_seq'::regclass);


--
-- Data for Name: extensions; Type: TABLE DATA; Schema: _realtime; Owner: postgres
--

COPY _realtime.extensions (id, type, settings, tenant_external_id, inserted_at, updated_at) FROM stdin;
23ba39c4-9335-42fa-bbc0-e2b3311efd3a	postgres_cdc_rls	{"region": "us-east-1", "db_host": "39cIa22qVeem+tEFRfMf6J2PLVqM1H/a6V9Ri/svTTQ=", "db_name": "sWBpZNdjggEPTQVlI52Zfw==", "db_port": "+enMDFi1J/3IrrquHHwUmA==", "db_user": "uxbEq/zz8DXVD53TOI1zmw==", "slot_name": "supabase_realtime_replication_slot", "db_password": "sWBpZNdjggEPTQVlI52Zfw==", "publication": "supabase_realtime", "ssl_enforced": false, "poll_interval_ms": 100, "poll_max_changes": 100, "poll_max_record_bytes": 1048576}	realtime-dev	2025-09-22 23:22:48	2025-09-22 23:22:48
\.


--
-- Data for Name: schema_migrations; Type: TABLE DATA; Schema: _realtime; Owner: postgres
--

COPY _realtime.schema_migrations (version, inserted_at) FROM stdin;
20210706140551	2025-09-22 23:22:33
20220329161857	2025-09-22 23:22:33
20220410212326	2025-09-22 23:22:33
20220506102948	2025-09-22 23:22:33
20220527210857	2025-09-22 23:22:33
20220815211129	2025-09-22 23:22:33
20220815215024	2025-09-22 23:22:33
20220818141501	2025-09-22 23:22:33
20221018173709	2025-09-22 23:22:33
20221102172703	2025-09-22 23:22:33
20221223010058	2025-09-22 23:22:33
20230110180046	2025-09-22 23:22:33
20230810220907	2025-09-22 23:22:33
20230810220924	2025-09-22 23:22:33
20231024094642	2025-09-22 23:22:33
20240306114423	2025-09-22 23:22:33
20240418082835	2025-09-22 23:22:33
20240625211759	2025-09-22 23:22:33
20240704172020	2025-09-22 23:22:33
20240902173232	2025-09-22 23:22:33
20241106103258	2025-09-22 23:22:33
20250424203323	2025-09-22 23:22:33
20250613072131	2025-09-22 23:22:33
20250711044927	2025-09-22 23:22:33
20250811121559	2025-09-22 23:22:33
\.


--
-- Data for Name: tenants; Type: TABLE DATA; Schema: _realtime; Owner: supabase_admin
--

COPY _realtime.tenants (id, name, external_id, jwt_secret, max_concurrent_users, inserted_at, updated_at, max_events_per_second, postgres_cdc_default, max_bytes_per_second, max_channels_per_client, max_joins_per_second, suspend, jwt_jwks, notify_private_alpha, private_only, migrations_ran, broadcast_adapter, max_presence_events_per_second, max_payload_size_in_kb) FROM stdin;
98f2ec0a-6b45-4a2a-bd44-7b8d375fd97b	realtime-dev	realtime-dev	iNjicxc4+llvc9wovDvqymwfnj9teWMlyOIbJ8Fh6j2WNU8CIJ2ZgjR6MUIKqSmeDmvpsKLsZ9jgXJmQPpwL8w==	200	2025-09-22 23:22:48	2025-09-22 23:22:48	100	postgres_cdc_rls	100000	100	100	f	{"keys": [{"k": "c3VwZXItc2VjcmV0LWp3dC10b2tlbi13aXRoLWF0LWxlYXN0LTMyLWNoYXJhY3RlcnMtbG9uZw", "kty": "oct"}]}	f	f	63	gen_rpc	10000	3000
\.


--
-- Data for Name: audit_log_entries; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.audit_log_entries (instance_id, id, payload, created_at, ip_address) FROM stdin;
\.


--
-- Data for Name: flow_state; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.flow_state (id, user_id, auth_code, code_challenge_method, code_challenge, provider_type, provider_access_token, provider_refresh_token, created_at, updated_at, authentication_method, auth_code_issued_at) FROM stdin;
\.


--
-- Data for Name: identities; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.identities (provider_id, user_id, identity_data, provider, last_sign_in_at, created_at, updated_at, id) FROM stdin;
\.


--
-- Data for Name: instances; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.instances (id, uuid, raw_base_config, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: mfa_amr_claims; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.mfa_amr_claims (session_id, created_at, updated_at, authentication_method, id) FROM stdin;
\.


--
-- Data for Name: mfa_challenges; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.mfa_challenges (id, factor_id, created_at, verified_at, ip_address, otp_code, web_authn_session_data) FROM stdin;
\.


--
-- Data for Name: mfa_factors; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.mfa_factors (id, user_id, friendly_name, factor_type, status, created_at, updated_at, secret, phone, last_challenged_at, web_authn_credential, web_authn_aaguid) FROM stdin;
\.


--
-- Data for Name: oauth_clients; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.oauth_clients (id, client_id, client_secret_hash, registration_type, redirect_uris, grant_types, client_name, client_uri, logo_uri, created_at, updated_at, deleted_at) FROM stdin;
\.


--
-- Data for Name: one_time_tokens; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.one_time_tokens (id, user_id, token_type, token_hash, relates_to, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: refresh_tokens; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.refresh_tokens (instance_id, id, token, user_id, revoked, created_at, updated_at, parent, session_id) FROM stdin;
\.


--
-- Data for Name: saml_providers; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.saml_providers (id, sso_provider_id, entity_id, metadata_xml, metadata_url, attribute_mapping, created_at, updated_at, name_id_format) FROM stdin;
\.


--
-- Data for Name: saml_relay_states; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.saml_relay_states (id, sso_provider_id, request_id, for_email, redirect_to, created_at, updated_at, flow_state_id) FROM stdin;
\.


--
-- Data for Name: schema_migrations; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.schema_migrations (version) FROM stdin;
20171026211738
20171026211808
20171026211834
20180103212743
20180108183307
20180119214651
20180125194653
00
20210710035447
20210722035447
20210730183235
20210909172000
20210927181326
20211122151130
20211124214934
20211202183645
20220114185221
20220114185340
20220224000811
20220323170000
20220429102000
20220531120530
20220614074223
20220811173540
20221003041349
20221003041400
20221011041400
20221020193600
20221021073300
20221021082433
20221027105023
20221114143122
20221114143410
20221125140132
20221208132122
20221215195500
20221215195800
20221215195900
20230116124310
20230116124412
20230131181311
20230322519590
20230402418590
20230411005111
20230508135423
20230523124323
20230818113222
20230914180801
20231027141322
20231114161723
20231117164230
20240115144230
20240214120130
20240306115329
20240314092811
20240427152123
20240612123726
20240729123726
20240802193726
20240806073726
20241009103726
20250717082212
20250731150234
\.


--
-- Data for Name: sessions; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.sessions (id, user_id, created_at, updated_at, factor_id, aal, not_after, refreshed_at, user_agent, ip, tag) FROM stdin;
\.


--
-- Data for Name: sso_domains; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.sso_domains (id, sso_provider_id, domain, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: sso_providers; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.sso_providers (id, resource_id, created_at, updated_at, disabled) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: auth; Owner: supabase_auth_admin
--

COPY auth.users (instance_id, id, aud, role, email, encrypted_password, email_confirmed_at, invited_at, confirmation_token, confirmation_sent_at, recovery_token, recovery_sent_at, email_change_token_new, email_change, email_change_sent_at, last_sign_in_at, raw_app_meta_data, raw_user_meta_data, is_super_admin, created_at, updated_at, phone, phone_confirmed_at, phone_change, phone_change_token, phone_change_sent_at, email_change_token_current, email_change_confirm_status, banned_until, reauthentication_token, reauthentication_sent_at, is_sso_user, deleted_at, is_anonymous) FROM stdin;
\.


--
-- Data for Name: _stag_fish_fix; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public._stag_fish_fix (name, clutch, started, genotype, background, notes) FROM stdin;
\.


--
-- Data for Name: _stag_fish_tg_diag; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public._stag_fish_tg_diag (fish_code, transgene_base_code, allele_num, notes) FROM stdin;
fish-201	elavl3_gcamp6s	a201	unknown
fish-202	elavl3_gcamp6s	a202	het
fish-203	elavl3_gcamp6s	a201	het
fish-204	myo6b_chr2	b201	unknown
\.


--
-- Data for Name: _staging_fish_load; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public._staging_fish_load (fish_name, date_birth, n_new_tanks) FROM stdin;
\.


--
-- Data for Name: dye_counters; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.dye_counters (n) FROM stdin;
\.


--
-- Data for Name: dye_treatments; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.dye_treatments (amount, units, route, id, treatment_id, dye_id, dye_code) FROM stdin;
\.


--
-- Data for Name: dyes; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.dyes (id_uuid, dye_code, name, created_at, created_by, description) FROM stdin;
1ead0f04-2f6d-48ef-b3a0-6726b4ca139c	dye-dil	DiI	2025-09-23 05:44:54.270702+00	\N	lipophilic carbocyanine dye
721afc49-98fe-4cc2-8e57-7d7c88712538	dexa	Dextran-Alexa488	2025-09-23 06:01:25.803829+00	\N	fixable dextran dye
\.


--
-- Data for Name: fish; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.fish (id_uuid, fish_code, name, created_at, created_by, date_birth, id, father_fish_id, mother_fish_id, date_of_birth, line_building_stage, strain, description, batch_label, auto_fish_code, nickname, notes) FROM stdin;
35eb0d7d-37c1-47d5-a206-e517bd25e273	FSH-2025-   9	mem-tdmSG-8m	2025-09-24 11:34:40.804233+00	\N	\N	5cc4540b-c8a7-46d6-a477-5ba21b34a030	\N	\N	2024-08-16	founder	casper	multiple alleles, male founder #8	2025-09-22-2205-seedkit_transgene_alleles_dqm	F25-002	membrane-tandem-mStayGold	\N
076a6623-df21-403a-b6f4-7e4437ade505	FSH-2025-  10	mem-tdmSG-11m	2025-09-24 11:34:40.804233+00	\N	\N	cc8671ac-57d6-4d92-a830-305cff5ddd44	\N	\N	2024-08-16	founder	casper	multiple alleles, male founder #11	2025-09-22-2205-seedkit_transgene_alleles_dqm	F25-003	membrane-tandem-mStayGold	\N
d1d09b73-a23d-4396-ac91-86334fc1abbb	FSH-2025-  11	mem-tdmSG-8m-F1	2025-09-24 11:34:40.804233+00	\N	\N	6fdf5241-a670-47b6-8eb4-c414bd0431d0	\N	\N	2024-11-12	F1	casper	multiple alleles, selected brightest	2025-09-22-2205-seedkit_transgene_alleles_dqm	F25-004	membrane-tandem-mStayGold	\N
339a0a51-759d-4acd-a600-085bb52cfe6c	FSH-2025-  12	mem-tdmSG-11m-F1	2025-09-24 11:34:40.804233+00	\N	\N	c8fe0f58-4d8f-471a-86b6-9e8ad1f12a44	\N	\N	2024-11-25	F1	casper	multiple alleles, selected brightest	2025-09-22-2205-seedkit_transgene_alleles_dqm	F25-005	membrane-tandem-mStayGold	\N
ea5fb1d3-f34c-4645-ba55-8b63015eeb81	FSH-2025-  13	mem-tdmSG-8m-F2	2025-09-24 11:34:40.804233+00	\N	\N	22779c02-7386-4a7a-9afb-7e950a0be0a7	\N	\N	2025-04-17	F2	casper	multiple alleles, selected brightest, check for homozygosity	2025-09-22-2205-seedkit_transgene_alleles_dqm	F25-006	membrane-tandem-mStayGold	\N
2a791ad5-3937-4adc-8e75-9f9fefc3fc70	FSH-2025-  14	mem-tdmSG-11m-F2	2025-09-24 11:34:40.804233+00	\N	\N	51e4e205-42ac-414c-bfb1-be100bbe6890	\N	\N	2025-03-03	F2	casper	multiple alleles, selected brightest, check for homozygosity	2025-09-22-2205-seedkit_transgene_alleles_dqm	F25-007	membrane-tandem-mStayGold	\N
49422857-84a1-403a-b7c0-199b7f682510	FSH-2025-   5	fish-201	2025-09-24 10:26:17.48027+00	\N	\N	4db5d7f1-00e5-4874-8d7f-b494f279247b	\N	\N	2025-08-11	founder	casper	baseline founder for elavl3 line	2025-09-22-2215-seedkit_transgene_alleles	F25-001	epsilon	baseline founder for elavl3 line
23b48d57-be05-47cc-8548-02124b2f3f87	FSH-2025-   6	fish-202	2025-09-24 10:26:17.48027+00	\N	\N	b32b4684-a282-468d-b04d-c86887e41cd7	\N	\N	2024-08-15	founder	AB	alternate genetic background	2025-09-22-2215-seedkit_transgene_alleles	F25-008	zeta	alternate genetic background
126db791-90d3-45c7-a81e-d9cba292821a	FSH-2025-   7	fish-203	2025-09-24 10:26:17.48027+00	\N	\N	6ae2c96b-2a23-4f2f-9176-69e6eb114a33	\N	\N	2025-07-30	F1	mixed	offspring from elavl3 founder cross	2025-09-22-2215-seedkit_transgene_alleles	F25-009	eta	offspring from elavl3 founder cross
fe4a81e4-d277-4266-8cdc-c4851b55a20d	FSH-2025-   8	fish-204	2025-09-24 10:26:17.48027+00	\N	\N	192507f2-277d-4c9e-b7ca-45fe3bfe04f8	\N	\N	2025-07-28	F1	casper	offspring from myo6b founder cross	2025-09-22-2215-seedkit_transgene_alleles	F25-00A	theta	offspring from myo6b founder cross
\.


--
-- Data for Name: fish_code_counters; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.fish_code_counters (year_small, next_seq) FROM stdin;
2025	1
25	29
\.


--
-- Data for Name: fish_tanks; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.fish_tanks (fish_name, linked_at, fish_id, tank_id) FROM stdin;
\.


--
-- Data for Name: fish_transgene_alleles; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number, zygosity) FROM stdin;
4db5d7f1-00e5-4874-8d7f-b494f279247b	elavl3_gcamp6s	a201	unknown
b32b4684-a282-468d-b04d-c86887e41cd7	elavl3_gcamp6s	a202	het
6ae2c96b-2a23-4f2f-9176-69e6eb114a33	elavl3_gcamp6s	a201	het
192507f2-277d-4c9e-b7ca-45fe3bfe04f8	myo6b_chr2	b201	unknown
5cc4540b-c8a7-46d6-a477-5ba21b34a030	pDQM005	301	unknown
cc8671ac-57d6-4d92-a830-305cff5ddd44	pDQM005	302	unknown
6fdf5241-a670-47b6-8eb4-c414bd0431d0	pDQM005	301	unknown
c8fe0f58-4d8f-471a-86b6-9e8ad1f12a44	pDQM005	302	unknown
22779c02-7386-4a7a-9afb-7e950a0be0a7	pDQM005	301	unknown
51e4e205-42ac-414c-bfb1-be100bbe6890	pDQM005	302	unknown
\.


--
-- Data for Name: fish_transgenes; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.fish_transgenes (fish_id, transgene_code) FROM stdin;
4db5d7f1-00e5-4874-8d7f-b494f279247b	elavl3_gcamp6s
b32b4684-a282-468d-b04d-c86887e41cd7	elavl3_gcamp6s
6ae2c96b-2a23-4f2f-9176-69e6eb114a33	elavl3_gcamp6s
192507f2-277d-4c9e-b7ca-45fe3bfe04f8	myo6b_chr2
5cc4540b-c8a7-46d6-a477-5ba21b34a030	pDQM005
cc8671ac-57d6-4d92-a830-305cff5ddd44	pDQM005
6fdf5241-a670-47b6-8eb4-c414bd0431d0	pDQM005
c8fe0f58-4d8f-471a-86b6-9e8ad1f12a44	pDQM005
22779c02-7386-4a7a-9afb-7e950a0be0a7	pDQM005
51e4e205-42ac-414c-bfb1-be100bbe6890	pDQM005
\.


--
-- Data for Name: fish_treatments; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.fish_treatments (id_uuid, applied_at, notes, created_at, created_by, updated_at, updated_by, fish_id, treatment_id) FROM stdin;
\.


--
-- Data for Name: fish_year_counters; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.fish_year_counters (year, n) FROM stdin;
2025	52
\.


--
-- Data for Name: genotypes; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.genotypes (id_uuid, transgene_id_uuid, zygosity, notes, created_at, created_by, fish_id) FROM stdin;
\.


--
-- Data for Name: injected_plasmid_treatments; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.injected_plasmid_treatments (concentration_ng_per_ul, volume_nl, injection_stage, vehicle, enzyme, id, treatment_id, plasmid_id, plasmid_code) FROM stdin;
\.


--
-- Data for Name: injected_rna_treatments; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.injected_rna_treatments (concentration_ng_per_ul, volume_nl, injection_stage, vehicle, id, treatment_id, rna_id, rna_code) FROM stdin;
\.


--
-- Data for Name: plasmid_counters; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.plasmid_counters (n) FROM stdin;
\.


--
-- Data for Name: plasmids; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.plasmids (id_uuid, plasmid_code, name, created_at, created_by, description) FROM stdin;
c5795f8e-7566-4793-882f-876035e62c91	ptol2-elavl3_gcamp6s	pan-neuronal GCaMP6s	2025-09-23 04:45:06.919+00	\N	Tol2; elavl3 promoter; inject at 1-cell
7f0c3839-c190-48c6-b1ad-b2b47b673129	ptol2-myo6b_chr2	myo6b chr2 reporter	2025-09-23 04:45:06.919+00	\N	Tol2; myo6b promoter; inject at 1-cell
\.


--
-- Data for Name: rna_counters; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.rna_counters (n) FROM stdin;
\.


--
-- Data for Name: rnas; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.rnas (id_uuid, rna_code, name, created_at, created_by, description) FROM stdin;
d3af8033-efd6-4b50-9a06-2b71ec2984de	mrna-lin28a-gfp	lin28a-GFP mRNA	2025-09-23 05:44:54.270702+00	\N	in vitro–transcribed mRNA
98367edc-3305-48d8-aa89-ffc0e96a1be5	h2b-mneo	h2b-mNeonGreen	2025-09-23 05:53:54.035547+00	\N	Histone H2B fused to mNeon
a8554476-1fa5-46e4-9751-b0f4c0e3b4c5	gap43-sfgfp	gap43-sfGFP	2025-09-23 05:53:54.035547+00	\N	membrane targeted sfGFP
e500a0ed-eb12-4734-992a-465669362924	gfp-sense	GFP sense RNA	2025-09-23 07:24:16.826083+00	\N	demo record for seed kit
\.


--
-- Data for Name: seed_fish_tmp; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.seed_fish_tmp (fish_name, nickname, date_birth, line_building_stage, strain, has_transgene, has_mutation, has_treatment_injected_plasmid, has_treatment_injected_rna, has_treatment_dye, n_new_tanks, seed_batch_id) FROM stdin;
\.


--
-- Data for Name: seed_transgenes_tmp; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.seed_transgenes_tmp (fish_name, transgene_name, allele_name, zygosity, new_allele_note, seed_batch_id) FROM stdin;
\.


--
-- Data for Name: seed_treatment_dye_tmp; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.seed_treatment_dye_tmp (fish_name, dye_name, operator, performed_at, description, notes, seed_batch_id) FROM stdin;
\.


--
-- Data for Name: seed_treatment_injected_plasmid_tmp; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.seed_treatment_injected_plasmid_tmp (fish_name, plasmid_name, operator, performed_at, batch_label, injection_mix, injection_notes, enzyme, seed_batch_id) FROM stdin;
\.


--
-- Data for Name: seed_treatment_injected_rna_tmp; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.seed_treatment_injected_rna_tmp (fish_name, rna_name, operator, performed_at, description, notes, seed_batch_id) FROM stdin;
\.


--
-- Data for Name: staging_links_dye; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.staging_links_dye (fish_code, dye_code, treatment_batch_id, performed_at, operator, amount, units, route, notes) FROM stdin;
\.


--
-- Data for Name: staging_links_dye_by_name; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.staging_links_dye_by_name (fish_name, dye_name, treatment_batch_id, performed_at, operator, amount, units, route, notes) FROM stdin;
\.


--
-- Data for Name: staging_links_injected_plasmid; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.staging_links_injected_plasmid (fish_code, plasmid_code, treatment_batch_id, performed_at, operator, concentration_ng_per_ul, volume_nl, injection_stage, vehicle, notes) FROM stdin;
\.


--
-- Data for Name: staging_links_injected_plasmid_by_name; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.staging_links_injected_plasmid_by_name (fish_name, plasmid_name, treatment_batch_id, performed_at, operator, concentration_ng_per_ul, volume_nl, injection_stage, vehicle, notes, enzyme) FROM stdin;
\.


--
-- Data for Name: staging_links_injected_rna; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.staging_links_injected_rna (fish_code, rna_code, treatment_batch_id, performed_at, operator, concentration_ng_per_ul, volume_nl, injection_stage, vehicle, notes) FROM stdin;
\.


--
-- Data for Name: staging_links_injected_rna_by_name; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.staging_links_injected_rna_by_name (fish_name, rna_name, treatment_batch_id, performed_at, operator, concentration_ng_per_ul, volume_nl, injection_stage, vehicle, notes) FROM stdin;
\.


--
-- Data for Name: stg_dye; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.stg_dye (fish_name, dye_name, operator, performed_at, notes, source) FROM stdin;
\.


--
-- Data for Name: stg_inj_plasmid; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.stg_inj_plasmid (fish_name, plasmid_name, operator, performed_at, batch_label, injection_mix, injection_notes, enzyme) FROM stdin;
\.


--
-- Data for Name: stg_inj_rna; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.stg_inj_rna (fish_name, rna_name, operator, performed_at, notes, source) FROM stdin;
\.


--
-- Data for Name: tank_assignments; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.tank_assignments (fish_id, tank_label, status) FROM stdin;
4db5d7f1-00e5-4874-8d7f-b494f279247b	TANK-25002	inactive
b32b4684-a282-468d-b04d-c86887e41cd7	TANK-25003	inactive
6ae2c96b-2a23-4f2f-9176-69e6eb114a33	TANK-25004	inactive
192507f2-277d-4c9e-b7ca-45fe3bfe04f8	TANK-25005	inactive
5cc4540b-c8a7-46d6-a477-5ba21b34a030	TANK-25006	inactive
cc8671ac-57d6-4d92-a830-305cff5ddd44	TANK-25007	inactive
6fdf5241-a670-47b6-8eb4-c414bd0431d0	TANK-25008	inactive
c8fe0f58-4d8f-471a-86b6-9e8ad1f12a44	TANK-25009	inactive
22779c02-7386-4a7a-9afb-7e950a0be0a7	TANK-2500A	inactive
51e4e205-42ac-414c-bfb1-be100bbe6890	TANK-2500B	inactive
\.


--
-- Data for Name: tank_code_counters; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.tank_code_counters (prefix, year_small, next_seq) FROM stdin;
NURSERY-	25	2
TANK-	25	12
\.


--
-- Data for Name: tanks; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.tanks (id, tank_code, created_at, id_uuid) FROM stdin;
\.


--
-- Data for Name: transgene_alleles; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.transgene_alleles (transgene_base_code, allele_number, description) FROM stdin;
pDQM005	301	\N
pDQM005	302	\N
elavl3_gcamp6s	a201	founder allele from epsilon
elavl3_gcamp6s	a202	independent integration event
myo6b_chr2	b201	founder allele from theta lineage
\.


--
-- Data for Name: transgenes; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.transgenes (id_uuid, allele_num, transgene_base_code, created_at, created_by, name, description, code) FROM stdin;
8ab8438d-b4c3-4725-96d4-88d5fbcf3993	\N	pDQM005	2025-09-24 11:30:58.310806+00	\N	ef1a:2xLynk:mSG		pDQM005
c2dcfbf6-7481-4f0d-b16d-ba3a412e714c	\N	elavl3_gcamp6s	2025-09-24 10:26:17.574247+00	\N	pan-neuronal GCaMP6s	Tol2 backbone; elavl3 promoter; calcium reporter	elavl3_gcamp6s
52094f36-af9f-40ab-b322-99274c362de5	\N	myo6b_chr2	2025-09-24 10:26:17.574247+00	\N	chr2 hair-cell reporter	Tol2 backbone; myo6b promoter; chromoprotein #2	myo6b_chr2
\.


--
-- Data for Name: treatments; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.treatments (id_uuid, treatment_type, batch_id, performed_at, operator, notes, created_at, created_by, batch_label, id, treatment_code, fish_id, date, method, plasmid_code, outcome, code) FROM stdin;
\.


--
-- Data for Name: fish_csv; Type: TABLE DATA; Schema: raw; Owner: postgres
--

COPY raw.fish_csv (fish_name, mother, date_of_birth, status, strain, alive, breeding_pairing, fish_code, archived, died, who) FROM stdin;
\.


--
-- Data for Name: fish_links_has_transgenes_csv; Type: TABLE DATA; Schema: raw; Owner: postgres
--

COPY raw.fish_links_has_transgenes_csv (fish_name, transgene_name, allele_name, zygosity, new_allele_note) FROM stdin;
\.


--
-- Data for Name: fish_links_has_treatment_dye_csv; Type: TABLE DATA; Schema: raw; Owner: postgres
--

COPY raw.fish_links_has_treatment_dye_csv (fish_name, dye_name, operator, performed_at, description, notes) FROM stdin;
\.


--
-- Data for Name: fish_links_has_treatment_injected_plasmid_csv; Type: TABLE DATA; Schema: raw; Owner: postgres
--

COPY raw.fish_links_has_treatment_injected_plasmid_csv (fish_name, plasmid_name, operator, performed_at, batch_label, injection_mix, injection_notes, enzyme) FROM stdin;
\.


--
-- Data for Name: fish_links_has_treatment_injected_rna_csv; Type: TABLE DATA; Schema: raw; Owner: postgres
--

COPY raw.fish_links_has_treatment_injected_rna_csv (fish_name, rna_name, operator, performed_at, description, notes) FROM stdin;
\.


--
-- Data for Name: messages_2025_09_21; Type: TABLE DATA; Schema: realtime; Owner: postgres
--

COPY realtime.messages_2025_09_21 (topic, extension, payload, event, private, updated_at, inserted_at, id) FROM stdin;
\.


--
-- Data for Name: messages_2025_09_22; Type: TABLE DATA; Schema: realtime; Owner: postgres
--

COPY realtime.messages_2025_09_22 (topic, extension, payload, event, private, updated_at, inserted_at, id) FROM stdin;
\.


--
-- Data for Name: messages_2025_09_23; Type: TABLE DATA; Schema: realtime; Owner: postgres
--

COPY realtime.messages_2025_09_23 (topic, extension, payload, event, private, updated_at, inserted_at, id) FROM stdin;
\.


--
-- Data for Name: messages_2025_09_24; Type: TABLE DATA; Schema: realtime; Owner: postgres
--

COPY realtime.messages_2025_09_24 (topic, extension, payload, event, private, updated_at, inserted_at, id) FROM stdin;
\.


--
-- Data for Name: messages_2025_09_25; Type: TABLE DATA; Schema: realtime; Owner: postgres
--

COPY realtime.messages_2025_09_25 (topic, extension, payload, event, private, updated_at, inserted_at, id) FROM stdin;
\.


--
-- Data for Name: schema_migrations; Type: TABLE DATA; Schema: realtime; Owner: supabase_admin
--

COPY realtime.schema_migrations (version, inserted_at) FROM stdin;
20211116024918	2025-09-22 23:22:35
20211116045059	2025-09-22 23:22:35
20211116050929	2025-09-22 23:22:35
20211116051442	2025-09-22 23:22:35
20211116212300	2025-09-22 23:22:35
20211116213355	2025-09-22 23:22:35
20211116213934	2025-09-22 23:22:35
20211116214523	2025-09-22 23:22:35
20211122062447	2025-09-22 23:22:35
20211124070109	2025-09-22 23:22:35
20211202204204	2025-09-22 23:22:35
20211202204605	2025-09-22 23:22:35
20211210212804	2025-09-22 23:22:35
20211228014915	2025-09-22 23:22:35
20220107221237	2025-09-22 23:22:35
20220228202821	2025-09-22 23:22:35
20220312004840	2025-09-22 23:22:35
20220603231003	2025-09-22 23:22:35
20220603232444	2025-09-22 23:22:35
20220615214548	2025-09-22 23:22:35
20220712093339	2025-09-22 23:22:35
20220908172859	2025-09-22 23:22:35
20220916233421	2025-09-22 23:22:35
20230119133233	2025-09-22 23:22:35
20230128025114	2025-09-22 23:22:35
20230128025212	2025-09-22 23:22:35
20230227211149	2025-09-22 23:22:35
20230228184745	2025-09-22 23:22:35
20230308225145	2025-09-22 23:22:35
20230328144023	2025-09-22 23:22:35
20231018144023	2025-09-22 23:22:35
20231204144023	2025-09-22 23:22:35
20231204144024	2025-09-22 23:22:35
20231204144025	2025-09-22 23:22:35
20240108234812	2025-09-22 23:22:35
20240109165339	2025-09-22 23:22:35
20240227174441	2025-09-22 23:22:35
20240311171622	2025-09-22 23:22:35
20240321100241	2025-09-22 23:22:35
20240401105812	2025-09-22 23:22:35
20240418121054	2025-09-22 23:22:35
20240523004032	2025-09-22 23:22:35
20240618124746	2025-09-22 23:22:35
20240801235015	2025-09-22 23:22:35
20240805133720	2025-09-22 23:22:35
20240827160934	2025-09-22 23:22:35
20240919163303	2025-09-22 23:22:35
20240919163305	2025-09-22 23:22:35
20241019105805	2025-09-22 23:22:35
20241030150047	2025-09-22 23:22:35
20241108114728	2025-09-22 23:22:35
20241121104152	2025-09-22 23:22:35
20241130184212	2025-09-22 23:22:35
20241220035512	2025-09-22 23:22:35
20241220123912	2025-09-22 23:22:35
20241224161212	2025-09-22 23:22:35
20250107150512	2025-09-22 23:22:35
20250110162412	2025-09-22 23:22:35
20250123174212	2025-09-22 23:22:35
20250128220012	2025-09-22 23:22:35
20250506224012	2025-09-22 23:22:35
20250523164012	2025-09-22 23:22:35
20250714121412	2025-09-22 23:22:35
\.


--
-- Data for Name: subscription; Type: TABLE DATA; Schema: realtime; Owner: supabase_admin
--

COPY realtime.subscription (id, subscription_id, entity, filters, claims, created_at) FROM stdin;
\.


--
-- Data for Name: _dye_csv; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging._dye_csv (fish_name, treatment_date, material_code, treatment_type, operator, notes) FROM stdin;
fish-201	2025-08-12	dii	soak	dk	membrane dye
fish-204	2025-07-29	fluorogold	injection	dk	retrograde label
\.


--
-- Data for Name: _fish_csv; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging._fish_csv (name) FROM stdin;
\.


--
-- Data for Name: _fish_names; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging._fish_names (name) FROM stdin;
\.


--
-- Data for Name: _fish_raw; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging._fish_raw (col1, col2, col3, col4, col5, col6) FROM stdin;
\.


--
-- Data for Name: _plasmid_csv; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging._plasmid_csv (fish_name, treatment_date, material_code, treatment_type, operator, notes) FROM stdin;
fish-201	2025-08-11	pTol2-elavl3_GCaMP6s	one-cell injection	dk	good fluorescence at 5 dpf
fish-204	2025-07-28	pTol2-myo6b_chr2	one-cell injection	dk	robust otic expression
fish-202	2025-08-12	rna:gfp-sense	one-cell injection	dk	strong heart signal
fish-203	2025-08-13	dye:dii	retro-orbital label	dk	optic tract labeled
\.


--
-- Data for Name: _rna_csv; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging._rna_csv (fish_name, treatment_date, material_code, treatment_type, operator, notes) FROM stdin;
fish-201	2025-08-12	ptol2-elavl3-gcamp6s-rna	one-cell injection	dk	co-expression w/ plasmid
fish-204	2025-07-29	ptol2-myo6b_chr2-rna	one-cell injection	dk	ear labeling
\.


--
-- Data for Name: core_dye_treatments_csv; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.core_dye_treatments_csv (fish_code, treatment_date, dye_code, method, operator, notes) FROM stdin;
fish-201	2025-08-12	dii	soak	dk	membrane dye
fish-204	2025-07-29	fluorogold	injection	dk	retrograde label
\.


--
-- Data for Name: core_dyes_csv; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.core_dyes_csv (dye_code, name, description) FROM stdin;
diI	DiI	lipophilic carbocyanine dye
dexa	Dextran-Alexa488	fixable dextran dye
\.


--
-- Data for Name: core_fish_csv; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.core_fish_csv (fish_code, name, date_of_birth, line_building_stage, strain, description) FROM stdin;
\.


--
-- Data for Name: core_fish_transgene_alleles_csv; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.core_fish_transgene_alleles_csv (fish_code, transgene_base_code, allele_number, zygosity) FROM stdin;
fish-201	elavl3_gcamp6s	a201	unknown
fish-202	elavl3_gcamp6s	a202	het
fish-203	elavl3_gcamp6s	a201	het
fish-204	myo6b_chr2	b201	unknown
\.


--
-- Data for Name: core_plasmids_csv; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.core_plasmids_csv (plasmid_code, name, description) FROM stdin;
\.


--
-- Data for Name: core_rna_treatments_csv; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.core_rna_treatments_csv (fish_code, treatment_date, rna_code, method, operator, notes) FROM stdin;
fish-201	2025-08-12	ptol2-elavl3-gcamp6s-rna	one-cell injection	dk	co-expression w/ plasmid
fish-204	2025-07-29	ptol2-myo6b_chr2-rna	one-cell injection	dk	ear labeling
\.


--
-- Data for Name: core_rnas_csv; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.core_rnas_csv (rna_code, name, description) FROM stdin;
h2b-mneo	h2b-mNeonGreen	Histone H2B fused to mNeon
gap43-sfGFP	gap43-sfGFP	membrane targeted sfGFP
\.


--
-- Data for Name: core_transgene_alleles_csv; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.core_transgene_alleles_csv (transgene_base_code, allele_number, description) FROM stdin;
\.


--
-- Data for Name: core_transgenes_csv; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.core_transgenes_csv (transgene_base_code, name, description) FROM stdin;
\.


--
-- Data for Name: core_treatments_csv; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.core_treatments_csv (fish_code, treatment_date, material, plasmid_code, method, operator, notes) FROM stdin;
fish-201	2025-08-11	\N	pTol2-elavl3_GCaMP6s	one-cell injection	dk	good fluorescence at 5 dpf
fish-204	2025-07-28	\N	pTol2-myo6b_chr2	one-cell injection	dk	robust otic expression
fish-202	2025-08-12	\N	rna:gfp-sense	one-cell injection	dk	strong heart signal
fish-203	2025-08-13	\N	dye:dii	retro-orbital label	dk	optic tract labeled
\.


--
-- Data for Name: core_treatments_unified_csv; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.core_treatments_unified_csv (fish_code, treatment_date, treatment_type, material_code, method, operator, notes) FROM stdin;
fish-201	2025-08-11	injected_plasmid	ptol2-elavl3_gcamp6s	one-cell injection	dk	good fluorescence at 5 dpf
fish-204	2025-07-28	injected_plasmid	ptol2-myo6b_chr2	one-cell injection	dk	robust otic expression
fish-201	2025-08-12	injected_rna	ptol2-elavl3-gcamp6s-rna	one-cell injection	dk	co-expression w/ plasmid
fish-204	2025-07-29	dye_labeling	dii	soak	dk	membrane dye
\.


--
-- Data for Name: fish_transgene_alleles; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.fish_transgene_alleles (fish_name, transgene_base_code, allele_number, zygosity) FROM stdin;
\.


--
-- Data for Name: links_fish_transgene_alleles; Type: TABLE DATA; Schema: staging; Owner: postgres
--

COPY staging.links_fish_transgene_alleles (fish_name, transgene_base_code, allele_number, zygosity) FROM stdin;
\.


--
-- Data for Name: buckets; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.buckets (id, name, owner, created_at, updated_at, public, avif_autodetection, file_size_limit, allowed_mime_types, owner_id) FROM stdin;
\.


--
-- Data for Name: migrations; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.migrations (id, name, hash, executed_at) FROM stdin;
0	create-migrations-table	e18db593bcde2aca2a408c4d1100f6abba2195df	2025-09-22 23:22:45.180768
1	initialmigration	6ab16121fbaa08bbd11b712d05f358f9b555d777	2025-09-22 23:22:45.183445
2	storage-schema	5c7968fd083fcea04050c1b7f6253c9771b99011	2025-09-22 23:22:45.185007
3	pathtoken-column	2cb1b0004b817b29d5b0a971af16bafeede4b70d	2025-09-22 23:22:45.190699
4	add-migrations-rls	427c5b63fe1c5937495d9c635c263ee7a5905058	2025-09-22 23:22:45.196402
5	add-size-functions	79e081a1455b63666c1294a440f8ad4b1e6a7f84	2025-09-22 23:22:45.198387
6	change-column-name-in-get-size	f93f62afdf6613ee5e7e815b30d02dc990201044	2025-09-22 23:22:45.202197
7	add-rls-to-buckets	e7e7f86adbc51049f341dfe8d30256c1abca17aa	2025-09-22 23:22:45.20467
8	add-public-to-buckets	fd670db39ed65f9d08b01db09d6202503ca2bab3	2025-09-22 23:22:45.207046
9	fix-search-function	3a0af29f42e35a4d101c259ed955b67e1bee6825	2025-09-22 23:22:45.209503
10	search-files-search-function	68dc14822daad0ffac3746a502234f486182ef6e	2025-09-22 23:22:45.212436
11	add-trigger-to-auto-update-updated_at-column	7425bdb14366d1739fa8a18c83100636d74dcaa2	2025-09-22 23:22:45.214987
12	add-automatic-avif-detection-flag	8e92e1266eb29518b6a4c5313ab8f29dd0d08df9	2025-09-22 23:22:45.220285
13	add-bucket-custom-limits	cce962054138135cd9a8c4bcd531598684b25e7d	2025-09-22 23:22:45.222743
14	use-bytes-for-max-size	941c41b346f9802b411f06f30e972ad4744dad27	2025-09-22 23:22:45.224675
15	add-can-insert-object-function	934146bc38ead475f4ef4b555c524ee5d66799e5	2025-09-22 23:22:45.232122
16	add-version	76debf38d3fd07dcfc747ca49096457d95b1221b	2025-09-22 23:22:45.234398
17	drop-owner-foreign-key	f1cbb288f1b7a4c1eb8c38504b80ae2a0153d101	2025-09-22 23:22:45.238115
18	add_owner_id_column_deprecate_owner	e7a511b379110b08e2f214be852c35414749fe66	2025-09-22 23:22:45.239549
19	alter-default-value-objects-id	02e5e22a78626187e00d173dc45f58fa66a4f043	2025-09-22 23:22:45.241344
20	list-objects-with-delimiter	cd694ae708e51ba82bf012bba00caf4f3b6393b7	2025-09-22 23:22:45.24324
21	s3-multipart-uploads	8c804d4a566c40cd1e4cc5b3725a664a9303657f	2025-09-22 23:22:45.245686
22	s3-multipart-uploads-big-ints	9737dc258d2397953c9953d9b86920b8be0cdb73	2025-09-22 23:22:45.250894
23	optimize-search-function	9d7e604cddc4b56a5422dc68c9313f4a1b6f132c	2025-09-22 23:22:45.25554
24	operation-function	8312e37c2bf9e76bbe841aa5fda889206d2bf8aa	2025-09-22 23:22:45.257389
25	custom-metadata	d974c6057c3db1c1f847afa0e291e6165693b990	2025-09-22 23:22:45.25915
\.


--
-- Data for Name: objects; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.objects (id, bucket_id, name, owner, created_at, updated_at, last_accessed_at, metadata, version, owner_id, user_metadata) FROM stdin;
\.


--
-- Data for Name: s3_multipart_uploads; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.s3_multipart_uploads (id, in_progress_size, upload_signature, bucket_id, key, version, owner_id, created_at, user_metadata) FROM stdin;
\.


--
-- Data for Name: s3_multipart_uploads_parts; Type: TABLE DATA; Schema: storage; Owner: supabase_storage_admin
--

COPY storage.s3_multipart_uploads_parts (id, upload_id, size, part_number, bucket_id, key, etag, owner_id, version, created_at) FROM stdin;
\.


--
-- Data for Name: hooks; Type: TABLE DATA; Schema: supabase_functions; Owner: supabase_functions_admin
--

COPY supabase_functions.hooks (id, hook_table_id, hook_name, created_at, request_id) FROM stdin;
\.


--
-- Data for Name: migrations; Type: TABLE DATA; Schema: supabase_functions; Owner: supabase_functions_admin
--

COPY supabase_functions.migrations (version, inserted_at) FROM stdin;
initial	2025-09-22 23:22:32.779748+00
20210809183423_update_grants	2025-09-22 23:22:32.779748+00
\.


--
-- Data for Name: schema_migrations; Type: TABLE DATA; Schema: supabase_migrations; Owner: postgres
--

COPY supabase_migrations.schema_migrations (version, statements, name) FROM stdin;
00000000000000	{"-- Ensure schema + sequences exist before any SQL-language functions are created\nSET search_path = public, pg_catalog","CREATE SCHEMA IF NOT EXISTS public","-- Sequences referenced by functions/views\nCREATE SEQUENCE IF NOT EXISTS public.tank_counters","CREATE SEQUENCE IF NOT EXISTS public.seq_tank_code","-- auto-generated: sequences referenced by baseline\nCREATE SEQUENCE IF NOT EXISTS public.seq_tank_code","CREATE SEQUENCE IF NOT EXISTS public.tank_counters"}	prelude
00000000000001	{"CREATE SCHEMA IF NOT EXISTS public","CREATE SCHEMA IF NOT EXISTS \\"public\\"","ALTER SCHEMA \\"public\\" OWNER TO \\"postgres\\"","COMMENT ON SCHEMA \\"public\\" IS 'standard public schema'","CREATE TYPE \\"public\\".\\"treatment_type_enum\\" AS ENUM (\n    'injected_plasmid',\n    'injected_rna',\n    'dye'\n)","ALTER TYPE \\"public\\".\\"treatment_type_enum\\" OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"_next_tank_code\\"() RETURNS \\"text\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\ndeclare y int := extract(year from now())::int;\n        n int;\nbegin\n  select nextval('public.seq_tank_code')::int into n;\n  return format('TANK-%s-%04s', public._tank_code_year(y), n);\nend;\n$$","ALTER FUNCTION \\"public\\".\\"_next_tank_code\\"() OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"_tank_code_year\\"(\\"y\\" integer) RETURNS \\"text\\"\n    LANGUAGE \\"sql\\" IMMUTABLE\n    AS $$ select lpad((y % 100)::text, 2, '0') $$","ALTER FUNCTION \\"public\\".\\"_tank_code_year\\"(\\"y\\" integer) OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"assert_treatment_type\\"(\\"expected\\" \\"text\\", \\"tid\\" \\"uuid\\") RETURNS \\"void\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\ndeclare\n  actual text;\n  exp text := lower(expected);\n  ok text[];\nbegin\n  select lower(treatment_type::text) into actual\n  from public.treatments\n  where id_uuid = tid;\n\n  if actual is null then\n    raise exception 'Treatment % not found', tid;\n  end if;\n\n  -- Accept common aliases\n  if exp in ('plasmid_injection','injected_plasmid') then\n    ok := array['plasmid_injection','injected_plasmid'];\n  elsif exp in ('rna_injection','injected_rna') then\n    ok := array['rna_injection','injected_rna'];\n  elsif exp in ('dye_injection','injected_dye') then\n    ok := array['dye_injection','injected_dye'];\n  else\n    ok := array[exp];\n  end if;\n\n  if actual <> all(ok) and actual <> any(ok) = false then\n    -- (defensive, but the previous line is sufficient in PG 12+)\n    null;\n  end if;\n\n  if not (actual = any(ok)) then\n    raise exception 'Treatment % must have type % (found %)', tid, exp, actual;\n  end if;\nend;\n$$","ALTER FUNCTION \\"public\\".\\"assert_treatment_type\\"(\\"expected\\" \\"text\\", \\"tid\\" \\"uuid\\") OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"assert_unique_batch_key\\"(\\"p_treatment_id\\" \\"uuid\\") RETURNS \\"void\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\ndeclare\n  v_type text;\n  v_performed_at timestamptz;\n  v_operator text;\nbegin\n  select lower(treatment_type::text), performed_at, operator\n    into v_type, v_performed_at, v_operator\n  from public.treatments\n  where id_uuid = p_treatment_id;\n\n  if v_type is null then\n    perform public.pg_raise('batch_incomplete', 'treatment not found');\n    return;\n  end if;\n\n  -- Require date & operator regardless of exact enum spelling\n  if v_performed_at is null or coalesce(nullif(btrim(v_operator), ''), '') = '' then\n    perform public.pg_raise('batch_incomplete', 'treatment is missing type/date/operator');\n    return;\n  end if;\n\n  return;\nend;\n$$","ALTER FUNCTION \\"public\\".\\"assert_unique_batch_key\\"(\\"p_treatment_id\\" \\"uuid\\") OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"detail_type_guard_v2\\"() RETURNS \\"trigger\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\nDECLARE\n  ttype text;\n  n int := 0;\nBEGIN\n  -- Verify treatment type matches the detail table\n  SELECT treatment_type INTO ttype\n  FROM public.treatments\n  WHERE id = NEW.treatment_id;\n\n  IF ttype IS NULL THEN\n    RAISE EXCEPTION 'No treatments.id = % found for detail row', NEW.treatment_id;\n  END IF;\n\n  IF TG_TABLE_NAME = 'injected_plasmid_treatments' AND ttype <> 'injected_plasmid' THEN\n    RAISE EXCEPTION 'treatment % has type %, expected injected_plasmid', NEW.treatment_id, ttype;\n  ELSIF TG_TABLE_NAME = 'injected_rna_treatments' AND ttype <> 'injected_rna' THEN\n    RAISE EXCEPTION 'treatment % has type %, expected injected_rna', NEW.treatment_id, ttype;\n  ELSIF TG_TABLE_NAME = 'dye_treatments' AND ttype <> 'dye' THEN\n    RAISE EXCEPTION 'treatment % has type %, expected dye', NEW.treatment_id, ttype;\n  END IF;\n\n  -- Count existing detail rows across all three tables, excluding self on UPDATE\n  n :=\n    (SELECT COUNT(*) FROM public.injected_plasmid_treatments\n      WHERE treatment_id = NEW.treatment_id\n        AND NOT (TG_TABLE_NAME='injected_plasmid_treatments' AND TG_OP='UPDATE' AND id = NEW.id))\n  + (SELECT COUNT(*) FROM public.injected_rna_treatments\n      WHERE treatment_id = NEW.treatment_id\n        AND NOT (TG_TABLE_NAME='injected_rna_treatments' AND TG_OP='UPDATE' AND id = NEW.id))\n  + (SELECT COUNT(*) FROM public.dye_treatments\n      WHERE treatment_id = NEW.treatment_id\n        AND NOT (TG_TABLE_NAME='dye_treatments' AND TG_OP='UPDATE' AND id = NEW.id));\n\n  IF TG_OP = 'INSERT' AND n > 0 THEN\n    RAISE EXCEPTION 'treatment % already has a detail row in another table', NEW.treatment_id;\n  ELSIF TG_OP = 'UPDATE' AND n > 1 THEN\n    RAISE EXCEPTION 'treatment % already has a detail row in another table', NEW.treatment_id;\n  END IF;\n\n  RETURN NEW;\nEND;\n$$","ALTER FUNCTION \\"public\\".\\"detail_type_guard_v2\\"() OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"dye_code_autofill\\"() RETURNS \\"trigger\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\nbegin if new.dye_code is null or btrim(new.dye_code)='' then new.dye_code:=public.gen_dye_code(); end if; return new; end $$","ALTER FUNCTION \\"public\\".\\"dye_code_autofill\\"() OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"fish_code_autofill\\"() RETURNS \\"trigger\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\nbegin if new.fish_code is null or btrim(new.fish_code)='' then new.fish_code := public.gen_fish_code(coalesce(new.created_at, now())); end if; return new; end $$","ALTER FUNCTION \\"public\\".\\"fish_code_autofill\\"() OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"gen_dye_code\\"() RETURNS \\"text\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\ndeclare k int;\nbegin update public.dye_counters set n=n+1 returning n into k; return format('DYE-%04s', k); end $$","ALTER FUNCTION \\"public\\".\\"gen_dye_code\\"() OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"gen_fish_code\\"(\\"p_ts\\" timestamp with time zone DEFAULT \\"now\\"()) RETURNS \\"text\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\ndeclare y int := extract(year from p_ts);\ndeclare k int;\nbegin insert into public.fish_year_counters(year,n) values (y,0) on conflict (year) do nothing;\nupdate public.fish_year_counters set n=n+1 where year=y returning n into k;\nreturn format('FSH-%s-%04s', y, k);\nend $$","ALTER FUNCTION \\"public\\".\\"gen_fish_code\\"(\\"p_ts\\" timestamp with time zone) OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"gen_plasmid_code\\"() RETURNS \\"text\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\ndeclare k int;\nbegin update public.plasmid_counters set n=n+1 returning n into k;\nreturn format('PLM-%04s', k);\nend $$","ALTER FUNCTION \\"public\\".\\"gen_plasmid_code\\"() OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"gen_rna_code\\"() RETURNS \\"text\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\ndeclare k int;\nbegin update public.rna_counters set n=n+1 returning n into k; return format('RNA-%04s', k); end $$","ALTER FUNCTION \\"public\\".\\"gen_rna_code\\"() OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"gen_tank_code\\"() RETURNS \\"text\\"\n    LANGUAGE \\"sql\\"\n    AS $$\n          select 'TANK-' || to_char(now(),'YYYY') || '-' ||\n                 lpad(nextval('public.tank_counters')::text, 4, '0');\n        $$","ALTER FUNCTION \\"public\\".\\"gen_tank_code\\"() OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"pg_raise\\"(\\"name\\" \\"text\\", \\"msg\\" \\"text\\") RETURNS \\"void\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\nbegin\n  raise exception using errcode = 'P0001', message = msg, constraint = name;\nend $$","ALTER FUNCTION \\"public\\".\\"pg_raise\\"(\\"name\\" \\"text\\", \\"msg\\" \\"text\\") OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"pg_raise\\"(\\"name\\" \\"text\\", \\"msg\\" \\"text\\", \\"tid\\" \\"uuid\\") RETURNS \\"void\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\nbegin\n  raise exception using errcode = 'P0001', message = msg || ' ('||tid||')', constraint = name;\nend $$","ALTER FUNCTION \\"public\\".\\"pg_raise\\"(\\"name\\" \\"text\\", \\"msg\\" \\"text\\", \\"tid\\" \\"uuid\\") OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"plasmid_code_autofill\\"() RETURNS \\"trigger\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\nbegin if new.plasmid_code is null or btrim(new.plasmid_code)='' then new.plasmid_code := public.gen_plasmid_code(); end if; return new; end $$","ALTER FUNCTION \\"public\\".\\"plasmid_code_autofill\\"() OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"rna_code_autofill\\"() RETURNS \\"trigger\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\nbegin if new.rna_code is null or btrim(new.rna_code)='' then new.rna_code:=public.gen_rna_code(); end if; return new; end $$","ALTER FUNCTION \\"public\\".\\"rna_code_autofill\\"() OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"set_updated_at\\"() RETURNS \\"trigger\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\nbegin new.updated_at=now(); return new; end $$","ALTER FUNCTION \\"public\\".\\"set_updated_at\\"() OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"treatment_batch_guard_v2\\"() RETURNS \\"trigger\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\nDECLARE\n  tid_uuid uuid;\nBEGIN\n  IF TG_TABLE_NAME = 'treatments' THEN\n    tid_uuid := NEW.id_uuid;\n  ELSE\n    -- detail tables now have treatment_id (→ treatments.id); look up its id_uuid\n    SELECT id_uuid INTO tid_uuid\n    FROM public.treatments\n    WHERE id = NEW.treatment_id;\n  END IF;\n\n  PERFORM public.assert_unique_batch_key(tid_uuid);\n  RETURN NEW;\nEND;\n$$","ALTER FUNCTION \\"public\\".\\"treatment_batch_guard_v2\\"() OWNER TO \\"postgres\\"","CREATE OR REPLACE FUNCTION \\"public\\".\\"trg_set_tank_code\\"() RETURNS \\"trigger\\"\n    LANGUAGE \\"plpgsql\\"\n    AS $$\nbegin\n  if new.tank_code is null or btrim(new.tank_code) = '' then\n    new.tank_code := public._next_tank_code();\n  end if;\n  return new;\nend;\n$$","ALTER FUNCTION \\"public\\".\\"trg_set_tank_code\\"() OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"_staging_fish_load\\" (\n    \\"fish_name\\" \\"text\\" NOT NULL,\n    \\"date_birth\\" \\"date\\",\n    \\"n_new_tanks\\" integer DEFAULT 0 NOT NULL\n)","ALTER TABLE \\"public\\".\\"_staging_fish_load\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"dye_counters\\" (\n    \\"n\\" integer DEFAULT 0 NOT NULL\n)","ALTER TABLE \\"public\\".\\"dye_counters\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"dye_treatments\\" (\n    \\"amount\\" numeric,\n    \\"units\\" \\"text\\",\n    \\"route\\" \\"text\\",\n    \\"id\\" \\"uuid\\" DEFAULT \\"gen_random_uuid\\"(),\n    \\"treatment_id\\" \\"uuid\\" NOT NULL,\n    \\"dye_id\\" \\"uuid\\" NOT NULL\n)","ALTER TABLE \\"public\\".\\"dye_treatments\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"dyes\\" (\n    \\"id_uuid\\" \\"uuid\\" DEFAULT \\"gen_random_uuid\\"() NOT NULL,\n    \\"dye_code\\" \\"text\\",\n    \\"name\\" \\"text\\",\n    \\"created_at\\" timestamp with time zone DEFAULT \\"now\\"() NOT NULL,\n    \\"created_by\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"dyes\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"fish\\" (\n    \\"id_uuid\\" \\"uuid\\" DEFAULT \\"gen_random_uuid\\"() NOT NULL,\n    \\"fish_code\\" \\"text\\",\n    \\"name\\" \\"text\\",\n    \\"created_at\\" timestamp with time zone DEFAULT \\"now\\"() NOT NULL,\n    \\"created_by\\" \\"text\\",\n    \\"date_birth\\" \\"date\\",\n    \\"id\\" \\"uuid\\" DEFAULT \\"gen_random_uuid\\"() NOT NULL,\n    \\"father_fish_id\\" \\"uuid\\",\n    \\"mother_fish_id\\" \\"uuid\\"\n)","ALTER TABLE \\"public\\".\\"fish\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"fish_tanks\\" (\n    \\"fish_name\\" \\"text\\" NOT NULL,\n    \\"linked_at\\" timestamp with time zone DEFAULT \\"now\\"() NOT NULL,\n    \\"fish_id\\" \\"uuid\\",\n    \\"tank_id\\" \\"uuid\\"\n)","ALTER TABLE \\"public\\".\\"fish_tanks\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"fish_treatments\\" (\n    \\"id_uuid\\" \\"uuid\\" DEFAULT \\"gen_random_uuid\\"() NOT NULL,\n    \\"applied_at\\" timestamp with time zone,\n    \\"notes\\" \\"text\\",\n    \\"created_at\\" timestamp with time zone DEFAULT \\"now\\"() NOT NULL,\n    \\"created_by\\" \\"text\\",\n    \\"updated_at\\" timestamp with time zone DEFAULT \\"now\\"() NOT NULL,\n    \\"updated_by\\" \\"text\\",\n    \\"fish_id\\" \\"uuid\\" NOT NULL,\n    \\"treatment_id\\" \\"uuid\\" NOT NULL\n)","ALTER TABLE \\"public\\".\\"fish_treatments\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"fish_year_counters\\" (\n    \\"year\\" integer NOT NULL,\n    \\"n\\" integer DEFAULT 0 NOT NULL\n)","ALTER TABLE \\"public\\".\\"fish_year_counters\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"genotypes\\" (\n    \\"id_uuid\\" \\"uuid\\" DEFAULT \\"gen_random_uuid\\"() NOT NULL,\n    \\"transgene_id_uuid\\" \\"uuid\\" NOT NULL,\n    \\"zygosity\\" \\"text\\",\n    \\"notes\\" \\"text\\",\n    \\"created_at\\" timestamp with time zone DEFAULT \\"now\\"() NOT NULL,\n    \\"created_by\\" \\"text\\",\n    \\"fish_id\\" \\"uuid\\",\n    CONSTRAINT \\"genotypes_zygosity_check\\" CHECK ((\\"zygosity\\" = ANY (ARRAY['het'::\\"text\\", 'hom'::\\"text\\", 'wt'::\\"text\\", 'unk'::\\"text\\"])))\n)","ALTER TABLE \\"public\\".\\"genotypes\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"injected_plasmid_treatments\\" (\n    \\"concentration_ng_per_ul\\" numeric,\n    \\"volume_nl\\" numeric,\n    \\"injection_stage\\" \\"text\\",\n    \\"vehicle\\" \\"text\\",\n    \\"enzyme\\" \\"text\\",\n    \\"id\\" \\"uuid\\" DEFAULT \\"gen_random_uuid\\"(),\n    \\"treatment_id\\" \\"uuid\\" NOT NULL,\n    \\"plasmid_id\\" \\"uuid\\" NOT NULL\n)","ALTER TABLE \\"public\\".\\"injected_plasmid_treatments\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"injected_rna_treatments\\" (\n    \\"concentration_ng_per_ul\\" numeric,\n    \\"volume_nl\\" numeric,\n    \\"injection_stage\\" \\"text\\",\n    \\"vehicle\\" \\"text\\",\n    \\"id\\" \\"uuid\\" DEFAULT \\"gen_random_uuid\\"(),\n    \\"treatment_id\\" \\"uuid\\" NOT NULL,\n    \\"rna_id\\" \\"uuid\\" NOT NULL\n)","ALTER TABLE \\"public\\".\\"injected_rna_treatments\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"plasmid_counters\\" (\n    \\"n\\" integer DEFAULT 0 NOT NULL\n)","ALTER TABLE \\"public\\".\\"plasmid_counters\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"plasmids\\" (\n    \\"id_uuid\\" \\"uuid\\" DEFAULT \\"gen_random_uuid\\"() NOT NULL,\n    \\"plasmid_code\\" \\"text\\",\n    \\"name\\" \\"text\\",\n    \\"created_at\\" timestamp with time zone DEFAULT \\"now\\"() NOT NULL,\n    \\"created_by\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"plasmids\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"rna_counters\\" (\n    \\"n\\" integer DEFAULT 0 NOT NULL\n)","ALTER TABLE \\"public\\".\\"rna_counters\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"rnas\\" (\n    \\"id_uuid\\" \\"uuid\\" DEFAULT \\"gen_random_uuid\\"() NOT NULL,\n    \\"rna_code\\" \\"text\\",\n    \\"name\\" \\"text\\",\n    \\"created_at\\" timestamp with time zone DEFAULT \\"now\\"() NOT NULL,\n    \\"created_by\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"rnas\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"seed_fish_tmp\\" (\n    \\"fish_name\\" \\"text\\",\n    \\"nickname\\" double precision,\n    \\"date_birth\\" \\"text\\",\n    \\"line_building_stage\\" \\"text\\",\n    \\"strain\\" \\"text\\",\n    \\"has_transgene\\" bigint,\n    \\"has_mutation\\" bigint,\n    \\"has_treatment_injected_plasmid\\" bigint,\n    \\"has_treatment_injected_rna\\" bigint,\n    \\"has_treatment_dye\\" bigint,\n    \\"n_new_tanks\\" bigint,\n    \\"seed_batch_id\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"seed_fish_tmp\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"seed_transgenes_tmp\\" (\n    \\"fish_name\\" \\"text\\",\n    \\"transgene_name\\" \\"text\\",\n    \\"allele_name\\" \\"text\\",\n    \\"zygosity\\" \\"text\\",\n    \\"new_allele_note\\" double precision,\n    \\"seed_batch_id\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"seed_transgenes_tmp\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"seed_treatment_dye_tmp\\" (\n    \\"fish_name\\" \\"text\\",\n    \\"dye_name\\" \\"text\\",\n    \\"operator\\" \\"text\\",\n    \\"performed_at\\" \\"text\\",\n    \\"description\\" double precision,\n    \\"notes\\" \\"text\\",\n    \\"seed_batch_id\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"seed_treatment_dye_tmp\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"seed_treatment_injected_plasmid_tmp\\" (\n    \\"fish_name\\" \\"text\\",\n    \\"plasmid_name\\" \\"text\\",\n    \\"operator\\" \\"text\\",\n    \\"performed_at\\" \\"text\\",\n    \\"batch_label\\" \\"text\\",\n    \\"injection_mix\\" \\"text\\",\n    \\"injection_notes\\" double precision,\n    \\"enzyme\\" \\"text\\",\n    \\"seed_batch_id\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"seed_treatment_injected_plasmid_tmp\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"seed_treatment_injected_rna_tmp\\" (\n    \\"fish_name\\" \\"text\\",\n    \\"rna_name\\" \\"text\\",\n    \\"operator\\" \\"text\\",\n    \\"performed_at\\" \\"text\\",\n    \\"description\\" double precision,\n    \\"notes\\" \\"text\\",\n    \\"seed_batch_id\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"seed_treatment_injected_rna_tmp\\" OWNER TO \\"postgres\\"","CREATE SEQUENCE IF NOT EXISTS \\"public\\".\\"seq_tank_code\\"\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1","ALTER SEQUENCE \\"public\\".\\"seq_tank_code\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"staging_links_dye\\" (\n    \\"fish_code\\" \\"text\\",\n    \\"dye_code\\" \\"text\\",\n    \\"treatment_batch_id\\" \\"text\\",\n    \\"performed_at\\" timestamp with time zone,\n    \\"operator\\" \\"text\\",\n    \\"amount\\" numeric,\n    \\"units\\" \\"text\\",\n    \\"route\\" \\"text\\",\n    \\"notes\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"staging_links_dye\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"staging_links_dye_by_name\\" (\n    \\"fish_name\\" \\"text\\",\n    \\"dye_name\\" \\"text\\",\n    \\"treatment_batch_id\\" \\"text\\",\n    \\"performed_at\\" timestamp with time zone,\n    \\"operator\\" \\"text\\",\n    \\"amount\\" numeric,\n    \\"units\\" \\"text\\",\n    \\"route\\" \\"text\\",\n    \\"notes\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"staging_links_dye_by_name\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"staging_links_injected_plasmid\\" (\n    \\"fish_code\\" \\"text\\",\n    \\"plasmid_code\\" \\"text\\",\n    \\"treatment_batch_id\\" \\"text\\",\n    \\"performed_at\\" timestamp with time zone,\n    \\"operator\\" \\"text\\",\n    \\"concentration_ng_per_ul\\" numeric,\n    \\"volume_nl\\" numeric,\n    \\"injection_stage\\" \\"text\\",\n    \\"vehicle\\" \\"text\\",\n    \\"notes\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"staging_links_injected_plasmid\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"staging_links_injected_plasmid_by_name\\" (\n    \\"fish_name\\" \\"text\\",\n    \\"plasmid_name\\" \\"text\\",\n    \\"treatment_batch_id\\" \\"text\\",\n    \\"performed_at\\" timestamp with time zone,\n    \\"operator\\" \\"text\\",\n    \\"concentration_ng_per_ul\\" numeric,\n    \\"volume_nl\\" numeric,\n    \\"injection_stage\\" \\"text\\",\n    \\"vehicle\\" \\"text\\",\n    \\"notes\\" \\"text\\",\n    \\"enzyme\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"staging_links_injected_plasmid_by_name\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"staging_links_injected_rna\\" (\n    \\"fish_code\\" \\"text\\",\n    \\"rna_code\\" \\"text\\",\n    \\"treatment_batch_id\\" \\"text\\",\n    \\"performed_at\\" timestamp with time zone,\n    \\"operator\\" \\"text\\",\n    \\"concentration_ng_per_ul\\" numeric,\n    \\"volume_nl\\" numeric,\n    \\"injection_stage\\" \\"text\\",\n    \\"vehicle\\" \\"text\\",\n    \\"notes\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"staging_links_injected_rna\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"staging_links_injected_rna_by_name\\" (\n    \\"fish_name\\" \\"text\\",\n    \\"rna_name\\" \\"text\\",\n    \\"treatment_batch_id\\" \\"text\\",\n    \\"performed_at\\" timestamp with time zone,\n    \\"operator\\" \\"text\\",\n    \\"concentration_ng_per_ul\\" numeric,\n    \\"volume_nl\\" numeric,\n    \\"injection_stage\\" \\"text\\",\n    \\"vehicle\\" \\"text\\",\n    \\"notes\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"staging_links_injected_rna_by_name\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"stg_dye\\" (\n    \\"fish_name\\" \\"text\\",\n    \\"dye_name\\" \\"text\\",\n    \\"operator\\" \\"text\\",\n    \\"performed_at\\" timestamp with time zone,\n    \\"notes\\" \\"text\\",\n    \\"source\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"stg_dye\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"stg_inj_plasmid\\" (\n    \\"fish_name\\" \\"text\\",\n    \\"plasmid_name\\" \\"text\\",\n    \\"operator\\" \\"text\\",\n    \\"performed_at\\" \\"text\\",\n    \\"batch_label\\" \\"text\\",\n    \\"injection_mix\\" \\"text\\",\n    \\"injection_notes\\" \\"text\\",\n    \\"enzyme\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"stg_inj_plasmid\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"stg_inj_rna\\" (\n    \\"fish_name\\" \\"text\\",\n    \\"rna_name\\" \\"text\\",\n    \\"operator\\" \\"text\\",\n    \\"performed_at\\" timestamp with time zone,\n    \\"notes\\" \\"text\\",\n    \\"source\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"stg_inj_rna\\" OWNER TO \\"postgres\\"","CREATE SEQUENCE IF NOT EXISTS \\"public\\".\\"tank_counters\\"\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1","ALTER SEQUENCE \\"public\\".\\"tank_counters\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"tanks\\" (\n    \\"id\\" bigint NOT NULL,\n    \\"tank_code\\" \\"text\\" NOT NULL,\n    \\"created_at\\" timestamp with time zone DEFAULT \\"now\\"() NOT NULL,\n    \\"id_uuid\\" \\"uuid\\"\n)","ALTER TABLE \\"public\\".\\"tanks\\" OWNER TO \\"postgres\\"","CREATE SEQUENCE IF NOT EXISTS \\"public\\".\\"tanks_id_seq\\"\n    START WITH 1\n    INCREMENT BY 1\n    NO MINVALUE\n    NO MAXVALUE\n    CACHE 1","ALTER SEQUENCE \\"public\\".\\"tanks_id_seq\\" OWNER TO \\"postgres\\"","ALTER SEQUENCE \\"public\\".\\"tanks_id_seq\\" OWNED BY \\"public\\".\\"tanks\\".\\"id\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"transgenes\\" (\n    \\"id_uuid\\" \\"uuid\\" DEFAULT \\"gen_random_uuid\\"() NOT NULL,\n    \\"base_code\\" \\"text\\" NOT NULL,\n    \\"allele_num\\" \\"text\\",\n    \\"name\\" \\"text\\",\n    \\"created_at\\" timestamp with time zone DEFAULT \\"now\\"() NOT NULL,\n    \\"created_by\\" \\"text\\"\n)","ALTER TABLE \\"public\\".\\"transgenes\\" OWNER TO \\"postgres\\"","CREATE TABLE IF NOT EXISTS \\"public\\".\\"treatments\\" (\n    \\"id_uuid\\" \\"uuid\\" DEFAULT \\"gen_random_uuid\\"() NOT NULL,\n    \\"treatment_type\\" \\"public\\".\\"treatment_type_enum\\" NOT NULL,\n    \\"batch_id\\" \\"text\\",\n    \\"performed_at\\" timestamp with time zone,\n    \\"operator\\" \\"text\\",\n    \\"notes\\" \\"text\\",\n    \\"created_at\\" timestamp with time zone DEFAULT \\"now\\"() NOT NULL,\n    \\"created_by\\" \\"text\\",\n    \\"batch_label\\" \\"text\\",\n    \\"performed_on_date\\" \\"date\\" GENERATED ALWAYS AS (((\\"performed_at\\" AT TIME ZONE 'America/Los_Angeles'::\\"text\\"))::\\"date\\") STORED,\n    \\"id\\" \\"uuid\\" NOT NULL\n)","ALTER TABLE \\"public\\".\\"treatments\\" OWNER TO \\"postgres\\"","CREATE OR REPLACE VIEW \\"public\\".\\"v_dye_treatments\\" AS\n SELECT \\"ft\\".\\"fish_id\\",\n    \\"dt\\".\\"treatment_id\\",\n    \\"d\\".\\"name\\" AS \\"dye_name\\"\n   FROM ((\\"public\\".\\"fish_treatments\\" \\"ft\\"\n     JOIN \\"public\\".\\"dye_treatments\\" \\"dt\\" ON ((\\"dt\\".\\"treatment_id\\" = \\"ft\\".\\"treatment_id\\")))\n     JOIN \\"public\\".\\"dyes\\" \\"d\\" ON ((\\"d\\".\\"id_uuid\\" = \\"dt\\".\\"dye_id\\")))","ALTER VIEW \\"public\\".\\"v_dye_treatments\\" OWNER TO \\"postgres\\"","CREATE OR REPLACE VIEW \\"public\\".\\"v_plasmid_treatments\\" AS\n SELECT \\"ft\\".\\"fish_id\\",\n    \\"ipt\\".\\"treatment_id\\",\n    \\"p\\".\\"name\\" AS \\"plasmid_name\\"\n   FROM ((\\"public\\".\\"fish_treatments\\" \\"ft\\"\n     JOIN \\"public\\".\\"injected_plasmid_treatments\\" \\"ipt\\" ON ((\\"ipt\\".\\"treatment_id\\" = \\"ft\\".\\"treatment_id\\")))\n     JOIN \\"public\\".\\"plasmids\\" \\"p\\" ON ((\\"p\\".\\"id_uuid\\" = \\"ipt\\".\\"plasmid_id\\")))","ALTER VIEW \\"public\\".\\"v_plasmid_treatments\\" OWNER TO \\"postgres\\"","CREATE OR REPLACE VIEW \\"public\\".\\"v_rna_treatments\\" AS\n SELECT \\"ft\\".\\"fish_id\\",\n    \\"irt\\".\\"treatment_id\\",\n    \\"r\\".\\"name\\" AS \\"rna_name\\"\n   FROM ((\\"public\\".\\"fish_treatments\\" \\"ft\\"\n     JOIN \\"public\\".\\"injected_rna_treatments\\" \\"irt\\" ON ((\\"irt\\".\\"treatment_id\\" = \\"ft\\".\\"treatment_id\\")))\n     JOIN \\"public\\".\\"rnas\\" \\"r\\" ON ((\\"r\\".\\"id_uuid\\" = \\"irt\\".\\"rna_id\\")))","ALTER VIEW \\"public\\".\\"v_rna_treatments\\" OWNER TO \\"postgres\\"","CREATE OR REPLACE VIEW \\"public\\".\\"v_fish_overview_v1\\" AS\n WITH \\"tanks\\" AS (\n         SELECT \\"ft\\".\\"fish_id\\",\n            \\"string_agg\\"(DISTINCT COALESCE(\\"t\\".\\"tank_code\\", (\\"t\\".\\"id_uuid\\")::\\"text\\"), ', '::\\"text\\" ORDER BY COALESCE(\\"t\\".\\"tank_code\\", (\\"t\\".\\"id_uuid\\")::\\"text\\")) AS \\"tanks\\"\n           FROM (\\"public\\".\\"fish_tanks\\" \\"ft\\"\n             JOIN \\"public\\".\\"tanks\\" \\"t\\" ON ((\\"t\\".\\"id_uuid\\" = \\"ft\\".\\"tank_id\\")))\n          GROUP BY \\"ft\\".\\"fish_id\\"\n        ), \\"plas\\" AS (\n         SELECT \\"vpt\\".\\"fish_id\\",\n            \\"string_agg\\"(DISTINCT \\"vpt\\".\\"plasmid_name\\", ', '::\\"text\\" ORDER BY \\"vpt\\".\\"plasmid_name\\") AS \\"plasmids\\"\n           FROM \\"public\\".\\"v_plasmid_treatments\\" \\"vpt\\"\n          GROUP BY \\"vpt\\".\\"fish_id\\"\n        ), \\"genos\\" AS (\n         SELECT \\"g\\".\\"fish_id\\",\n            \\"string_agg\\"(DISTINCT COALESCE(\\"tg\\".\\"name\\", \\"tg\\".\\"base_code\\"), ', '::\\"text\\" ORDER BY COALESCE(\\"tg\\".\\"name\\", \\"tg\\".\\"base_code\\")) AS \\"genotypes\\"\n           FROM (\\"public\\".\\"genotypes\\" \\"g\\"\n             JOIN \\"public\\".\\"transgenes\\" \\"tg\\" ON ((\\"tg\\".\\"id_uuid\\" = \\"g\\".\\"transgene_id_uuid\\")))\n          GROUP BY \\"g\\".\\"fish_id\\"\n        ), \\"rnas\\" AS (\n         SELECT \\"v\\".\\"fish_id\\",\n            \\"string_agg\\"(DISTINCT \\"v\\".\\"rna_name\\", ', '::\\"text\\" ORDER BY \\"v\\".\\"rna_name\\") AS \\"rnas\\"\n           FROM \\"public\\".\\"v_rna_treatments\\" \\"v\\"\n          GROUP BY \\"v\\".\\"fish_id\\"\n        ), \\"dyes\\" AS (\n         SELECT \\"v\\".\\"fish_id\\",\n            \\"string_agg\\"(DISTINCT \\"v\\".\\"dye_name\\", ', '::\\"text\\" ORDER BY \\"v\\".\\"dye_name\\") AS \\"dyes\\"\n           FROM \\"public\\".\\"v_dye_treatments\\" \\"v\\"\n          GROUP BY \\"v\\".\\"fish_id\\"\n        ), \\"treats\\" AS (\n         SELECT \\"s\\".\\"fish_id\\",\n            \\"string_agg\\"(DISTINCT \\"s\\".\\"val\\", '; '::\\"text\\" ORDER BY \\"s\\".\\"val\\") AS \\"treatments\\"\n           FROM ( SELECT \\"ft\\".\\"fish_id\\",\n                    (COALESCE((\\"tr_1\\".\\"treatment_type\\")::\\"text\\", 'unknown'::\\"text\\") ||\n                        CASE\n                            WHEN (TRIM(BOTH FROM COALESCE(\\"tr_1\\".\\"notes\\", ''::\\"text\\")) <> ''::\\"text\\") THEN ((' ('::\\"text\\" || TRIM(BOTH FROM \\"tr_1\\".\\"notes\\")) || ')'::\\"text\\")\n                            ELSE ''::\\"text\\"\n                        END) AS \\"val\\"\n                   FROM (\\"public\\".\\"fish_treatments\\" \\"ft\\"\n                     JOIN \\"public\\".\\"treatments\\" \\"tr_1\\" ON ((\\"tr_1\\".\\"id\\" = \\"ft\\".\\"treatment_id\\")))) \\"s\\"\n          GROUP BY \\"s\\".\\"fish_id\\"\n        )\n SELECT \\"f\\".\\"id\\" AS \\"fish_id\\",\n    \\"f\\".\\"name\\" AS \\"fish_name\\",\n    \\"f\\".\\"date_birth\\",\n    \\"f\\".\\"created_at\\",\n    COALESCE(\\"tn\\".\\"tanks\\", ''::\\"text\\") AS \\"tanks\\",\n    COALESCE(\\"tr\\".\\"treatments\\", ''::\\"text\\") AS \\"treatments\\",\n    COALESCE(\\"pl\\".\\"plasmids\\", ''::\\"text\\") AS \\"plasmids\\",\n    COALESCE(\\"gn\\".\\"genotypes\\", ''::\\"text\\") AS \\"genotypes\\",\n    COALESCE(\\"rn\\".\\"rnas\\", ''::\\"text\\") AS \\"rnas\\",\n    COALESCE(\\"dy\\".\\"dyes\\", ''::\\"text\\") AS \\"dyes\\"\n   FROM ((((((\\"public\\".\\"fish\\" \\"f\\"\n     LEFT JOIN \\"tanks\\" \\"tn\\" ON ((\\"tn\\".\\"fish_id\\" = \\"f\\".\\"id\\")))\n     LEFT JOIN \\"treats\\" \\"tr\\" ON ((\\"tr\\".\\"fish_id\\" = \\"f\\".\\"id\\")))\n     LEFT JOIN \\"plas\\" \\"pl\\" ON ((\\"pl\\".\\"fish_id\\" = \\"f\\".\\"id\\")))\n     LEFT JOIN \\"genos\\" \\"gn\\" ON ((\\"gn\\".\\"fish_id\\" = \\"f\\".\\"id\\")))\n     LEFT JOIN \\"rnas\\" \\"rn\\" ON ((\\"rn\\".\\"fish_id\\" = \\"f\\".\\"id\\")))\n     LEFT JOIN \\"dyes\\" \\"dy\\" ON ((\\"dy\\".\\"fish_id\\" = \\"f\\".\\"id\\")))\n  ORDER BY \\"f\\".\\"created_at\\", \\"f\\".\\"name\\"","ALTER VIEW \\"public\\".\\"v_fish_overview_v1\\" OWNER TO \\"postgres\\"","ALTER TABLE ONLY \\"public\\".\\"tanks\\" ALTER COLUMN \\"id\\" SET DEFAULT \\"nextval\\"('\\"public\\".\\"tanks_id_seq\\"'::\\"regclass\\")","ALTER TABLE ONLY \\"public\\".\\"dyes\\"\n    ADD CONSTRAINT \\"dyes_dye_code_key\\" UNIQUE (\\"dye_code\\")","ALTER TABLE ONLY \\"public\\".\\"dyes\\"\n    ADD CONSTRAINT \\"dyes_pkey\\" PRIMARY KEY (\\"id_uuid\\")","ALTER TABLE ONLY \\"public\\".\\"fish\\"\n    ADD CONSTRAINT \\"fish_fish_code_key\\" UNIQUE (\\"fish_code\\")","ALTER TABLE ONLY \\"public\\".\\"fish\\"\n    ADD CONSTRAINT \\"fish_name_key\\" UNIQUE (\\"name\\")","ALTER TABLE ONLY \\"public\\".\\"fish\\"\n    ADD CONSTRAINT \\"fish_pkey\\" PRIMARY KEY (\\"id_uuid\\")","ALTER TABLE ONLY \\"public\\".\\"fish_treatments\\"\n    ADD CONSTRAINT \\"fish_treatments_pkey\\" PRIMARY KEY (\\"id_uuid\\")","ALTER TABLE ONLY \\"public\\".\\"fish_year_counters\\"\n    ADD CONSTRAINT \\"fish_year_counters_pkey\\" PRIMARY KEY (\\"year\\")","ALTER TABLE ONLY \\"public\\".\\"genotypes\\"\n    ADD CONSTRAINT \\"genotypes_pkey\\" PRIMARY KEY (\\"id_uuid\\")","ALTER TABLE ONLY \\"public\\".\\"plasmids\\"\n    ADD CONSTRAINT \\"plasmids_pkey\\" PRIMARY KEY (\\"id_uuid\\")","ALTER TABLE ONLY \\"public\\".\\"plasmids\\"\n    ADD CONSTRAINT \\"plasmids_plasmid_code_key\\" UNIQUE (\\"plasmid_code\\")","ALTER TABLE ONLY \\"public\\".\\"rnas\\"\n    ADD CONSTRAINT \\"rnas_pkey\\" PRIMARY KEY (\\"id_uuid\\")","ALTER TABLE ONLY \\"public\\".\\"rnas\\"\n    ADD CONSTRAINT \\"rnas_rna_code_key\\" UNIQUE (\\"rna_code\\")","ALTER TABLE ONLY \\"public\\".\\"tanks\\"\n    ADD CONSTRAINT \\"tanks_pkey\\" PRIMARY KEY (\\"id\\")","ALTER TABLE ONLY \\"public\\".\\"tanks\\"\n    ADD CONSTRAINT \\"tanks_tank_code_key\\" UNIQUE (\\"tank_code\\")","ALTER TABLE ONLY \\"public\\".\\"transgenes\\"\n    ADD CONSTRAINT \\"transgenes_name_key\\" UNIQUE (\\"name\\")","ALTER TABLE ONLY \\"public\\".\\"transgenes\\"\n    ADD CONSTRAINT \\"transgenes_pkey\\" PRIMARY KEY (\\"id_uuid\\")","ALTER TABLE ONLY \\"public\\".\\"treatments\\"\n    ADD CONSTRAINT \\"treatments_pkey\\" PRIMARY KEY (\\"id_uuid\\")","ALTER TABLE ONLY \\"public\\".\\"dye_treatments\\"\n    ADD CONSTRAINT \\"uq_dt_treatment\\" UNIQUE (\\"treatment_id\\")","ALTER TABLE ONLY \\"public\\".\\"injected_plasmid_treatments\\"\n    ADD CONSTRAINT \\"uq_ipt_treatment\\" UNIQUE (\\"treatment_id\\")","ALTER TABLE ONLY \\"public\\".\\"injected_rna_treatments\\"\n    ADD CONSTRAINT \\"uq_irt_treatment\\" UNIQUE (\\"treatment_id\\")","CREATE UNIQUE INDEX \\"idx_fish_name_unique\\" ON \\"public\\".\\"fish\\" USING \\"btree\\" (\\"name\\")","CREATE INDEX \\"ix_dye_treatments_dye\\" ON \\"public\\".\\"dye_treatments\\" USING \\"btree\\" (\\"dye_id\\")","CREATE INDEX \\"ix_fish_name\\" ON \\"public\\".\\"fish\\" USING \\"btree\\" (\\"name\\")","CREATE INDEX \\"ix_fish_treatments_treatment\\" ON \\"public\\".\\"fish_treatments\\" USING \\"btree\\" (\\"treatment_id\\")","CREATE INDEX \\"ix_genotypes_transgene\\" ON \\"public\\".\\"genotypes\\" USING \\"btree\\" (\\"transgene_id_uuid\\")","CREATE INDEX \\"ix_injected_plasmid_treatments_plasmid\\" ON \\"public\\".\\"injected_plasmid_treatments\\" USING \\"btree\\" (\\"plasmid_id\\")","CREATE INDEX \\"ix_injected_rna_treatments_rna\\" ON \\"public\\".\\"injected_rna_treatments\\" USING \\"btree\\" (\\"rna_id\\")","CREATE INDEX \\"ix_ipt_enzyme_ci\\" ON \\"public\\".\\"injected_plasmid_treatments\\" USING \\"btree\\" (\\"lower\\"(\\"enzyme\\")) WHERE (\\"enzyme\\" IS NOT NULL)","CREATE INDEX \\"ix_treatments_batch\\" ON \\"public\\".\\"treatments\\" USING \\"btree\\" (\\"batch_id\\")","CREATE INDEX \\"ix_treatments_operator_ci\\" ON \\"public\\".\\"treatments\\" USING \\"btree\\" (\\"lower\\"(\\"operator\\")) WHERE (\\"operator\\" IS NOT NULL)","CREATE INDEX \\"ix_treatments_type\\" ON \\"public\\".\\"treatments\\" USING \\"btree\\" (\\"treatment_type\\")","CREATE UNIQUE INDEX \\"uq_dye_name_ci\\" ON \\"public\\".\\"dyes\\" USING \\"btree\\" (\\"lower\\"(\\"name\\")) WHERE (\\"name\\" IS NOT NULL)","CREATE UNIQUE INDEX \\"uq_fish_id\\" ON \\"public\\".\\"fish\\" USING \\"btree\\" (\\"id\\")","CREATE UNIQUE INDEX \\"uq_fish_name_ci\\" ON \\"public\\".\\"fish\\" USING \\"btree\\" (\\"lower\\"(\\"name\\")) WHERE (\\"name\\" IS NOT NULL)","CREATE UNIQUE INDEX \\"uq_fish_treatments_pair\\" ON \\"public\\".\\"fish_treatments\\" USING \\"btree\\" (\\"fish_id\\", \\"treatment_id\\")","CREATE UNIQUE INDEX \\"uq_genotypes_fish_transgene\\" ON \\"public\\".\\"genotypes\\" USING \\"btree\\" (\\"fish_id\\", \\"transgene_id_uuid\\")","CREATE UNIQUE INDEX \\"uq_plasmids_name_ci\\" ON \\"public\\".\\"plasmids\\" USING \\"btree\\" (\\"lower\\"(\\"name\\")) WHERE (\\"name\\" IS NOT NULL)","CREATE UNIQUE INDEX \\"uq_rna_name_ci\\" ON \\"public\\".\\"rnas\\" USING \\"btree\\" (\\"lower\\"(\\"name\\")) WHERE (\\"name\\" IS NOT NULL)","CREATE UNIQUE INDEX \\"uq_tanks_id_uuid\\" ON \\"public\\".\\"tanks\\" USING \\"btree\\" (\\"id_uuid\\")","CREATE UNIQUE INDEX \\"uq_tanks_tank_code\\" ON \\"public\\".\\"tanks\\" USING \\"btree\\" (\\"tank_code\\")","CREATE UNIQUE INDEX \\"uq_treatments_id\\" ON \\"public\\".\\"treatments\\" USING \\"btree\\" (\\"id\\")","CREATE OR REPLACE TRIGGER \\"trg_batch_guard_dye\\" AFTER INSERT OR UPDATE ON \\"public\\".\\"dye_treatments\\" FOR EACH ROW EXECUTE FUNCTION \\"public\\".\\"treatment_batch_guard_v2\\"()","CREATE OR REPLACE TRIGGER \\"trg_batch_guard_plasmid\\" AFTER INSERT OR UPDATE ON \\"public\\".\\"injected_plasmid_treatments\\" FOR EACH ROW EXECUTE FUNCTION \\"public\\".\\"treatment_batch_guard_v2\\"()","CREATE OR REPLACE TRIGGER \\"trg_batch_guard_rna\\" AFTER INSERT OR UPDATE ON \\"public\\".\\"injected_rna_treatments\\" FOR EACH ROW EXECUTE FUNCTION \\"public\\".\\"treatment_batch_guard_v2\\"()","CREATE OR REPLACE TRIGGER \\"trg_batch_guard_treat\\" AFTER INSERT OR UPDATE ON \\"public\\".\\"treatments\\" FOR EACH ROW EXECUTE FUNCTION \\"public\\".\\"treatment_batch_guard_v2\\"()","CREATE OR REPLACE TRIGGER \\"trg_dye_code_autofill\\" BEFORE INSERT ON \\"public\\".\\"dyes\\" FOR EACH ROW EXECUTE FUNCTION \\"public\\".\\"dye_code_autofill\\"()","CREATE OR REPLACE TRIGGER \\"trg_fish_code_autofill\\" BEFORE INSERT ON \\"public\\".\\"fish\\" FOR EACH ROW EXECUTE FUNCTION \\"public\\".\\"fish_code_autofill\\"()","CREATE OR REPLACE TRIGGER \\"trg_ft_updated_at\\" BEFORE UPDATE ON \\"public\\".\\"fish_treatments\\" FOR EACH ROW EXECUTE FUNCTION \\"public\\".\\"set_updated_at\\"()","CREATE OR REPLACE TRIGGER \\"trg_plasmid_code_autofill\\" BEFORE INSERT ON \\"public\\".\\"plasmids\\" FOR EACH ROW EXECUTE FUNCTION \\"public\\".\\"plasmid_code_autofill\\"()","CREATE OR REPLACE TRIGGER \\"trg_rna_code_autofill\\" BEFORE INSERT ON \\"public\\".\\"rnas\\" FOR EACH ROW EXECUTE FUNCTION \\"public\\".\\"rna_code_autofill\\"()","CREATE OR REPLACE TRIGGER \\"trg_set_tank_code\\" BEFORE INSERT ON \\"public\\".\\"tanks\\" FOR EACH ROW EXECUTE FUNCTION \\"public\\".\\"trg_set_tank_code\\"()","CREATE OR REPLACE TRIGGER \\"trg_type_guard_dye\\" BEFORE INSERT OR UPDATE ON \\"public\\".\\"dye_treatments\\" FOR EACH ROW EXECUTE FUNCTION \\"public\\".\\"detail_type_guard_v2\\"()","CREATE OR REPLACE TRIGGER \\"trg_type_guard_plasmid\\" BEFORE INSERT OR UPDATE ON \\"public\\".\\"injected_plasmid_treatments\\" FOR EACH ROW EXECUTE FUNCTION \\"public\\".\\"detail_type_guard_v2\\"()","CREATE OR REPLACE TRIGGER \\"trg_type_guard_rna\\" BEFORE INSERT OR UPDATE ON \\"public\\".\\"injected_rna_treatments\\" FOR EACH ROW EXECUTE FUNCTION \\"public\\".\\"detail_type_guard_v2\\"()","ALTER TABLE ONLY \\"public\\".\\"dye_treatments\\"\n    ADD CONSTRAINT \\"dye_treatments_dye_fk\\" FOREIGN KEY (\\"dye_id\\") REFERENCES \\"public\\".\\"dyes\\"(\\"id_uuid\\") ON DELETE CASCADE","ALTER TABLE ONLY \\"public\\".\\"dye_treatments\\"\n    ADD CONSTRAINT \\"dye_treatments_treatment_fk\\" FOREIGN KEY (\\"treatment_id\\") REFERENCES \\"public\\".\\"treatments\\"(\\"id\\") ON DELETE CASCADE","ALTER TABLE ONLY \\"public\\".\\"fish\\"\n    ADD CONSTRAINT \\"fish_father_fk\\" FOREIGN KEY (\\"father_fish_id\\") REFERENCES \\"public\\".\\"fish\\"(\\"id\\") ON DELETE SET NULL","ALTER TABLE ONLY \\"public\\".\\"fish\\"\n    ADD CONSTRAINT \\"fish_mother_fk\\" FOREIGN KEY (\\"mother_fish_id\\") REFERENCES \\"public\\".\\"fish\\"(\\"id\\") ON DELETE SET NULL","ALTER TABLE ONLY \\"public\\".\\"fish_tanks\\"\n    ADD CONSTRAINT \\"fish_tanks_tank_fk\\" FOREIGN KEY (\\"tank_id\\") REFERENCES \\"public\\".\\"tanks\\"(\\"id_uuid\\") ON DELETE SET NULL","ALTER TABLE ONLY \\"public\\".\\"fish_treatments\\"\n    ADD CONSTRAINT \\"fish_treatments_fish_fk\\" FOREIGN KEY (\\"fish_id\\") REFERENCES \\"public\\".\\"fish\\"(\\"id\\") ON DELETE CASCADE","ALTER TABLE ONLY \\"public\\".\\"fish_treatments\\"\n    ADD CONSTRAINT \\"fish_treatments_treatment_fk\\" FOREIGN KEY (\\"treatment_id\\") REFERENCES \\"public\\".\\"treatments\\"(\\"id\\") ON DELETE CASCADE","ALTER TABLE ONLY \\"public\\".\\"genotypes\\"\n    ADD CONSTRAINT \\"genotypes_fish_fk\\" FOREIGN KEY (\\"fish_id\\") REFERENCES \\"public\\".\\"fish\\"(\\"id\\") ON DELETE CASCADE","ALTER TABLE ONLY \\"public\\".\\"genotypes\\"\n    ADD CONSTRAINT \\"genotypes_transgene_id_uuid_fkey\\" FOREIGN KEY (\\"transgene_id_uuid\\") REFERENCES \\"public\\".\\"transgenes\\"(\\"id_uuid\\") ON DELETE CASCADE","ALTER TABLE ONLY \\"public\\".\\"injected_rna_treatments\\"\n    ADD CONSTRAINT \\"injected_rna_treatments_rna_fk\\" FOREIGN KEY (\\"rna_id\\") REFERENCES \\"public\\".\\"rnas\\"(\\"id_uuid\\") ON DELETE CASCADE","ALTER TABLE ONLY \\"public\\".\\"injected_rna_treatments\\"\n    ADD CONSTRAINT \\"injected_rna_treatments_treatment_fk\\" FOREIGN KEY (\\"treatment_id\\") REFERENCES \\"public\\".\\"treatments\\"(\\"id\\") ON DELETE CASCADE","ALTER TABLE ONLY \\"public\\".\\"injected_plasmid_treatments\\"\n    ADD CONSTRAINT \\"ipt_plasmid_fk\\" FOREIGN KEY (\\"plasmid_id\\") REFERENCES \\"public\\".\\"plasmids\\"(\\"id_uuid\\")","ALTER TABLE ONLY \\"public\\".\\"injected_plasmid_treatments\\"\n    ADD CONSTRAINT \\"ipt_treatment_fk\\" FOREIGN KEY (\\"treatment_id\\") REFERENCES \\"public\\".\\"treatments\\"(\\"id\\") ON DELETE CASCADE","REVOKE USAGE ON SCHEMA \\"public\\" FROM PUBLIC","GRANT SELECT ON TABLE \\"public\\".\\"v_dye_treatments\\" TO \\"anon\\"","GRANT SELECT ON TABLE \\"public\\".\\"v_dye_treatments\\" TO \\"authenticated\\"","GRANT SELECT ON TABLE \\"public\\".\\"v_dye_treatments\\" TO \\"service_role\\"","GRANT SELECT ON TABLE \\"public\\".\\"v_plasmid_treatments\\" TO \\"anon\\"","GRANT SELECT ON TABLE \\"public\\".\\"v_plasmid_treatments\\" TO \\"authenticated\\"","GRANT SELECT ON TABLE \\"public\\".\\"v_plasmid_treatments\\" TO \\"service_role\\"","GRANT SELECT ON TABLE \\"public\\".\\"v_rna_treatments\\" TO \\"anon\\"","GRANT SELECT ON TABLE \\"public\\".\\"v_rna_treatments\\" TO \\"authenticated\\"","GRANT SELECT ON TABLE \\"public\\".\\"v_rna_treatments\\" TO \\"service_role\\"","GRANT SELECT ON TABLE \\"public\\".\\"v_fish_overview_v1\\" TO \\"anon\\"","GRANT SELECT ON TABLE \\"public\\".\\"v_fish_overview_v1\\" TO \\"authenticated\\"","GRANT SELECT ON TABLE \\"public\\".\\"v_fish_overview_v1\\" TO \\"service_role\\"","RESET ALL"}	baseline
20250922115105	\N	schema_pre
20250922115106	\N	schema_post
20250922150010	{"-- Ensure public.transgenes exposes a canonical text key: transgene_base_code.\n\nDO $$\nDECLARE\n  pk_col  text;\n  pk_type text;\nBEGIN\n  IF EXISTS (\n    SELECT 1\n    FROM information_schema.columns\n    WHERE table_schema='public' AND table_name='transgenes'\n      AND column_name='transgene_base_code'\n  ) THEN\n    RAISE NOTICE 'transgenes.transgene_base_code already exists';\n    RETURN;\n  END IF;\n\n  IF EXISTS (\n    SELECT 1 FROM information_schema.columns\n    WHERE table_schema='public' AND table_name='transgenes' AND column_name='code'\n  ) THEN\n    EXECUTE 'ALTER TABLE public.transgenes RENAME COLUMN \\"code\\" TO transgene_base_code';\n  ELSIF EXISTS (\n    SELECT 1 FROM information_schema.columns\n    WHERE table_schema='public' AND table_name='transgenes' AND column_name='name'\n  ) THEN\n    EXECUTE 'ALTER TABLE public.transgenes RENAME COLUMN \\"name\\" TO transgene_base_code';\n  ELSE\n    SELECT a.attname,\n           COALESCE(c.data_type, format_type(a.atttypid, a.atttypmod))\n      INTO pk_col, pk_type\n    FROM pg_constraint con\n    JOIN pg_class t       ON t.oid = con.conrelid\n    JOIN pg_namespace n   ON n.oid = t.relnamespace\n    JOIN unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE\n    JOIN pg_attribute a   ON a.attrelid = t.oid AND a.attnum = k.attnum\n    LEFT JOIN information_schema.columns c\n           ON c.table_schema = n.nspname AND c.table_name = t.relname AND c.column_name = a.attname\n    WHERE n.nspname='public' AND t.relname='transgenes' AND con.contype='p'\n    ORDER BY k.ord\n    LIMIT 1;\n\n    EXECUTE 'ALTER TABLE public.transgenes ADD COLUMN transgene_base_code text';\n\n    IF pk_col IS NOT NULL THEN\n      EXECUTE format('UPDATE public.transgenes SET transgene_base_code = %I::text', pk_col);\n    ELSE\n      EXECUTE 'CREATE EXTENSION IF NOT EXISTS pgcrypto';\n      EXECUTE 'UPDATE public.transgenes SET transgene_base_code = md5(gen_random_uuid()::text)';\n    END IF;\n\n    EXECUTE 'ALTER TABLE public.transgenes ALTER COLUMN transgene_base_code SET NOT NULL';\n  END IF;\n\n  IF NOT EXISTS (\n    SELECT 1 FROM pg_constraint con\n    JOIN pg_class t     ON t.oid = con.conrelid\n    JOIN pg_namespace n ON n.oid = t.relnamespace\n    WHERE n.nspname='public' AND t.relname='transgenes' AND con.contype='p'\n  ) THEN\n    EXECUTE 'ALTER TABLE public.transgenes ADD CONSTRAINT transgenes_pkey PRIMARY KEY (transgene_base_code)';\n  ELSE\n    IF NOT EXISTS (\n      SELECT 1 FROM pg_constraint con\n      JOIN pg_class t     ON t.oid = con.conrelid\n      JOIN pg_namespace n ON n.oid = t.relnamespace\n      WHERE n.nspname='public' AND t.relname='transgenes' AND con.contype='u'\n        AND pg_get_constraintdef(con.oid) LIKE 'UNIQUE (transgene_base_code)'\n    ) THEN\n      EXECUTE 'ALTER TABLE public.transgenes ADD CONSTRAINT transgenes_transgene_base_code_key UNIQUE (transgene_base_code)';\n    END IF;\n  END IF;\nEND$$ LANGUAGE plpgsql"}	fix_transgenes_key
20250922160000	{"-- Transgenes (already present in your DB, but keep this idempotent)\ncreate table if not exists public.transgenes (\n  transgene_base_code text primary key\n)","-- Specific alleles of a transgene (composite PK)\ncreate table if not exists public.transgene_alleles (\n  transgene_base_code text not null,\n  allele_number       text not null,\n  description         text,\n  constraint transgene_alleles_pk primary key (transgene_base_code, allele_number),\n  constraint transgene_alleles_fk_transgene\n    foreign key (transgene_base_code)\n    references public.transgenes(transgene_base_code)\n    on delete cascade\n)","-- Link: fish ↔ specific allele (+ optional zygosity)\ncreate table if not exists public.fish_transgene_alleles (\n  fish_id             uuid not null,\n  transgene_base_code text not null,\n  allele_number       text not null,\n  zygosity            text,  -- e.g. homozygous / heterozygous / unknown\n  constraint fish_transgene_alleles_pk\n    primary key (fish_id, transgene_base_code, allele_number),\n  constraint fish_transgene_alleles_fk_fish\n    foreign key (fish_id) references public.fish(id)\n    on delete cascade,\n  constraint fish_transgene_alleles_fk_allele\n    foreign key (transgene_base_code, allele_number)\n    references public.transgene_alleles(transgene_base_code, allele_number)\n    on delete cascade\n)","-- Optional nudge away from legacy booleans\ndo $$\nbegin\n  if exists (\n    select 1\n    from information_schema.columns\n    where table_schema='public' and table_name='fish'\n      and column_name like 'has_%'\n  ) then\n    raise notice 'Consider removing legacy has_* columns on public.fish (use fish_transgene_alleles instead).';\n  end if;\nend$$"}	genetics_core
20250922161000	{"DO $$\nDECLARE v text;\nBEGIN\n  -- Only patch if the view exists\n  IF to_regclass('public.v_fish_overview_v1') IS NOT NULL THEN\n    v := pg_get_viewdef('public.v_fish_overview_v1'::regclass, true);\n    -- Replace both fully-qualified and alias-based \\".base_code\\"\n    v := replace(v, 'transgenes.base_code', 'transgenes.transgene_base_code');\n    v := regexp_replace(v, '([A-Za-z_][A-Za-z0-9_]*)\\\\.base_code', '\\\\1.transgene_base_code', 'gi');\n    EXECUTE 'CREATE OR REPLACE VIEW public.v_fish_overview_v1 AS ' || v;\n  END IF;\nEND$$ LANGUAGE plpgsql"}	patch_views_for_transgene_key
20250922161100	{BEGIN,"-- One-time sync just in case anything left the two columns out of sync.\nUPDATE public.transgenes\nSET transgene_base_code = COALESCE(transgene_base_code, base_code)\nWHERE base_code IS NOT NULL","-- Drop any remaining indexes on base_code (belt & suspenders)\nDO $$\nDECLARE r record;\nBEGIN\n  FOR r IN\n    SELECT i.indexname\n    FROM pg_indexes i\n    WHERE i.schemaname='public'\n      AND i.tablename='transgenes'\n      AND i.indexdef ILIKE '%(base_code%'\n  LOOP\n    EXECUTE format('DROP INDEX IF EXISTS %I', r.indexname);\n  END LOOP;\nEND$$","ALTER TABLE public.transgenes\n  DROP COLUMN IF EXISTS base_code",COMMIT}	drop_transgenes_base_code
20250922170000	{"DO $$\nDECLARE\n  v      text;\n  vlist  text[];\nBEGIN\n  -- 1) Gather dependent views (anything referencing public.transgenes)\n  SELECT array_agg(quote_ident(n.nspname) || '.' || quote_ident(c.relname))\n  INTO vlist\n  FROM pg_depend d\n  JOIN pg_rewrite  r  ON r.oid = d.objid\n  JOIN pg_class    c  ON c.oid = r.ev_class AND c.relkind = 'v'\n  JOIN pg_namespace n ON n.oid = c.relnamespace\n  JOIN pg_class    t  ON t.oid = d.refobjid\n  JOIN pg_namespace nt ON nt.oid = t.relnamespace\n  WHERE nt.nspname = 'public' AND t.relname = 'transgenes';\n\n  -- 2) Drop those views (we already keep view SQL in repo, so safe)\n  IF vlist IS NOT NULL THEN\n    FOREACH v IN ARRAY vlist LOOP\n      EXECUTE format('DROP VIEW IF EXISTS %s', v);\n    END LOOP;\n  END IF;\nEND$$ LANGUAGE plpgsql","-- 3) *** your table changes go here ***\n-- e.g. ALTER TABLE public.transgenes RENAME COLUMN base_code TO transgene_base_code;\n\n-- 4) Recreate views (either paste CREATEs here, or keep as separate migrations)\n-- Example:\n-- CREATE OR REPLACE VIEW public.v_fish_overview_v1 AS\n-- <paste the SELECT body here>;"}	views_rebuild_after_transgene_refactor
20250922170500	{BEGIN,"-- Add the columns the seedkit expects (safe if they already exist)\nALTER TABLE public.fish\n  ADD COLUMN IF NOT EXISTS date_of_birth       date,\n  ADD COLUMN IF NOT EXISTS line_building_stage text,\n  ADD COLUMN IF NOT EXISTS strain              text","-- Ensure fish_code exists & is unique\nALTER TABLE public.fish\n  ADD COLUMN IF NOT EXISTS fish_code text","CREATE UNIQUE INDEX IF NOT EXISTS fish_fish_code_key\n  ON public.fish(fish_code)","-- Keep these handy on genetics tables\nALTER TABLE public.transgenes\n  ADD COLUMN IF NOT EXISTS name        text,\n  ADD COLUMN IF NOT EXISTS description text","ALTER TABLE public.transgene_alleles\n  ADD COLUMN IF NOT EXISTS description text",COMMIT}	fish_add_core_columns
20250922201746	\N	20250922_add_xyz
20250922	{"-- Raw landing schema (safe to re-run)\ncreate schema if not exists raw","-- 01_fish.csv\ncreate table if not exists raw.fish_csv (\n  fish_name              text,\n  mother                 text,\n  date_of_birth          text,\n  status                 text,\n  strain                 text,\n  alive                  text,\n  breeding_pairing       text,\n  fish_code              text,\n  archived               text,\n  died                   text,\n  who                    text\n)","-- 10_fish_links_has_transgenes.csv\ncreate table if not exists raw.fish_links_has_transgenes_csv (\n  fish_name       text,\n  transgene_name  text,\n  allele_name     text,\n  zygosity        text,\n  new_allele_note text\n)","-- 10_fish_links_has_treatment_dye.csv\ncreate table if not exists raw.fish_links_has_treatment_dye_csv (\n  fish_name   text,\n  dye_name    text,\n  operator    text,\n  performed_at text,\n  description text,\n  notes       text\n)","-- 10_fish_links_has_treatment_injected_plasmid.csv\ncreate table if not exists raw.fish_links_has_treatment_injected_plasmid_csv (\n  fish_name      text,\n  plasmid_name   text,\n  operator       text,\n  performed_at   text,\n  batch_label    text,\n  injection_mix  text,\n  injection_notes text,\n  enzyme         text\n)","-- 10_fish_links_has_treatment_injected_rna.csv\ncreate table if not exists raw.fish_links_has_treatment_injected_rna_csv (\n  fish_name   text,\n  rna_name    text,\n  operator    text,\n  performed_at text,\n  description text,\n  notes       text\n)"}	raw_ingest_tables
\.


--
-- Data for Name: seed_files; Type: TABLE DATA; Schema: supabase_migrations; Owner: postgres
--

COPY supabase_migrations.seed_files (path, hash) FROM stdin;
supabase/seed.sql	a7e9a8eb629674d59f36c067401d5d40fec7ad0deb078062a763ab8ef332f5cd
\.


--
-- Data for Name: secrets; Type: TABLE DATA; Schema: vault; Owner: supabase_admin
--

COPY vault.secrets (id, name, description, secret, key_id, nonce, created_at, updated_at) FROM stdin;
\.


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE SET; Schema: auth; Owner: supabase_auth_admin
--

SELECT pg_catalog.setval('auth.refresh_tokens_id_seq', 1, false);


--
-- Name: fish_code_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.fish_code_seq', 10, true);


--
-- Name: seq_tank_code; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.seq_tank_code', 1, false);


--
-- Name: tank_counters; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tank_counters', 1, false);


--
-- Name: tanks_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tanks_id_seq', 1, false);


--
-- Name: subscription_id_seq; Type: SEQUENCE SET; Schema: realtime; Owner: supabase_admin
--

SELECT pg_catalog.setval('realtime.subscription_id_seq', 1, false);


--
-- Name: hooks_id_seq; Type: SEQUENCE SET; Schema: supabase_functions; Owner: supabase_functions_admin
--

SELECT pg_catalog.setval('supabase_functions.hooks_id_seq', 1, false);


--
-- Name: extensions extensions_pkey; Type: CONSTRAINT; Schema: _realtime; Owner: postgres
--

ALTER TABLE ONLY _realtime.extensions
    ADD CONSTRAINT extensions_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: _realtime; Owner: postgres
--

ALTER TABLE ONLY _realtime.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: _realtime; Owner: supabase_admin
--

ALTER TABLE ONLY _realtime.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: mfa_amr_claims amr_id_pk; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT amr_id_pk PRIMARY KEY (id);


--
-- Name: audit_log_entries audit_log_entries_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.audit_log_entries
    ADD CONSTRAINT audit_log_entries_pkey PRIMARY KEY (id);


--
-- Name: flow_state flow_state_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.flow_state
    ADD CONSTRAINT flow_state_pkey PRIMARY KEY (id);


--
-- Name: identities identities_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_pkey PRIMARY KEY (id);


--
-- Name: identities identities_provider_id_provider_unique; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_provider_id_provider_unique UNIQUE (provider_id, provider);


--
-- Name: instances instances_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.instances
    ADD CONSTRAINT instances_pkey PRIMARY KEY (id);


--
-- Name: mfa_amr_claims mfa_amr_claims_session_id_authentication_method_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT mfa_amr_claims_session_id_authentication_method_pkey UNIQUE (session_id, authentication_method);


--
-- Name: mfa_challenges mfa_challenges_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_challenges
    ADD CONSTRAINT mfa_challenges_pkey PRIMARY KEY (id);


--
-- Name: mfa_factors mfa_factors_last_challenged_at_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_last_challenged_at_key UNIQUE (last_challenged_at);


--
-- Name: mfa_factors mfa_factors_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_pkey PRIMARY KEY (id);


--
-- Name: oauth_clients oauth_clients_client_id_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_clients
    ADD CONSTRAINT oauth_clients_client_id_key UNIQUE (client_id);


--
-- Name: oauth_clients oauth_clients_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.oauth_clients
    ADD CONSTRAINT oauth_clients_pkey PRIMARY KEY (id);


--
-- Name: one_time_tokens one_time_tokens_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.one_time_tokens
    ADD CONSTRAINT one_time_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_token_unique; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_token_unique UNIQUE (token);


--
-- Name: saml_providers saml_providers_entity_id_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_entity_id_key UNIQUE (entity_id);


--
-- Name: saml_providers saml_providers_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_pkey PRIMARY KEY (id);


--
-- Name: saml_relay_states saml_relay_states_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: sso_domains sso_domains_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sso_domains
    ADD CONSTRAINT sso_domains_pkey PRIMARY KEY (id);


--
-- Name: sso_providers sso_providers_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sso_providers
    ADD CONSTRAINT sso_providers_pkey PRIMARY KEY (id);


--
-- Name: users users_phone_key; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_phone_key UNIQUE (phone);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: dyes dyes_dye_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dyes
    ADD CONSTRAINT dyes_dye_code_key UNIQUE (dye_code);


--
-- Name: dyes dyes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dyes
    ADD CONSTRAINT dyes_pkey PRIMARY KEY (id_uuid);


--
-- Name: fish_code_counters fish_code_counters_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fish_code_counters
    ADD CONSTRAINT fish_code_counters_pkey PRIMARY KEY (year_small);


--
-- Name: fish fish_fish_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT fish_fish_code_key UNIQUE (fish_code);


--
-- Name: fish fish_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT fish_pkey PRIMARY KEY (id_uuid);


--
-- Name: fish_transgene_alleles fish_transgene_alleles_pk; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fish_transgene_alleles
    ADD CONSTRAINT fish_transgene_alleles_pk PRIMARY KEY (fish_id, transgene_base_code, allele_number);


--
-- Name: fish_transgenes fish_transgenes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fish_transgenes
    ADD CONSTRAINT fish_transgenes_pkey PRIMARY KEY (fish_id, transgene_code);


--
-- Name: fish_treatments fish_treatments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fish_treatments
    ADD CONSTRAINT fish_treatments_pkey PRIMARY KEY (id_uuid);


--
-- Name: fish_year_counters fish_year_counters_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fish_year_counters
    ADD CONSTRAINT fish_year_counters_pkey PRIMARY KEY (year);


--
-- Name: genotypes genotypes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.genotypes
    ADD CONSTRAINT genotypes_pkey PRIMARY KEY (id_uuid);


--
-- Name: plasmids plasmids_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plasmids
    ADD CONSTRAINT plasmids_pkey PRIMARY KEY (id_uuid);


--
-- Name: plasmids plasmids_plasmid_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plasmids
    ADD CONSTRAINT plasmids_plasmid_code_key UNIQUE (plasmid_code);


--
-- Name: rnas rnas_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.rnas
    ADD CONSTRAINT rnas_pkey PRIMARY KEY (id_uuid);


--
-- Name: rnas rnas_rna_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.rnas
    ADD CONSTRAINT rnas_rna_code_key UNIQUE (rna_code);


--
-- Name: tank_assignments tank_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tank_assignments
    ADD CONSTRAINT tank_assignments_pkey PRIMARY KEY (fish_id);


--
-- Name: tank_code_counters tank_code_counters_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tank_code_counters
    ADD CONSTRAINT tank_code_counters_pkey PRIMARY KEY (prefix, year_small);


--
-- Name: tanks tanks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tanks
    ADD CONSTRAINT tanks_pkey PRIMARY KEY (id);


--
-- Name: tanks tanks_tank_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tanks
    ADD CONSTRAINT tanks_tank_code_key UNIQUE (tank_code);


--
-- Name: transgene_alleles transgene_alleles_pk; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transgene_alleles
    ADD CONSTRAINT transgene_alleles_pk PRIMARY KEY (transgene_base_code, allele_number);


--
-- Name: transgenes transgenes_code_unique; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transgenes
    ADD CONSTRAINT transgenes_code_unique UNIQUE (code);


--
-- Name: transgenes transgenes_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transgenes
    ADD CONSTRAINT transgenes_name_key UNIQUE (transgene_base_code);


--
-- Name: transgenes transgenes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transgenes
    ADD CONSTRAINT transgenes_pkey PRIMARY KEY (id_uuid);


--
-- Name: treatments treatments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.treatments
    ADD CONSTRAINT treatments_pkey PRIMARY KEY (id_uuid);


--
-- Name: treatments treatments_treatment_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.treatments
    ADD CONSTRAINT treatments_treatment_code_key UNIQUE (treatment_code);


--
-- Name: dye_treatments uq_dt_treatment; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dye_treatments
    ADD CONSTRAINT uq_dt_treatment UNIQUE (treatment_id);


--
-- Name: injected_plasmid_treatments uq_ipt_treatment; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.injected_plasmid_treatments
    ADD CONSTRAINT uq_ipt_treatment UNIQUE (treatment_id);


--
-- Name: injected_rna_treatments uq_irt_treatment; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.injected_rna_treatments
    ADD CONSTRAINT uq_irt_treatment UNIQUE (treatment_id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER TABLE ONLY realtime.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_09_21 messages_2025_09_21_pkey; Type: CONSTRAINT; Schema: realtime; Owner: postgres
--

ALTER TABLE ONLY realtime.messages_2025_09_21
    ADD CONSTRAINT messages_2025_09_21_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_09_22 messages_2025_09_22_pkey; Type: CONSTRAINT; Schema: realtime; Owner: postgres
--

ALTER TABLE ONLY realtime.messages_2025_09_22
    ADD CONSTRAINT messages_2025_09_22_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_09_23 messages_2025_09_23_pkey; Type: CONSTRAINT; Schema: realtime; Owner: postgres
--

ALTER TABLE ONLY realtime.messages_2025_09_23
    ADD CONSTRAINT messages_2025_09_23_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_09_24 messages_2025_09_24_pkey; Type: CONSTRAINT; Schema: realtime; Owner: postgres
--

ALTER TABLE ONLY realtime.messages_2025_09_24
    ADD CONSTRAINT messages_2025_09_24_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: messages_2025_09_25 messages_2025_09_25_pkey; Type: CONSTRAINT; Schema: realtime; Owner: postgres
--

ALTER TABLE ONLY realtime.messages_2025_09_25
    ADD CONSTRAINT messages_2025_09_25_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: subscription pk_subscription; Type: CONSTRAINT; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.subscription
    ADD CONSTRAINT pk_subscription PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: realtime; Owner: supabase_admin
--

ALTER TABLE ONLY realtime.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: buckets buckets_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.buckets
    ADD CONSTRAINT buckets_pkey PRIMARY KEY (id);


--
-- Name: migrations migrations_name_key; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.migrations
    ADD CONSTRAINT migrations_name_key UNIQUE (name);


--
-- Name: migrations migrations_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.migrations
    ADD CONSTRAINT migrations_pkey PRIMARY KEY (id);


--
-- Name: objects objects_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.objects
    ADD CONSTRAINT objects_pkey PRIMARY KEY (id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_pkey PRIMARY KEY (id);


--
-- Name: s3_multipart_uploads s3_multipart_uploads_pkey; Type: CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads
    ADD CONSTRAINT s3_multipart_uploads_pkey PRIMARY KEY (id);


--
-- Name: hooks hooks_pkey; Type: CONSTRAINT; Schema: supabase_functions; Owner: supabase_functions_admin
--

ALTER TABLE ONLY supabase_functions.hooks
    ADD CONSTRAINT hooks_pkey PRIMARY KEY (id);


--
-- Name: migrations migrations_pkey; Type: CONSTRAINT; Schema: supabase_functions; Owner: supabase_functions_admin
--

ALTER TABLE ONLY supabase_functions.migrations
    ADD CONSTRAINT migrations_pkey PRIMARY KEY (version);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: supabase_migrations; Owner: postgres
--

ALTER TABLE ONLY supabase_migrations.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: seed_files seed_files_pkey; Type: CONSTRAINT; Schema: supabase_migrations; Owner: postgres
--

ALTER TABLE ONLY supabase_migrations.seed_files
    ADD CONSTRAINT seed_files_pkey PRIMARY KEY (path);


--
-- Name: extensions_tenant_external_id_index; Type: INDEX; Schema: _realtime; Owner: postgres
--

CREATE INDEX extensions_tenant_external_id_index ON _realtime.extensions USING btree (tenant_external_id);


--
-- Name: extensions_tenant_external_id_type_index; Type: INDEX; Schema: _realtime; Owner: postgres
--

CREATE UNIQUE INDEX extensions_tenant_external_id_type_index ON _realtime.extensions USING btree (tenant_external_id, type);


--
-- Name: tenants_external_id_index; Type: INDEX; Schema: _realtime; Owner: supabase_admin
--

CREATE UNIQUE INDEX tenants_external_id_index ON _realtime.tenants USING btree (external_id);


--
-- Name: audit_logs_instance_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX audit_logs_instance_id_idx ON auth.audit_log_entries USING btree (instance_id);


--
-- Name: confirmation_token_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX confirmation_token_idx ON auth.users USING btree (confirmation_token) WHERE ((confirmation_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: email_change_token_current_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX email_change_token_current_idx ON auth.users USING btree (email_change_token_current) WHERE ((email_change_token_current)::text !~ '^[0-9 ]*$'::text);


--
-- Name: email_change_token_new_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX email_change_token_new_idx ON auth.users USING btree (email_change_token_new) WHERE ((email_change_token_new)::text !~ '^[0-9 ]*$'::text);


--
-- Name: factor_id_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX factor_id_created_at_idx ON auth.mfa_factors USING btree (user_id, created_at);


--
-- Name: flow_state_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX flow_state_created_at_idx ON auth.flow_state USING btree (created_at DESC);


--
-- Name: identities_email_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX identities_email_idx ON auth.identities USING btree (email text_pattern_ops);


--
-- Name: INDEX identities_email_idx; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON INDEX auth.identities_email_idx IS 'Auth: Ensures indexed queries on the email column';


--
-- Name: identities_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX identities_user_id_idx ON auth.identities USING btree (user_id);


--
-- Name: idx_auth_code; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX idx_auth_code ON auth.flow_state USING btree (auth_code);


--
-- Name: idx_user_id_auth_method; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX idx_user_id_auth_method ON auth.flow_state USING btree (user_id, authentication_method);


--
-- Name: mfa_challenge_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX mfa_challenge_created_at_idx ON auth.mfa_challenges USING btree (created_at DESC);


--
-- Name: mfa_factors_user_friendly_name_unique; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX mfa_factors_user_friendly_name_unique ON auth.mfa_factors USING btree (friendly_name, user_id) WHERE (TRIM(BOTH FROM friendly_name) <> ''::text);


--
-- Name: mfa_factors_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX mfa_factors_user_id_idx ON auth.mfa_factors USING btree (user_id);


--
-- Name: oauth_clients_client_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_clients_client_id_idx ON auth.oauth_clients USING btree (client_id);


--
-- Name: oauth_clients_deleted_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX oauth_clients_deleted_at_idx ON auth.oauth_clients USING btree (deleted_at);


--
-- Name: one_time_tokens_relates_to_hash_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX one_time_tokens_relates_to_hash_idx ON auth.one_time_tokens USING hash (relates_to);


--
-- Name: one_time_tokens_token_hash_hash_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX one_time_tokens_token_hash_hash_idx ON auth.one_time_tokens USING hash (token_hash);


--
-- Name: one_time_tokens_user_id_token_type_key; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX one_time_tokens_user_id_token_type_key ON auth.one_time_tokens USING btree (user_id, token_type);


--
-- Name: reauthentication_token_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX reauthentication_token_idx ON auth.users USING btree (reauthentication_token) WHERE ((reauthentication_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: recovery_token_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX recovery_token_idx ON auth.users USING btree (recovery_token) WHERE ((recovery_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: refresh_tokens_instance_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_instance_id_idx ON auth.refresh_tokens USING btree (instance_id);


--
-- Name: refresh_tokens_instance_id_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_instance_id_user_id_idx ON auth.refresh_tokens USING btree (instance_id, user_id);


--
-- Name: refresh_tokens_parent_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_parent_idx ON auth.refresh_tokens USING btree (parent);


--
-- Name: refresh_tokens_session_id_revoked_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_session_id_revoked_idx ON auth.refresh_tokens USING btree (session_id, revoked);


--
-- Name: refresh_tokens_updated_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX refresh_tokens_updated_at_idx ON auth.refresh_tokens USING btree (updated_at DESC);


--
-- Name: saml_providers_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX saml_providers_sso_provider_id_idx ON auth.saml_providers USING btree (sso_provider_id);


--
-- Name: saml_relay_states_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX saml_relay_states_created_at_idx ON auth.saml_relay_states USING btree (created_at DESC);


--
-- Name: saml_relay_states_for_email_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX saml_relay_states_for_email_idx ON auth.saml_relay_states USING btree (for_email);


--
-- Name: saml_relay_states_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX saml_relay_states_sso_provider_id_idx ON auth.saml_relay_states USING btree (sso_provider_id);


--
-- Name: sessions_not_after_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sessions_not_after_idx ON auth.sessions USING btree (not_after DESC);


--
-- Name: sessions_user_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sessions_user_id_idx ON auth.sessions USING btree (user_id);


--
-- Name: sso_domains_domain_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX sso_domains_domain_idx ON auth.sso_domains USING btree (lower(domain));


--
-- Name: sso_domains_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sso_domains_sso_provider_id_idx ON auth.sso_domains USING btree (sso_provider_id);


--
-- Name: sso_providers_resource_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX sso_providers_resource_id_idx ON auth.sso_providers USING btree (lower(resource_id));


--
-- Name: sso_providers_resource_id_pattern_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX sso_providers_resource_id_pattern_idx ON auth.sso_providers USING btree (resource_id text_pattern_ops);


--
-- Name: unique_phone_factor_per_user; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX unique_phone_factor_per_user ON auth.mfa_factors USING btree (user_id, phone);


--
-- Name: user_id_created_at_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX user_id_created_at_idx ON auth.sessions USING btree (user_id, created_at);


--
-- Name: users_email_partial_key; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE UNIQUE INDEX users_email_partial_key ON auth.users USING btree (email) WHERE (is_sso_user = false);


--
-- Name: INDEX users_email_partial_key; Type: COMMENT; Schema: auth; Owner: supabase_auth_admin
--

COMMENT ON INDEX auth.users_email_partial_key IS 'Auth: A partial unique index that applies only when is_sso_user is false';


--
-- Name: users_instance_id_email_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX users_instance_id_email_idx ON auth.users USING btree (instance_id, lower((email)::text));


--
-- Name: users_instance_id_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX users_instance_id_idx ON auth.users USING btree (instance_id);


--
-- Name: users_is_anonymous_idx; Type: INDEX; Schema: auth; Owner: supabase_auth_admin
--

CREATE INDEX users_is_anonymous_idx ON auth.users USING btree (is_anonymous);


--
-- Name: idx_fish_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_fish_name ON public.fish USING btree (name);


--
-- Name: ix_dt_dye_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_dt_dye_code ON public.dye_treatments USING btree (dye_code);


--
-- Name: ix_dye_treatments_dye; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_dye_treatments_dye ON public.dye_treatments USING btree (dye_id);


--
-- Name: ix_dyes_name_ci; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_dyes_name_ci ON public.dyes USING btree (lower(name));


--
-- Name: ix_fish_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_fish_code ON public.fish USING btree (fish_code);


--
-- Name: ix_fish_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_fish_name ON public.fish USING btree (name);


--
-- Name: ix_fish_transgenes_fish; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_fish_transgenes_fish ON public.fish_transgenes USING btree (fish_id);


--
-- Name: ix_fish_transgenes_tg; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_fish_transgenes_tg ON public.fish_transgenes USING btree (transgene_code);


--
-- Name: ix_fish_treatments_treatment; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_fish_treatments_treatment ON public.fish_treatments USING btree (treatment_id);


--
-- Name: ix_genotypes_transgene; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_genotypes_transgene ON public.genotypes USING btree (transgene_id_uuid);


--
-- Name: ix_injected_plasmid_treatments_plasmid; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_injected_plasmid_treatments_plasmid ON public.injected_plasmid_treatments USING btree (plasmid_id);


--
-- Name: ix_injected_rna_treatments_rna; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_injected_rna_treatments_rna ON public.injected_rna_treatments USING btree (rna_id);


--
-- Name: ix_ipt_enzyme_ci; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_ipt_enzyme_ci ON public.injected_plasmid_treatments USING btree (lower(enzyme)) WHERE (enzyme IS NOT NULL);


--
-- Name: ix_ipt_plasmid_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_ipt_plasmid_code ON public.injected_plasmid_treatments USING btree (plasmid_code);


--
-- Name: ix_irt_rna_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_irt_rna_code ON public.injected_rna_treatments USING btree (rna_code);


--
-- Name: ix_links_fish; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_links_fish ON public.fish_transgene_alleles USING btree (fish_id);


--
-- Name: ix_links_tgallele; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_links_tgallele ON public.fish_transgene_alleles USING btree (transgene_base_code, allele_number);


--
-- Name: ix_rnas_name_ci; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_rnas_name_ci ON public.rnas USING btree (lower(name));


--
-- Name: ix_tank_assignments_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_tank_assignments_status ON public.tank_assignments USING btree (status);


--
-- Name: ix_tg_alleles_pk; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_tg_alleles_pk ON public.transgene_alleles USING btree (transgene_base_code, allele_number);


--
-- Name: ix_treatments_batch; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_treatments_batch ON public.treatments USING btree (batch_id);


--
-- Name: ix_treatments_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_treatments_code ON public.treatments USING btree (treatment_code);


--
-- Name: ix_treatments_fish; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_treatments_fish ON public.treatments USING btree (fish_id);


--
-- Name: ix_treatments_operator_ci; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_treatments_operator_ci ON public.treatments USING btree (lower(operator)) WHERE (operator IS NOT NULL);


--
-- Name: ix_treatments_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_treatments_type ON public.treatments USING btree (treatment_type);


--
-- Name: ix_treatments_type_time_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_treatments_type_time_code ON public.treatments USING btree (treatment_type, performed_at, code);


--
-- Name: uq_dye_name_ci; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_dye_name_ci ON public.dyes USING btree (lower(name)) WHERE (name IS NOT NULL);


--
-- Name: uq_fish_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_fish_id ON public.fish USING btree (id);


--
-- Name: uq_fish_tg_allele; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_fish_tg_allele ON public.fish_transgene_alleles USING btree (fish_id, transgene_base_code, allele_number);


--
-- Name: uq_fish_treatments; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_fish_treatments ON public.fish_treatments USING btree (fish_id, treatment_id);


--
-- Name: uq_fish_treatments_pair; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_fish_treatments_pair ON public.fish_treatments USING btree (fish_id, treatment_id);


--
-- Name: uq_genotypes_fish_transgene; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_genotypes_fish_transgene ON public.genotypes USING btree (fish_id, transgene_id_uuid);


--
-- Name: uq_plasmids_name_ci; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_plasmids_name_ci ON public.plasmids USING btree (lower(name)) WHERE (name IS NOT NULL);


--
-- Name: uq_rna_name_ci; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_rna_name_ci ON public.rnas USING btree (lower(name)) WHERE (name IS NOT NULL);


--
-- Name: uq_tanks_id_uuid; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_tanks_id_uuid ON public.tanks USING btree (id_uuid);


--
-- Name: uq_tanks_tank_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_tanks_tank_code ON public.tanks USING btree (tank_code);


--
-- Name: uq_treatments_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_treatments_id ON public.treatments USING btree (id);


--
-- Name: uq_treatments_treatment_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_treatments_treatment_code ON public.treatments USING btree (treatment_code);


--
-- Name: ux_fish_auto_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ux_fish_auto_code ON public.fish USING btree (auto_fish_code);


--
-- Name: ux_fish_name; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ux_fish_name ON public.fish USING btree (name);


--
-- Name: ux_tank_assignments_fish; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ux_tank_assignments_fish ON public.tank_assignments USING btree (fish_id);


--
-- Name: ux_tank_code_counters_prefix_year; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ux_tank_code_counters_prefix_year ON public.tank_code_counters USING btree (prefix, year_small);


--
-- Name: ux_transgenes_base; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ux_transgenes_base ON public.transgenes USING btree (transgene_base_code);


--
-- Name: ux_transgenes_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ux_transgenes_code ON public.transgenes USING btree (code);


--
-- Name: ix_realtime_subscription_entity; Type: INDEX; Schema: realtime; Owner: supabase_admin
--

CREATE INDEX ix_realtime_subscription_entity ON realtime.subscription USING btree (entity);


--
-- Name: subscription_subscription_id_entity_filters_key; Type: INDEX; Schema: realtime; Owner: supabase_admin
--

CREATE UNIQUE INDEX subscription_subscription_id_entity_filters_key ON realtime.subscription USING btree (subscription_id, entity, filters);


--
-- Name: bname; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE UNIQUE INDEX bname ON storage.buckets USING btree (name);


--
-- Name: bucketid_objname; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE UNIQUE INDEX bucketid_objname ON storage.objects USING btree (bucket_id, name);


--
-- Name: idx_multipart_uploads_list; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX idx_multipart_uploads_list ON storage.s3_multipart_uploads USING btree (bucket_id, key, created_at);


--
-- Name: idx_objects_bucket_id_name; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX idx_objects_bucket_id_name ON storage.objects USING btree (bucket_id, name COLLATE "C");


--
-- Name: name_prefix_search; Type: INDEX; Schema: storage; Owner: supabase_storage_admin
--

CREATE INDEX name_prefix_search ON storage.objects USING btree (name text_pattern_ops);


--
-- Name: supabase_functions_hooks_h_table_id_h_name_idx; Type: INDEX; Schema: supabase_functions; Owner: supabase_functions_admin
--

CREATE INDEX supabase_functions_hooks_h_table_id_h_name_idx ON supabase_functions.hooks USING btree (hook_table_id, hook_name);


--
-- Name: supabase_functions_hooks_request_id_idx; Type: INDEX; Schema: supabase_functions; Owner: supabase_functions_admin
--

CREATE INDEX supabase_functions_hooks_request_id_idx ON supabase_functions.hooks USING btree (request_id);


--
-- Name: messages_2025_09_21_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_09_21_pkey;


--
-- Name: messages_2025_09_22_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_09_22_pkey;


--
-- Name: messages_2025_09_23_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_09_23_pkey;


--
-- Name: messages_2025_09_24_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_09_24_pkey;


--
-- Name: messages_2025_09_25_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_09_25_pkey;


--
-- Name: fish trg_assign_auto_fish_code; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_assign_auto_fish_code BEFORE INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.assign_auto_fish_code();


--
-- Name: tank_assignments trg_assign_tank_label; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_assign_tank_label BEFORE INSERT ON public.tank_assignments FOR EACH ROW EXECUTE FUNCTION public.assign_tank_label();


--
-- Name: fish trg_assign_tank_on_insert; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_assign_tank_on_insert AFTER INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.assign_tank_on_insert();


--
-- Name: fish trg_auto_assign_tank; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_auto_assign_tank AFTER INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.auto_assign_tank();


--
-- Name: dye_treatments trg_batch_guard_dye; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_batch_guard_dye AFTER INSERT OR UPDATE ON public.dye_treatments FOR EACH ROW EXECUTE FUNCTION public.treatment_batch_guard_v2();


--
-- Name: injected_plasmid_treatments trg_batch_guard_plasmid; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_batch_guard_plasmid AFTER INSERT OR UPDATE ON public.injected_plasmid_treatments FOR EACH ROW EXECUTE FUNCTION public.treatment_batch_guard_v2();


--
-- Name: injected_rna_treatments trg_batch_guard_rna; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_batch_guard_rna AFTER INSERT OR UPDATE ON public.injected_rna_treatments FOR EACH ROW EXECUTE FUNCTION public.treatment_batch_guard_v2();


--
-- Name: treatments trg_batch_guard_treat; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_batch_guard_treat AFTER INSERT OR UPDATE ON public.treatments FOR EACH ROW EXECUTE FUNCTION public.treatment_batch_guard_v2();


--
-- Name: dyes trg_dye_code_autofill; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_dye_code_autofill BEFORE INSERT ON public.dyes FOR EACH ROW EXECUTE FUNCTION public.dye_code_autofill();


--
-- Name: fish trg_fish_code_autofill; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_fish_code_autofill BEFORE INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.fish_code_autofill();


--
-- Name: fish_treatments trg_ft_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_ft_updated_at BEFORE UPDATE ON public.fish_treatments FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: fish trg_no_update_auto_fish_code; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_no_update_auto_fish_code BEFORE UPDATE OF auto_fish_code ON public.fish FOR EACH ROW EXECUTE FUNCTION public.no_update_auto_fish_code();


--
-- Name: plasmids trg_plasmid_code_autofill; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_plasmid_code_autofill BEFORE INSERT ON public.plasmids FOR EACH ROW EXECUTE FUNCTION public.plasmid_code_autofill();


--
-- Name: rnas trg_rna_code_autofill; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_rna_code_autofill BEFORE INSERT ON public.rnas FOR EACH ROW EXECUTE FUNCTION public.rna_code_autofill();


--
-- Name: tanks trg_set_tank_code; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_set_tank_code BEFORE INSERT ON public.tanks FOR EACH ROW EXECUTE FUNCTION public.trg_set_tank_code();


--
-- Name: treatments trg_treatment_detail_mirror; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_treatment_detail_mirror AFTER INSERT OR UPDATE OF treatment_type, treatment_code, plasmid_code ON public.treatments FOR EACH ROW EXECUTE FUNCTION public.treatment_detail_mirror();


--
-- Name: dye_treatments trg_type_guard_dye; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_type_guard_dye BEFORE INSERT OR UPDATE ON public.dye_treatments FOR EACH ROW EXECUTE FUNCTION public.detail_type_guard_v2();


--
-- Name: injected_plasmid_treatments trg_type_guard_plasmid; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_type_guard_plasmid BEFORE INSERT OR UPDATE ON public.injected_plasmid_treatments FOR EACH ROW EXECUTE FUNCTION public.detail_type_guard_v2();


--
-- Name: injected_rna_treatments trg_type_guard_rna; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_type_guard_rna BEFORE INSERT OR UPDATE ON public.injected_rna_treatments FOR EACH ROW EXECUTE FUNCTION public.detail_type_guard_v2();


--
-- Name: subscription tr_check_filters; Type: TRIGGER; Schema: realtime; Owner: supabase_admin
--

CREATE TRIGGER tr_check_filters BEFORE INSERT OR UPDATE ON realtime.subscription FOR EACH ROW EXECUTE FUNCTION realtime.subscription_check_filters();


--
-- Name: objects update_objects_updated_at; Type: TRIGGER; Schema: storage; Owner: supabase_storage_admin
--

CREATE TRIGGER update_objects_updated_at BEFORE UPDATE ON storage.objects FOR EACH ROW EXECUTE FUNCTION storage.update_updated_at_column();


--
-- Name: identities identities_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: mfa_amr_claims mfa_amr_claims_session_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT mfa_amr_claims_session_id_fkey FOREIGN KEY (session_id) REFERENCES auth.sessions(id) ON DELETE CASCADE;


--
-- Name: mfa_challenges mfa_challenges_auth_factor_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_challenges
    ADD CONSTRAINT mfa_challenges_auth_factor_id_fkey FOREIGN KEY (factor_id) REFERENCES auth.mfa_factors(id) ON DELETE CASCADE;


--
-- Name: mfa_factors mfa_factors_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: one_time_tokens one_time_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.one_time_tokens
    ADD CONSTRAINT one_time_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens refresh_tokens_session_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_session_id_fkey FOREIGN KEY (session_id) REFERENCES auth.sessions(id) ON DELETE CASCADE;


--
-- Name: saml_providers saml_providers_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: saml_relay_states saml_relay_states_flow_state_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_flow_state_id_fkey FOREIGN KEY (flow_state_id) REFERENCES auth.flow_state(id) ON DELETE CASCADE;


--
-- Name: saml_relay_states saml_relay_states_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: sessions sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: sso_domains sso_domains_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE ONLY auth.sso_domains
    ADD CONSTRAINT sso_domains_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: dye_treatments dye_treatments_dye_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dye_treatments
    ADD CONSTRAINT dye_treatments_dye_code_fkey FOREIGN KEY (dye_code) REFERENCES public.dyes(dye_code);


--
-- Name: dye_treatments dye_treatments_dye_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dye_treatments
    ADD CONSTRAINT dye_treatments_dye_fk FOREIGN KEY (dye_id) REFERENCES public.dyes(id_uuid) ON DELETE CASCADE;


--
-- Name: dye_treatments dye_treatments_treatment_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dye_treatments
    ADD CONSTRAINT dye_treatments_treatment_fk FOREIGN KEY (treatment_id) REFERENCES public.treatments(id) ON DELETE CASCADE;


--
-- Name: fish fish_father_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT fish_father_fk FOREIGN KEY (father_fish_id) REFERENCES public.fish(id) ON DELETE SET NULL;


--
-- Name: fish fish_mother_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT fish_mother_fk FOREIGN KEY (mother_fish_id) REFERENCES public.fish(id) ON DELETE SET NULL;


--
-- Name: fish_tanks fish_tanks_tank_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fish_tanks
    ADD CONSTRAINT fish_tanks_tank_fk FOREIGN KEY (tank_id) REFERENCES public.tanks(id_uuid) ON DELETE SET NULL;


--
-- Name: fish_transgene_alleles fish_transgene_alleles_fk_allele; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fish_transgene_alleles
    ADD CONSTRAINT fish_transgene_alleles_fk_allele FOREIGN KEY (transgene_base_code, allele_number) REFERENCES public.transgene_alleles(transgene_base_code, allele_number) ON DELETE CASCADE;


--
-- Name: fish_transgene_alleles fish_transgene_alleles_fk_fish; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fish_transgene_alleles
    ADD CONSTRAINT fish_transgene_alleles_fk_fish FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;


--
-- Name: fish_transgenes fish_transgenes_fish_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fish_transgenes
    ADD CONSTRAINT fish_transgenes_fish_id_fkey FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;


--
-- Name: fish_transgenes fish_transgenes_transgene_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fish_transgenes
    ADD CONSTRAINT fish_transgenes_transgene_code_fkey FOREIGN KEY (transgene_code) REFERENCES public.transgenes(code) ON DELETE RESTRICT;


--
-- Name: fish_treatments fish_treatments_fish_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fish_treatments
    ADD CONSTRAINT fish_treatments_fish_fk FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;


--
-- Name: fish_treatments fish_treatments_treatment_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fish_treatments
    ADD CONSTRAINT fish_treatments_treatment_fk FOREIGN KEY (treatment_id) REFERENCES public.treatments(id) ON DELETE CASCADE;


--
-- Name: genotypes genotypes_fish_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.genotypes
    ADD CONSTRAINT genotypes_fish_fk FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;


--
-- Name: genotypes genotypes_transgene_id_uuid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.genotypes
    ADD CONSTRAINT genotypes_transgene_id_uuid_fkey FOREIGN KEY (transgene_id_uuid) REFERENCES public.transgenes(id_uuid) ON DELETE CASCADE;


--
-- Name: injected_plasmid_treatments injected_plasmid_treatments_plasmid_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.injected_plasmid_treatments
    ADD CONSTRAINT injected_plasmid_treatments_plasmid_code_fkey FOREIGN KEY (plasmid_code) REFERENCES public.plasmids(plasmid_code);


--
-- Name: injected_rna_treatments injected_rna_treatments_rna_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.injected_rna_treatments
    ADD CONSTRAINT injected_rna_treatments_rna_code_fkey FOREIGN KEY (rna_code) REFERENCES public.rnas(rna_code);


--
-- Name: injected_rna_treatments injected_rna_treatments_rna_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.injected_rna_treatments
    ADD CONSTRAINT injected_rna_treatments_rna_fk FOREIGN KEY (rna_id) REFERENCES public.rnas(id_uuid) ON DELETE CASCADE;


--
-- Name: injected_rna_treatments injected_rna_treatments_treatment_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.injected_rna_treatments
    ADD CONSTRAINT injected_rna_treatments_treatment_fk FOREIGN KEY (treatment_id) REFERENCES public.treatments(id) ON DELETE CASCADE;


--
-- Name: injected_plasmid_treatments ipt_plasmid_code_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.injected_plasmid_treatments
    ADD CONSTRAINT ipt_plasmid_code_fk FOREIGN KEY (plasmid_code) REFERENCES public.plasmids(plasmid_code) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: injected_plasmid_treatments ipt_plasmid_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.injected_plasmid_treatments
    ADD CONSTRAINT ipt_plasmid_fk FOREIGN KEY (plasmid_id) REFERENCES public.plasmids(id_uuid);


--
-- Name: injected_plasmid_treatments ipt_treatment_fk; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.injected_plasmid_treatments
    ADD CONSTRAINT ipt_treatment_fk FOREIGN KEY (treatment_id) REFERENCES public.treatments(id) ON DELETE CASCADE;


--
-- Name: tank_assignments tank_assignments_fish_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tank_assignments
    ADD CONSTRAINT tank_assignments_fish_id_fkey FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;


--
-- Name: transgene_alleles transgene_alleles_fk_transgene; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.transgene_alleles
    ADD CONSTRAINT transgene_alleles_fk_transgene FOREIGN KEY (transgene_base_code) REFERENCES public.transgenes(transgene_base_code) ON DELETE CASCADE;


--
-- Name: treatments treatments_fish_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.treatments
    ADD CONSTRAINT treatments_fish_id_fkey FOREIGN KEY (fish_id) REFERENCES public.fish(id);


--
-- Name: treatments treatments_plasmid_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.treatments
    ADD CONSTRAINT treatments_plasmid_code_fkey FOREIGN KEY (plasmid_code) REFERENCES public.plasmids(plasmid_code);


--
-- Name: objects objects_bucketId_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.objects
    ADD CONSTRAINT "objects_bucketId_fkey" FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads s3_multipart_uploads_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads
    ADD CONSTRAINT s3_multipart_uploads_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_upload_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES storage.s3_multipart_uploads(id) ON DELETE CASCADE;


--
-- Name: audit_log_entries; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.audit_log_entries ENABLE ROW LEVEL SECURITY;

--
-- Name: flow_state; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.flow_state ENABLE ROW LEVEL SECURITY;

--
-- Name: identities; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.identities ENABLE ROW LEVEL SECURITY;

--
-- Name: instances; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.instances ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_amr_claims; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.mfa_amr_claims ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_challenges; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.mfa_challenges ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_factors; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.mfa_factors ENABLE ROW LEVEL SECURITY;

--
-- Name: one_time_tokens; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.one_time_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: refresh_tokens; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.refresh_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: saml_providers; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.saml_providers ENABLE ROW LEVEL SECURITY;

--
-- Name: saml_relay_states; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.saml_relay_states ENABLE ROW LEVEL SECURITY;

--
-- Name: schema_migrations; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.schema_migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: sessions; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.sessions ENABLE ROW LEVEL SECURITY;

--
-- Name: sso_domains; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.sso_domains ENABLE ROW LEVEL SECURITY;

--
-- Name: sso_providers; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.sso_providers ENABLE ROW LEVEL SECURITY;

--
-- Name: users; Type: ROW SECURITY; Schema: auth; Owner: supabase_auth_admin
--

ALTER TABLE auth.users ENABLE ROW LEVEL SECURITY;

--
-- Name: messages; Type: ROW SECURITY; Schema: realtime; Owner: supabase_realtime_admin
--

ALTER TABLE realtime.messages ENABLE ROW LEVEL SECURITY;

--
-- Name: buckets; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.buckets ENABLE ROW LEVEL SECURITY;

--
-- Name: migrations; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: objects; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

--
-- Name: s3_multipart_uploads; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.s3_multipart_uploads ENABLE ROW LEVEL SECURITY;

--
-- Name: s3_multipart_uploads_parts; Type: ROW SECURITY; Schema: storage; Owner: supabase_storage_admin
--

ALTER TABLE storage.s3_multipart_uploads_parts ENABLE ROW LEVEL SECURITY;

--
-- Name: supabase_realtime; Type: PUBLICATION; Schema: -; Owner: postgres
--

CREATE PUBLICATION supabase_realtime WITH (publish = 'insert, update, delete, truncate');


ALTER PUBLICATION supabase_realtime OWNER TO postgres;

--
-- Name: SCHEMA auth; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA auth TO anon;
GRANT USAGE ON SCHEMA auth TO authenticated;
GRANT USAGE ON SCHEMA auth TO service_role;
GRANT ALL ON SCHEMA auth TO supabase_auth_admin;
GRANT ALL ON SCHEMA auth TO dashboard_user;
GRANT USAGE ON SCHEMA auth TO postgres;


--
-- Name: SCHEMA extensions; Type: ACL; Schema: -; Owner: postgres
--

GRANT USAGE ON SCHEMA extensions TO anon;
GRANT USAGE ON SCHEMA extensions TO authenticated;
GRANT USAGE ON SCHEMA extensions TO service_role;
GRANT ALL ON SCHEMA extensions TO dashboard_user;


--
-- Name: SCHEMA net; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA net TO supabase_functions_admin;
GRANT USAGE ON SCHEMA net TO postgres;
GRANT USAGE ON SCHEMA net TO anon;
GRANT USAGE ON SCHEMA net TO authenticated;
GRANT USAGE ON SCHEMA net TO service_role;


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: postgres
--

REVOKE USAGE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO anon;
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT USAGE ON SCHEMA public TO service_role;


--
-- Name: SCHEMA realtime; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA realtime TO postgres;
GRANT USAGE ON SCHEMA realtime TO anon;
GRANT USAGE ON SCHEMA realtime TO authenticated;
GRANT USAGE ON SCHEMA realtime TO service_role;
GRANT ALL ON SCHEMA realtime TO supabase_realtime_admin;


--
-- Name: SCHEMA storage; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA storage TO postgres WITH GRANT OPTION;
GRANT USAGE ON SCHEMA storage TO anon;
GRANT USAGE ON SCHEMA storage TO authenticated;
GRANT USAGE ON SCHEMA storage TO service_role;
GRANT ALL ON SCHEMA storage TO supabase_storage_admin;
GRANT ALL ON SCHEMA storage TO dashboard_user;


--
-- Name: SCHEMA supabase_functions; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA supabase_functions TO postgres;
GRANT USAGE ON SCHEMA supabase_functions TO anon;
GRANT USAGE ON SCHEMA supabase_functions TO authenticated;
GRANT USAGE ON SCHEMA supabase_functions TO service_role;
GRANT ALL ON SCHEMA supabase_functions TO supabase_functions_admin;


--
-- Name: SCHEMA vault; Type: ACL; Schema: -; Owner: supabase_admin
--

GRANT USAGE ON SCHEMA vault TO postgres WITH GRANT OPTION;
GRANT USAGE ON SCHEMA vault TO service_role;


--
-- Name: FUNCTION email(); Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON FUNCTION auth.email() TO dashboard_user;


--
-- Name: FUNCTION jwt(); Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON FUNCTION auth.jwt() TO postgres;
GRANT ALL ON FUNCTION auth.jwt() TO dashboard_user;


--
-- Name: FUNCTION role(); Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON FUNCTION auth.role() TO dashboard_user;


--
-- Name: FUNCTION uid(); Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON FUNCTION auth.uid() TO dashboard_user;


--
-- Name: FUNCTION armor(bytea); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.armor(bytea) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION armor(bytea, text[], text[]); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.armor(bytea, text[], text[]) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION crypt(text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.crypt(text, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION dearmor(text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.dearmor(text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION decrypt(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.decrypt(bytea, bytea, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION decrypt_iv(bytea, bytea, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.decrypt_iv(bytea, bytea, bytea, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION digest(bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.digest(bytea, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION digest(text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.digest(text, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION encrypt(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.encrypt(bytea, bytea, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION encrypt_iv(bytea, bytea, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.encrypt_iv(bytea, bytea, bytea, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION gen_random_bytes(integer); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.gen_random_bytes(integer) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION gen_random_uuid(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.gen_random_uuid() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION gen_salt(text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.gen_salt(text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION gen_salt(text, integer); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.gen_salt(text, integer) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION grant_pg_cron_access(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

REVOKE ALL ON FUNCTION extensions.grant_pg_cron_access() FROM supabase_admin;
GRANT ALL ON FUNCTION extensions.grant_pg_cron_access() TO supabase_admin WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.grant_pg_cron_access() TO dashboard_user;


--
-- Name: FUNCTION grant_pg_graphql_access(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.grant_pg_graphql_access() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION grant_pg_net_access(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

REVOKE ALL ON FUNCTION extensions.grant_pg_net_access() FROM supabase_admin;
GRANT ALL ON FUNCTION extensions.grant_pg_net_access() TO supabase_admin WITH GRANT OPTION;
GRANT ALL ON FUNCTION extensions.grant_pg_net_access() TO dashboard_user;


--
-- Name: FUNCTION hmac(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.hmac(bytea, bytea, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION hmac(text, text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.hmac(text, text, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pg_stat_statements(showtext boolean, OUT userid oid, OUT dbid oid, OUT toplevel boolean, OUT queryid bigint, OUT query text, OUT plans bigint, OUT total_plan_time double precision, OUT min_plan_time double precision, OUT max_plan_time double precision, OUT mean_plan_time double precision, OUT stddev_plan_time double precision, OUT calls bigint, OUT total_exec_time double precision, OUT min_exec_time double precision, OUT max_exec_time double precision, OUT mean_exec_time double precision, OUT stddev_exec_time double precision, OUT rows bigint, OUT shared_blks_hit bigint, OUT shared_blks_read bigint, OUT shared_blks_dirtied bigint, OUT shared_blks_written bigint, OUT local_blks_hit bigint, OUT local_blks_read bigint, OUT local_blks_dirtied bigint, OUT local_blks_written bigint, OUT temp_blks_read bigint, OUT temp_blks_written bigint, OUT shared_blk_read_time double precision, OUT shared_blk_write_time double precision, OUT local_blk_read_time double precision, OUT local_blk_write_time double precision, OUT temp_blk_read_time double precision, OUT temp_blk_write_time double precision, OUT wal_records bigint, OUT wal_fpi bigint, OUT wal_bytes numeric, OUT jit_functions bigint, OUT jit_generation_time double precision, OUT jit_inlining_count bigint, OUT jit_inlining_time double precision, OUT jit_optimization_count bigint, OUT jit_optimization_time double precision, OUT jit_emission_count bigint, OUT jit_emission_time double precision, OUT jit_deform_count bigint, OUT jit_deform_time double precision, OUT stats_since timestamp with time zone, OUT minmax_stats_since timestamp with time zone); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pg_stat_statements(showtext boolean, OUT userid oid, OUT dbid oid, OUT toplevel boolean, OUT queryid bigint, OUT query text, OUT plans bigint, OUT total_plan_time double precision, OUT min_plan_time double precision, OUT max_plan_time double precision, OUT mean_plan_time double precision, OUT stddev_plan_time double precision, OUT calls bigint, OUT total_exec_time double precision, OUT min_exec_time double precision, OUT max_exec_time double precision, OUT mean_exec_time double precision, OUT stddev_exec_time double precision, OUT rows bigint, OUT shared_blks_hit bigint, OUT shared_blks_read bigint, OUT shared_blks_dirtied bigint, OUT shared_blks_written bigint, OUT local_blks_hit bigint, OUT local_blks_read bigint, OUT local_blks_dirtied bigint, OUT local_blks_written bigint, OUT temp_blks_read bigint, OUT temp_blks_written bigint, OUT shared_blk_read_time double precision, OUT shared_blk_write_time double precision, OUT local_blk_read_time double precision, OUT local_blk_write_time double precision, OUT temp_blk_read_time double precision, OUT temp_blk_write_time double precision, OUT wal_records bigint, OUT wal_fpi bigint, OUT wal_bytes numeric, OUT jit_functions bigint, OUT jit_generation_time double precision, OUT jit_inlining_count bigint, OUT jit_inlining_time double precision, OUT jit_optimization_count bigint, OUT jit_optimization_time double precision, OUT jit_emission_count bigint, OUT jit_emission_time double precision, OUT jit_deform_count bigint, OUT jit_deform_time double precision, OUT stats_since timestamp with time zone, OUT minmax_stats_since timestamp with time zone) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pg_stat_statements_info(OUT dealloc bigint, OUT stats_reset timestamp with time zone); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pg_stat_statements_info(OUT dealloc bigint, OUT stats_reset timestamp with time zone) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_armor_headers(text, OUT key text, OUT value text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_armor_headers(text, OUT key text, OUT value text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_key_id(bytea); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_key_id(bytea) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_pub_decrypt(bytea, bytea); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_pub_decrypt(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_pub_decrypt(bytea, bytea, text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt(bytea, bytea, text, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_pub_decrypt_bytea(bytea, bytea); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_pub_decrypt_bytea(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_pub_decrypt_bytea(bytea, bytea, text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_decrypt_bytea(bytea, bytea, text, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_pub_encrypt(text, bytea); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_pub_encrypt(text, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt(text, bytea, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_pub_encrypt_bytea(bytea, bytea); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_pub_encrypt_bytea(bytea, bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_pub_encrypt_bytea(bytea, bytea, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_sym_decrypt(bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_sym_decrypt(bytea, text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt(bytea, text, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_sym_decrypt_bytea(bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_sym_decrypt_bytea(bytea, text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_sym_decrypt_bytea(bytea, text, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_sym_encrypt(text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_sym_encrypt(text, text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt(text, text, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_sym_encrypt_bytea(bytea, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgp_sym_encrypt_bytea(bytea, text, text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgp_sym_encrypt_bytea(bytea, text, text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgrst_ddl_watch(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgrst_ddl_watch() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION pgrst_drop_watch(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.pgrst_drop_watch() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION set_graphql_placeholder(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.set_graphql_placeholder() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION uuid_generate_v1(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_generate_v1() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION uuid_generate_v1mc(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_generate_v1mc() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION uuid_generate_v3(namespace uuid, name text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_generate_v3(namespace uuid, name text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION uuid_generate_v4(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_generate_v4() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION uuid_generate_v5(namespace uuid, name text); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_generate_v5(namespace uuid, name text) TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION uuid_nil(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_nil() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION uuid_ns_dns(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_ns_dns() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION uuid_ns_oid(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_ns_oid() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION uuid_ns_url(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_ns_url() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION uuid_ns_x500(); Type: ACL; Schema: extensions; Owner: supabase_admin
--

GRANT ALL ON FUNCTION extensions.uuid_ns_x500() TO postgres WITH GRANT OPTION;


--
-- Name: FUNCTION graphql("operationName" text, query text, variables jsonb, extensions jsonb); Type: ACL; Schema: graphql_public; Owner: supabase_admin
--

GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO postgres;
GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO anon;
GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO authenticated;
GRANT ALL ON FUNCTION graphql_public.graphql("operationName" text, query text, variables jsonb, extensions jsonb) TO service_role;


--
-- Name: FUNCTION http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer); Type: ACL; Schema: net; Owner: supabase_admin
--

REVOKE ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;
GRANT ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin;
GRANT ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO postgres;
GRANT ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO anon;
GRANT ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO authenticated;
GRANT ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO service_role;


--
-- Name: FUNCTION http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer); Type: ACL; Schema: net; Owner: supabase_admin
--

REVOKE ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;
GRANT ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin;
GRANT ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO postgres;
GRANT ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO anon;
GRANT ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO authenticated;
GRANT ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO service_role;


--
-- Name: FUNCTION get_auth(p_usename text); Type: ACL; Schema: pgbouncer; Owner: supabase_admin
--

REVOKE ALL ON FUNCTION pgbouncer.get_auth(p_usename text) FROM PUBLIC;
GRANT ALL ON FUNCTION pgbouncer.get_auth(p_usename text) TO pgbouncer;
GRANT ALL ON FUNCTION pgbouncer.get_auth(p_usename text) TO postgres;


--
-- Name: FUNCTION _next_tank_code(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public._next_tank_code() TO anon;
GRANT ALL ON FUNCTION public._next_tank_code() TO authenticated;
GRANT ALL ON FUNCTION public._next_tank_code() TO service_role;


--
-- Name: FUNCTION _tank_code_year(y integer); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public._tank_code_year(y integer) TO anon;
GRANT ALL ON FUNCTION public._tank_code_year(y integer) TO authenticated;
GRANT ALL ON FUNCTION public._tank_code_year(y integer) TO service_role;


--
-- Name: FUNCTION assert_treatment_type(expected text, tid uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.assert_treatment_type(expected text, tid uuid) TO anon;
GRANT ALL ON FUNCTION public.assert_treatment_type(expected text, tid uuid) TO authenticated;
GRANT ALL ON FUNCTION public.assert_treatment_type(expected text, tid uuid) TO service_role;


--
-- Name: FUNCTION assert_unique_batch_key(p_treatment_id uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.assert_unique_batch_key(p_treatment_id uuid) TO anon;
GRANT ALL ON FUNCTION public.assert_unique_batch_key(p_treatment_id uuid) TO authenticated;
GRANT ALL ON FUNCTION public.assert_unique_batch_key(p_treatment_id uuid) TO service_role;


--
-- Name: FUNCTION assign_auto_fish_code(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.assign_auto_fish_code() TO anon;
GRANT ALL ON FUNCTION public.assign_auto_fish_code() TO authenticated;
GRANT ALL ON FUNCTION public.assign_auto_fish_code() TO service_role;


--
-- Name: FUNCTION assign_tank_label(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.assign_tank_label() TO anon;
GRANT ALL ON FUNCTION public.assign_tank_label() TO authenticated;
GRANT ALL ON FUNCTION public.assign_tank_label() TO service_role;


--
-- Name: FUNCTION assign_tank_on_insert(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.assign_tank_on_insert() TO anon;
GRANT ALL ON FUNCTION public.assign_tank_on_insert() TO authenticated;
GRANT ALL ON FUNCTION public.assign_tank_on_insert() TO service_role;


--
-- Name: FUNCTION auto_assign_tank(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.auto_assign_tank() TO anon;
GRANT ALL ON FUNCTION public.auto_assign_tank() TO authenticated;
GRANT ALL ON FUNCTION public.auto_assign_tank() TO service_role;


--
-- Name: FUNCTION base36_encode(n integer); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.base36_encode(n integer) TO anon;
GRANT ALL ON FUNCTION public.base36_encode(n integer) TO authenticated;
GRANT ALL ON FUNCTION public.base36_encode(n integer) TO service_role;


--
-- Name: FUNCTION detail_type_guard_v2(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.detail_type_guard_v2() TO anon;
GRANT ALL ON FUNCTION public.detail_type_guard_v2() TO authenticated;
GRANT ALL ON FUNCTION public.detail_type_guard_v2() TO service_role;


--
-- Name: FUNCTION dye_code_autofill(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.dye_code_autofill() TO anon;
GRANT ALL ON FUNCTION public.dye_code_autofill() TO authenticated;
GRANT ALL ON FUNCTION public.dye_code_autofill() TO service_role;


--
-- Name: FUNCTION fish_code_autofill(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.fish_code_autofill() TO anon;
GRANT ALL ON FUNCTION public.fish_code_autofill() TO authenticated;
GRANT ALL ON FUNCTION public.fish_code_autofill() TO service_role;


--
-- Name: FUNCTION gen_dye_code(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gen_dye_code() TO anon;
GRANT ALL ON FUNCTION public.gen_dye_code() TO authenticated;
GRANT ALL ON FUNCTION public.gen_dye_code() TO service_role;


--
-- Name: FUNCTION gen_fish_code(p_ts timestamp with time zone); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gen_fish_code(p_ts timestamp with time zone) TO anon;
GRANT ALL ON FUNCTION public.gen_fish_code(p_ts timestamp with time zone) TO authenticated;
GRANT ALL ON FUNCTION public.gen_fish_code(p_ts timestamp with time zone) TO service_role;


--
-- Name: FUNCTION gen_plasmid_code(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gen_plasmid_code() TO anon;
GRANT ALL ON FUNCTION public.gen_plasmid_code() TO authenticated;
GRANT ALL ON FUNCTION public.gen_plasmid_code() TO service_role;


--
-- Name: FUNCTION gen_rna_code(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gen_rna_code() TO anon;
GRANT ALL ON FUNCTION public.gen_rna_code() TO authenticated;
GRANT ALL ON FUNCTION public.gen_rna_code() TO service_role;


--
-- Name: FUNCTION gen_tank_code(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.gen_tank_code() TO anon;
GRANT ALL ON FUNCTION public.gen_tank_code() TO authenticated;
GRANT ALL ON FUNCTION public.gen_tank_code() TO service_role;


--
-- Name: FUNCTION make_auto_fish_code(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.make_auto_fish_code() TO anon;
GRANT ALL ON FUNCTION public.make_auto_fish_code() TO authenticated;
GRANT ALL ON FUNCTION public.make_auto_fish_code() TO service_role;


--
-- Name: FUNCTION next_auto_fish_code(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.next_auto_fish_code() TO anon;
GRANT ALL ON FUNCTION public.next_auto_fish_code() TO authenticated;
GRANT ALL ON FUNCTION public.next_auto_fish_code() TO service_role;


--
-- Name: FUNCTION next_tank_code(p_prefix text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.next_tank_code(p_prefix text) TO anon;
GRANT ALL ON FUNCTION public.next_tank_code(p_prefix text) TO authenticated;
GRANT ALL ON FUNCTION public.next_tank_code(p_prefix text) TO service_role;


--
-- Name: FUNCTION no_update_auto_fish_code(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.no_update_auto_fish_code() TO anon;
GRANT ALL ON FUNCTION public.no_update_auto_fish_code() TO authenticated;
GRANT ALL ON FUNCTION public.no_update_auto_fish_code() TO service_role;


--
-- Name: FUNCTION pg_raise(name text, msg text); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.pg_raise(name text, msg text) TO anon;
GRANT ALL ON FUNCTION public.pg_raise(name text, msg text) TO authenticated;
GRANT ALL ON FUNCTION public.pg_raise(name text, msg text) TO service_role;


--
-- Name: FUNCTION pg_raise(name text, msg text, tid uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.pg_raise(name text, msg text, tid uuid) TO anon;
GRANT ALL ON FUNCTION public.pg_raise(name text, msg text, tid uuid) TO authenticated;
GRANT ALL ON FUNCTION public.pg_raise(name text, msg text, tid uuid) TO service_role;


--
-- Name: FUNCTION plasmid_code_autofill(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.plasmid_code_autofill() TO anon;
GRANT ALL ON FUNCTION public.plasmid_code_autofill() TO authenticated;
GRANT ALL ON FUNCTION public.plasmid_code_autofill() TO service_role;


--
-- Name: FUNCTION rna_code_autofill(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.rna_code_autofill() TO anon;
GRANT ALL ON FUNCTION public.rna_code_autofill() TO authenticated;
GRANT ALL ON FUNCTION public.rna_code_autofill() TO service_role;


--
-- Name: FUNCTION set_updated_at(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.set_updated_at() TO anon;
GRANT ALL ON FUNCTION public.set_updated_at() TO authenticated;
GRANT ALL ON FUNCTION public.set_updated_at() TO service_role;


--
-- Name: FUNCTION tank_prefix_for_fish(p_fish uuid); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.tank_prefix_for_fish(p_fish uuid) TO anon;
GRANT ALL ON FUNCTION public.tank_prefix_for_fish(p_fish uuid) TO authenticated;
GRANT ALL ON FUNCTION public.tank_prefix_for_fish(p_fish uuid) TO service_role;


--
-- Name: FUNCTION treatment_batch_guard_v2(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.treatment_batch_guard_v2() TO anon;
GRANT ALL ON FUNCTION public.treatment_batch_guard_v2() TO authenticated;
GRANT ALL ON FUNCTION public.treatment_batch_guard_v2() TO service_role;


--
-- Name: FUNCTION treatment_detail_mirror(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.treatment_detail_mirror() TO anon;
GRANT ALL ON FUNCTION public.treatment_detail_mirror() TO authenticated;
GRANT ALL ON FUNCTION public.treatment_detail_mirror() TO service_role;


--
-- Name: FUNCTION trg_set_tank_code(); Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON FUNCTION public.trg_set_tank_code() TO anon;
GRANT ALL ON FUNCTION public.trg_set_tank_code() TO authenticated;
GRANT ALL ON FUNCTION public.trg_set_tank_code() TO service_role;


--
-- Name: FUNCTION apply_rls(wal jsonb, max_record_bytes integer); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO postgres;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO anon;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO authenticated;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO service_role;
GRANT ALL ON FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer) TO supabase_realtime_admin;


--
-- Name: FUNCTION broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text) TO postgres;
GRANT ALL ON FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text) TO dashboard_user;


--
-- Name: FUNCTION build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO postgres;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO anon;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO authenticated;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO service_role;
GRANT ALL ON FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) TO supabase_realtime_admin;


--
-- Name: FUNCTION "cast"(val text, type_ regtype); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO postgres;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO dashboard_user;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO anon;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO authenticated;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO service_role;
GRANT ALL ON FUNCTION realtime."cast"(val text, type_ regtype) TO supabase_realtime_admin;


--
-- Name: FUNCTION check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO postgres;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO anon;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO authenticated;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO service_role;
GRANT ALL ON FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) TO supabase_realtime_admin;


--
-- Name: FUNCTION is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO postgres;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO anon;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO authenticated;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO service_role;
GRANT ALL ON FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) TO supabase_realtime_admin;


--
-- Name: FUNCTION list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO postgres;
GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO anon;
GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO authenticated;
GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO service_role;
GRANT ALL ON FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) TO supabase_realtime_admin;


--
-- Name: FUNCTION quote_wal2json(entity regclass); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO postgres;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO anon;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO authenticated;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO service_role;
GRANT ALL ON FUNCTION realtime.quote_wal2json(entity regclass) TO supabase_realtime_admin;


--
-- Name: FUNCTION send(payload jsonb, event text, topic text, private boolean); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean) TO postgres;
GRANT ALL ON FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean) TO dashboard_user;


--
-- Name: FUNCTION subscription_check_filters(); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO postgres;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO dashboard_user;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO anon;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO authenticated;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO service_role;
GRANT ALL ON FUNCTION realtime.subscription_check_filters() TO supabase_realtime_admin;


--
-- Name: FUNCTION to_regrole(role_name text); Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO postgres;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO dashboard_user;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO anon;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO authenticated;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO service_role;
GRANT ALL ON FUNCTION realtime.to_regrole(role_name text) TO supabase_realtime_admin;


--
-- Name: FUNCTION topic(); Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON FUNCTION realtime.topic() TO postgres;
GRANT ALL ON FUNCTION realtime.topic() TO dashboard_user;


--
-- Name: FUNCTION http_request(); Type: ACL; Schema: supabase_functions; Owner: supabase_functions_admin
--

REVOKE ALL ON FUNCTION supabase_functions.http_request() FROM PUBLIC;
GRANT ALL ON FUNCTION supabase_functions.http_request() TO postgres;
GRANT ALL ON FUNCTION supabase_functions.http_request() TO anon;
GRANT ALL ON FUNCTION supabase_functions.http_request() TO authenticated;
GRANT ALL ON FUNCTION supabase_functions.http_request() TO service_role;


--
-- Name: FUNCTION _crypto_aead_det_decrypt(message bytea, additional bytea, key_id bigint, context bytea, nonce bytea); Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT ALL ON FUNCTION vault._crypto_aead_det_decrypt(message bytea, additional bytea, key_id bigint, context bytea, nonce bytea) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION vault._crypto_aead_det_decrypt(message bytea, additional bytea, key_id bigint, context bytea, nonce bytea) TO service_role;


--
-- Name: FUNCTION create_secret(new_secret text, new_name text, new_description text, new_key_id uuid); Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT ALL ON FUNCTION vault.create_secret(new_secret text, new_name text, new_description text, new_key_id uuid) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION vault.create_secret(new_secret text, new_name text, new_description text, new_key_id uuid) TO service_role;


--
-- Name: FUNCTION update_secret(secret_id uuid, new_secret text, new_name text, new_description text, new_key_id uuid); Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT ALL ON FUNCTION vault.update_secret(secret_id uuid, new_secret text, new_name text, new_description text, new_key_id uuid) TO postgres WITH GRANT OPTION;
GRANT ALL ON FUNCTION vault.update_secret(secret_id uuid, new_secret text, new_name text, new_description text, new_key_id uuid) TO service_role;


--
-- Name: TABLE audit_log_entries; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.audit_log_entries TO dashboard_user;
GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.audit_log_entries TO postgres;
GRANT SELECT ON TABLE auth.audit_log_entries TO postgres WITH GRANT OPTION;


--
-- Name: TABLE flow_state; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.flow_state TO postgres;
GRANT SELECT ON TABLE auth.flow_state TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.flow_state TO dashboard_user;


--
-- Name: TABLE identities; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.identities TO postgres;
GRANT SELECT ON TABLE auth.identities TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.identities TO dashboard_user;


--
-- Name: TABLE instances; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.instances TO dashboard_user;
GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.instances TO postgres;
GRANT SELECT ON TABLE auth.instances TO postgres WITH GRANT OPTION;


--
-- Name: TABLE mfa_amr_claims; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.mfa_amr_claims TO postgres;
GRANT SELECT ON TABLE auth.mfa_amr_claims TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.mfa_amr_claims TO dashboard_user;


--
-- Name: TABLE mfa_challenges; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.mfa_challenges TO postgres;
GRANT SELECT ON TABLE auth.mfa_challenges TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.mfa_challenges TO dashboard_user;


--
-- Name: TABLE mfa_factors; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.mfa_factors TO postgres;
GRANT SELECT ON TABLE auth.mfa_factors TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.mfa_factors TO dashboard_user;


--
-- Name: TABLE oauth_clients; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.oauth_clients TO postgres;
GRANT ALL ON TABLE auth.oauth_clients TO dashboard_user;


--
-- Name: TABLE one_time_tokens; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.one_time_tokens TO postgres;
GRANT SELECT ON TABLE auth.one_time_tokens TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.one_time_tokens TO dashboard_user;


--
-- Name: TABLE refresh_tokens; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.refresh_tokens TO dashboard_user;
GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.refresh_tokens TO postgres;
GRANT SELECT ON TABLE auth.refresh_tokens TO postgres WITH GRANT OPTION;


--
-- Name: SEQUENCE refresh_tokens_id_seq; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON SEQUENCE auth.refresh_tokens_id_seq TO dashboard_user;
GRANT ALL ON SEQUENCE auth.refresh_tokens_id_seq TO postgres;


--
-- Name: TABLE saml_providers; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.saml_providers TO postgres;
GRANT SELECT ON TABLE auth.saml_providers TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.saml_providers TO dashboard_user;


--
-- Name: TABLE saml_relay_states; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.saml_relay_states TO postgres;
GRANT SELECT ON TABLE auth.saml_relay_states TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.saml_relay_states TO dashboard_user;


--
-- Name: TABLE schema_migrations; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT SELECT ON TABLE auth.schema_migrations TO postgres WITH GRANT OPTION;


--
-- Name: TABLE sessions; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.sessions TO postgres;
GRANT SELECT ON TABLE auth.sessions TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.sessions TO dashboard_user;


--
-- Name: TABLE sso_domains; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.sso_domains TO postgres;
GRANT SELECT ON TABLE auth.sso_domains TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.sso_domains TO dashboard_user;


--
-- Name: TABLE sso_providers; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.sso_providers TO postgres;
GRANT SELECT ON TABLE auth.sso_providers TO postgres WITH GRANT OPTION;
GRANT ALL ON TABLE auth.sso_providers TO dashboard_user;


--
-- Name: TABLE users; Type: ACL; Schema: auth; Owner: supabase_auth_admin
--

GRANT ALL ON TABLE auth.users TO dashboard_user;
GRANT INSERT,REFERENCES,DELETE,TRIGGER,TRUNCATE,MAINTAIN,UPDATE ON TABLE auth.users TO postgres;
GRANT SELECT ON TABLE auth.users TO postgres WITH GRANT OPTION;


--
-- Name: TABLE _stag_fish_fix; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public._stag_fish_fix TO anon;
GRANT ALL ON TABLE public._stag_fish_fix TO authenticated;
GRANT ALL ON TABLE public._stag_fish_fix TO service_role;


--
-- Name: TABLE _stag_fish_tg_diag; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public._stag_fish_tg_diag TO anon;
GRANT ALL ON TABLE public._stag_fish_tg_diag TO authenticated;
GRANT ALL ON TABLE public._stag_fish_tg_diag TO service_role;


--
-- Name: TABLE _staging_fish_load; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public._staging_fish_load TO anon;
GRANT ALL ON TABLE public._staging_fish_load TO authenticated;
GRANT ALL ON TABLE public._staging_fish_load TO service_role;


--
-- Name: TABLE dye_counters; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.dye_counters TO anon;
GRANT ALL ON TABLE public.dye_counters TO authenticated;
GRANT ALL ON TABLE public.dye_counters TO service_role;


--
-- Name: TABLE dye_treatments; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.dye_treatments TO anon;
GRANT ALL ON TABLE public.dye_treatments TO authenticated;
GRANT ALL ON TABLE public.dye_treatments TO service_role;


--
-- Name: TABLE dyes; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.dyes TO anon;
GRANT ALL ON TABLE public.dyes TO authenticated;
GRANT ALL ON TABLE public.dyes TO service_role;


--
-- Name: TABLE fish; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.fish TO anon;
GRANT ALL ON TABLE public.fish TO authenticated;
GRANT ALL ON TABLE public.fish TO service_role;


--
-- Name: TABLE fish_code_counters; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.fish_code_counters TO anon;
GRANT ALL ON TABLE public.fish_code_counters TO authenticated;
GRANT ALL ON TABLE public.fish_code_counters TO service_role;


--
-- Name: SEQUENCE fish_code_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.fish_code_seq TO anon;
GRANT ALL ON SEQUENCE public.fish_code_seq TO authenticated;
GRANT ALL ON SEQUENCE public.fish_code_seq TO service_role;


--
-- Name: TABLE fish_tanks; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.fish_tanks TO anon;
GRANT ALL ON TABLE public.fish_tanks TO authenticated;
GRANT ALL ON TABLE public.fish_tanks TO service_role;


--
-- Name: TABLE fish_transgene_alleles; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.fish_transgene_alleles TO anon;
GRANT ALL ON TABLE public.fish_transgene_alleles TO authenticated;
GRANT ALL ON TABLE public.fish_transgene_alleles TO service_role;


--
-- Name: TABLE fish_transgenes; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.fish_transgenes TO anon;
GRANT ALL ON TABLE public.fish_transgenes TO authenticated;
GRANT ALL ON TABLE public.fish_transgenes TO service_role;


--
-- Name: TABLE fish_treatments; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.fish_treatments TO anon;
GRANT ALL ON TABLE public.fish_treatments TO authenticated;
GRANT ALL ON TABLE public.fish_treatments TO service_role;


--
-- Name: TABLE fish_year_counters; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.fish_year_counters TO anon;
GRANT ALL ON TABLE public.fish_year_counters TO authenticated;
GRANT ALL ON TABLE public.fish_year_counters TO service_role;


--
-- Name: TABLE genotypes; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.genotypes TO anon;
GRANT ALL ON TABLE public.genotypes TO authenticated;
GRANT ALL ON TABLE public.genotypes TO service_role;


--
-- Name: TABLE injected_plasmid_treatments; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.injected_plasmid_treatments TO anon;
GRANT ALL ON TABLE public.injected_plasmid_treatments TO authenticated;
GRANT ALL ON TABLE public.injected_plasmid_treatments TO service_role;


--
-- Name: TABLE injected_rna_treatments; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.injected_rna_treatments TO anon;
GRANT ALL ON TABLE public.injected_rna_treatments TO authenticated;
GRANT ALL ON TABLE public.injected_rna_treatments TO service_role;


--
-- Name: TABLE plasmid_counters; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.plasmid_counters TO anon;
GRANT ALL ON TABLE public.plasmid_counters TO authenticated;
GRANT ALL ON TABLE public.plasmid_counters TO service_role;


--
-- Name: TABLE plasmids; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.plasmids TO anon;
GRANT ALL ON TABLE public.plasmids TO authenticated;
GRANT ALL ON TABLE public.plasmids TO service_role;


--
-- Name: TABLE rna_counters; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.rna_counters TO anon;
GRANT ALL ON TABLE public.rna_counters TO authenticated;
GRANT ALL ON TABLE public.rna_counters TO service_role;


--
-- Name: TABLE rnas; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.rnas TO anon;
GRANT ALL ON TABLE public.rnas TO authenticated;
GRANT ALL ON TABLE public.rnas TO service_role;


--
-- Name: TABLE seed_fish_tmp; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.seed_fish_tmp TO anon;
GRANT ALL ON TABLE public.seed_fish_tmp TO authenticated;
GRANT ALL ON TABLE public.seed_fish_tmp TO service_role;


--
-- Name: TABLE seed_transgenes_tmp; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.seed_transgenes_tmp TO anon;
GRANT ALL ON TABLE public.seed_transgenes_tmp TO authenticated;
GRANT ALL ON TABLE public.seed_transgenes_tmp TO service_role;


--
-- Name: TABLE seed_treatment_dye_tmp; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.seed_treatment_dye_tmp TO anon;
GRANT ALL ON TABLE public.seed_treatment_dye_tmp TO authenticated;
GRANT ALL ON TABLE public.seed_treatment_dye_tmp TO service_role;


--
-- Name: TABLE seed_treatment_injected_plasmid_tmp; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.seed_treatment_injected_plasmid_tmp TO anon;
GRANT ALL ON TABLE public.seed_treatment_injected_plasmid_tmp TO authenticated;
GRANT ALL ON TABLE public.seed_treatment_injected_plasmid_tmp TO service_role;


--
-- Name: TABLE seed_treatment_injected_rna_tmp; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.seed_treatment_injected_rna_tmp TO anon;
GRANT ALL ON TABLE public.seed_treatment_injected_rna_tmp TO authenticated;
GRANT ALL ON TABLE public.seed_treatment_injected_rna_tmp TO service_role;


--
-- Name: SEQUENCE seq_tank_code; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.seq_tank_code TO anon;
GRANT ALL ON SEQUENCE public.seq_tank_code TO authenticated;
GRANT ALL ON SEQUENCE public.seq_tank_code TO service_role;


--
-- Name: TABLE staging_links_dye; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.staging_links_dye TO anon;
GRANT ALL ON TABLE public.staging_links_dye TO authenticated;
GRANT ALL ON TABLE public.staging_links_dye TO service_role;


--
-- Name: TABLE staging_links_dye_by_name; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.staging_links_dye_by_name TO anon;
GRANT ALL ON TABLE public.staging_links_dye_by_name TO authenticated;
GRANT ALL ON TABLE public.staging_links_dye_by_name TO service_role;


--
-- Name: TABLE staging_links_injected_plasmid; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.staging_links_injected_plasmid TO anon;
GRANT ALL ON TABLE public.staging_links_injected_plasmid TO authenticated;
GRANT ALL ON TABLE public.staging_links_injected_plasmid TO service_role;


--
-- Name: TABLE staging_links_injected_plasmid_by_name; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.staging_links_injected_plasmid_by_name TO anon;
GRANT ALL ON TABLE public.staging_links_injected_plasmid_by_name TO authenticated;
GRANT ALL ON TABLE public.staging_links_injected_plasmid_by_name TO service_role;


--
-- Name: TABLE staging_links_injected_rna; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.staging_links_injected_rna TO anon;
GRANT ALL ON TABLE public.staging_links_injected_rna TO authenticated;
GRANT ALL ON TABLE public.staging_links_injected_rna TO service_role;


--
-- Name: TABLE staging_links_injected_rna_by_name; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.staging_links_injected_rna_by_name TO anon;
GRANT ALL ON TABLE public.staging_links_injected_rna_by_name TO authenticated;
GRANT ALL ON TABLE public.staging_links_injected_rna_by_name TO service_role;


--
-- Name: TABLE stg_dye; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.stg_dye TO anon;
GRANT ALL ON TABLE public.stg_dye TO authenticated;
GRANT ALL ON TABLE public.stg_dye TO service_role;


--
-- Name: TABLE stg_inj_plasmid; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.stg_inj_plasmid TO anon;
GRANT ALL ON TABLE public.stg_inj_plasmid TO authenticated;
GRANT ALL ON TABLE public.stg_inj_plasmid TO service_role;


--
-- Name: TABLE stg_inj_rna; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.stg_inj_rna TO anon;
GRANT ALL ON TABLE public.stg_inj_rna TO authenticated;
GRANT ALL ON TABLE public.stg_inj_rna TO service_role;


--
-- Name: TABLE tank_assignments; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.tank_assignments TO anon;
GRANT ALL ON TABLE public.tank_assignments TO authenticated;
GRANT ALL ON TABLE public.tank_assignments TO service_role;


--
-- Name: TABLE tank_code_counters; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.tank_code_counters TO anon;
GRANT ALL ON TABLE public.tank_code_counters TO authenticated;
GRANT ALL ON TABLE public.tank_code_counters TO service_role;


--
-- Name: SEQUENCE tank_counters; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.tank_counters TO anon;
GRANT ALL ON SEQUENCE public.tank_counters TO authenticated;
GRANT ALL ON SEQUENCE public.tank_counters TO service_role;


--
-- Name: TABLE tanks; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.tanks TO anon;
GRANT ALL ON TABLE public.tanks TO authenticated;
GRANT ALL ON TABLE public.tanks TO service_role;


--
-- Name: SEQUENCE tanks_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.tanks_id_seq TO anon;
GRANT ALL ON SEQUENCE public.tanks_id_seq TO authenticated;
GRANT ALL ON SEQUENCE public.tanks_id_seq TO service_role;


--
-- Name: TABLE transgene_alleles; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.transgene_alleles TO anon;
GRANT ALL ON TABLE public.transgene_alleles TO authenticated;
GRANT ALL ON TABLE public.transgene_alleles TO service_role;


--
-- Name: TABLE transgenes; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.transgenes TO anon;
GRANT ALL ON TABLE public.transgenes TO authenticated;
GRANT ALL ON TABLE public.transgenes TO service_role;


--
-- Name: TABLE treatments; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.treatments TO anon;
GRANT ALL ON TABLE public.treatments TO authenticated;
GRANT ALL ON TABLE public.treatments TO service_role;


--
-- Name: TABLE v_dye_treatments; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.v_dye_treatments TO anon;
GRANT ALL ON TABLE public.v_dye_treatments TO authenticated;
GRANT ALL ON TABLE public.v_dye_treatments TO service_role;


--
-- Name: TABLE v_fish_links; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.v_fish_links TO anon;
GRANT ALL ON TABLE public.v_fish_links TO authenticated;
GRANT ALL ON TABLE public.v_fish_links TO service_role;


--
-- Name: TABLE v_plasmid_treatments; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.v_plasmid_treatments TO anon;
GRANT ALL ON TABLE public.v_plasmid_treatments TO authenticated;
GRANT ALL ON TABLE public.v_plasmid_treatments TO service_role;


--
-- Name: TABLE v_rna_treatments; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.v_rna_treatments TO anon;
GRANT ALL ON TABLE public.v_rna_treatments TO authenticated;
GRANT ALL ON TABLE public.v_rna_treatments TO service_role;


--
-- Name: TABLE v_treatments; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.v_treatments TO anon;
GRANT ALL ON TABLE public.v_treatments TO authenticated;
GRANT ALL ON TABLE public.v_treatments TO service_role;


--
-- Name: TABLE v_treatments_unified; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.v_treatments_unified TO anon;
GRANT ALL ON TABLE public.v_treatments_unified TO authenticated;
GRANT ALL ON TABLE public.v_treatments_unified TO service_role;


--
-- Name: TABLE v_treatments_dye; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.v_treatments_dye TO anon;
GRANT ALL ON TABLE public.v_treatments_dye TO authenticated;
GRANT ALL ON TABLE public.v_treatments_dye TO service_role;


--
-- Name: TABLE v_treatments_expanded; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.v_treatments_expanded TO anon;
GRANT ALL ON TABLE public.v_treatments_expanded TO authenticated;
GRANT ALL ON TABLE public.v_treatments_expanded TO service_role;


--
-- Name: TABLE v_treatments_join; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.v_treatments_join TO anon;
GRANT ALL ON TABLE public.v_treatments_join TO authenticated;
GRANT ALL ON TABLE public.v_treatments_join TO service_role;


--
-- Name: TABLE v_treatments_plasmid; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.v_treatments_plasmid TO anon;
GRANT ALL ON TABLE public.v_treatments_plasmid TO authenticated;
GRANT ALL ON TABLE public.v_treatments_plasmid TO service_role;


--
-- Name: TABLE v_treatments_rna; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.v_treatments_rna TO anon;
GRANT ALL ON TABLE public.v_treatments_rna TO authenticated;
GRANT ALL ON TABLE public.v_treatments_rna TO service_role;


--
-- Name: TABLE messages; Type: ACL; Schema: realtime; Owner: supabase_realtime_admin
--

GRANT ALL ON TABLE realtime.messages TO postgres;
GRANT ALL ON TABLE realtime.messages TO dashboard_user;
GRANT SELECT,INSERT,UPDATE ON TABLE realtime.messages TO anon;
GRANT SELECT,INSERT,UPDATE ON TABLE realtime.messages TO authenticated;
GRANT SELECT,INSERT,UPDATE ON TABLE realtime.messages TO service_role;


--
-- Name: TABLE messages_2025_09_21; Type: ACL; Schema: realtime; Owner: postgres
--

GRANT ALL ON TABLE realtime.messages_2025_09_21 TO dashboard_user;


--
-- Name: TABLE messages_2025_09_22; Type: ACL; Schema: realtime; Owner: postgres
--

GRANT ALL ON TABLE realtime.messages_2025_09_22 TO dashboard_user;


--
-- Name: TABLE messages_2025_09_23; Type: ACL; Schema: realtime; Owner: postgres
--

GRANT ALL ON TABLE realtime.messages_2025_09_23 TO dashboard_user;


--
-- Name: TABLE messages_2025_09_24; Type: ACL; Schema: realtime; Owner: postgres
--

GRANT ALL ON TABLE realtime.messages_2025_09_24 TO dashboard_user;


--
-- Name: TABLE messages_2025_09_25; Type: ACL; Schema: realtime; Owner: postgres
--

GRANT ALL ON TABLE realtime.messages_2025_09_25 TO dashboard_user;


--
-- Name: TABLE schema_migrations; Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON TABLE realtime.schema_migrations TO postgres;
GRANT ALL ON TABLE realtime.schema_migrations TO dashboard_user;
GRANT SELECT ON TABLE realtime.schema_migrations TO anon;
GRANT SELECT ON TABLE realtime.schema_migrations TO authenticated;
GRANT SELECT ON TABLE realtime.schema_migrations TO service_role;
GRANT ALL ON TABLE realtime.schema_migrations TO supabase_realtime_admin;


--
-- Name: TABLE subscription; Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON TABLE realtime.subscription TO postgres;
GRANT ALL ON TABLE realtime.subscription TO dashboard_user;
GRANT SELECT ON TABLE realtime.subscription TO anon;
GRANT SELECT ON TABLE realtime.subscription TO authenticated;
GRANT SELECT ON TABLE realtime.subscription TO service_role;
GRANT ALL ON TABLE realtime.subscription TO supabase_realtime_admin;


--
-- Name: SEQUENCE subscription_id_seq; Type: ACL; Schema: realtime; Owner: supabase_admin
--

GRANT ALL ON SEQUENCE realtime.subscription_id_seq TO postgres;
GRANT ALL ON SEQUENCE realtime.subscription_id_seq TO dashboard_user;
GRANT USAGE ON SEQUENCE realtime.subscription_id_seq TO anon;
GRANT USAGE ON SEQUENCE realtime.subscription_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE realtime.subscription_id_seq TO service_role;
GRANT ALL ON SEQUENCE realtime.subscription_id_seq TO supabase_realtime_admin;


--
-- Name: TABLE buckets; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.buckets TO anon;
GRANT ALL ON TABLE storage.buckets TO authenticated;
GRANT ALL ON TABLE storage.buckets TO service_role;
GRANT ALL ON TABLE storage.buckets TO postgres WITH GRANT OPTION;


--
-- Name: TABLE objects; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.objects TO anon;
GRANT ALL ON TABLE storage.objects TO authenticated;
GRANT ALL ON TABLE storage.objects TO service_role;
GRANT ALL ON TABLE storage.objects TO postgres WITH GRANT OPTION;


--
-- Name: TABLE s3_multipart_uploads; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.s3_multipart_uploads TO service_role;
GRANT SELECT ON TABLE storage.s3_multipart_uploads TO authenticated;
GRANT SELECT ON TABLE storage.s3_multipart_uploads TO anon;


--
-- Name: TABLE s3_multipart_uploads_parts; Type: ACL; Schema: storage; Owner: supabase_storage_admin
--

GRANT ALL ON TABLE storage.s3_multipart_uploads_parts TO service_role;
GRANT SELECT ON TABLE storage.s3_multipart_uploads_parts TO authenticated;
GRANT SELECT ON TABLE storage.s3_multipart_uploads_parts TO anon;


--
-- Name: TABLE hooks; Type: ACL; Schema: supabase_functions; Owner: supabase_functions_admin
--

GRANT ALL ON TABLE supabase_functions.hooks TO postgres;
GRANT ALL ON TABLE supabase_functions.hooks TO anon;
GRANT ALL ON TABLE supabase_functions.hooks TO authenticated;
GRANT ALL ON TABLE supabase_functions.hooks TO service_role;


--
-- Name: SEQUENCE hooks_id_seq; Type: ACL; Schema: supabase_functions; Owner: supabase_functions_admin
--

GRANT ALL ON SEQUENCE supabase_functions.hooks_id_seq TO postgres;
GRANT ALL ON SEQUENCE supabase_functions.hooks_id_seq TO anon;
GRANT ALL ON SEQUENCE supabase_functions.hooks_id_seq TO authenticated;
GRANT ALL ON SEQUENCE supabase_functions.hooks_id_seq TO service_role;


--
-- Name: TABLE migrations; Type: ACL; Schema: supabase_functions; Owner: supabase_functions_admin
--

GRANT ALL ON TABLE supabase_functions.migrations TO postgres;
GRANT ALL ON TABLE supabase_functions.migrations TO anon;
GRANT ALL ON TABLE supabase_functions.migrations TO authenticated;
GRANT ALL ON TABLE supabase_functions.migrations TO service_role;


--
-- Name: TABLE secrets; Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT SELECT,REFERENCES,DELETE,TRUNCATE ON TABLE vault.secrets TO postgres WITH GRANT OPTION;
GRANT SELECT,DELETE ON TABLE vault.secrets TO service_role;


--
-- Name: TABLE decrypted_secrets; Type: ACL; Schema: vault; Owner: supabase_admin
--

GRANT SELECT,REFERENCES,DELETE,TRUNCATE ON TABLE vault.decrypted_secrets TO postgres WITH GRANT OPTION;
GRANT SELECT,DELETE ON TABLE vault.decrypted_secrets TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: auth; Owner: supabase_auth_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON SEQUENCES TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: auth; Owner: supabase_auth_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON FUNCTIONS TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: auth; Owner: supabase_auth_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth GRANT ALL ON TABLES TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: extensions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA extensions GRANT ALL ON SEQUENCES TO postgres WITH GRANT OPTION;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: extensions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA extensions GRANT ALL ON FUNCTIONS TO postgres WITH GRANT OPTION;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: extensions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA extensions GRANT ALL ON TABLES TO postgres WITH GRANT OPTION;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: graphql; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: graphql; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: graphql; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: graphql_public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: graphql_public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: graphql_public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA graphql_public GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA public GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: realtime; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON SEQUENCES TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: realtime; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON FUNCTIONS TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: realtime; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA realtime GRANT ALL ON TABLES TO dashboard_user;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: storage; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: storage; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: storage; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA storage GRANT ALL ON TABLES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: supabase_functions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON SEQUENCES TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: supabase_functions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON FUNCTIONS TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON FUNCTIONS TO service_role;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: supabase_functions; Owner: supabase_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA supabase_functions GRANT ALL ON TABLES TO service_role;


--
-- Name: issue_graphql_placeholder; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER issue_graphql_placeholder ON sql_drop
         WHEN TAG IN ('DROP EXTENSION')
   EXECUTE FUNCTION extensions.set_graphql_placeholder();


ALTER EVENT TRIGGER issue_graphql_placeholder OWNER TO supabase_admin;

--
-- Name: issue_pg_cron_access; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER issue_pg_cron_access ON ddl_command_end
         WHEN TAG IN ('CREATE EXTENSION')
   EXECUTE FUNCTION extensions.grant_pg_cron_access();


ALTER EVENT TRIGGER issue_pg_cron_access OWNER TO supabase_admin;

--
-- Name: issue_pg_graphql_access; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER issue_pg_graphql_access ON ddl_command_end
         WHEN TAG IN ('CREATE FUNCTION')
   EXECUTE FUNCTION extensions.grant_pg_graphql_access();


ALTER EVENT TRIGGER issue_pg_graphql_access OWNER TO supabase_admin;

--
-- Name: issue_pg_net_access; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER issue_pg_net_access ON ddl_command_end
         WHEN TAG IN ('CREATE EXTENSION')
   EXECUTE FUNCTION extensions.grant_pg_net_access();


ALTER EVENT TRIGGER issue_pg_net_access OWNER TO supabase_admin;

--
-- Name: pgrst_ddl_watch; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER pgrst_ddl_watch ON ddl_command_end
   EXECUTE FUNCTION extensions.pgrst_ddl_watch();


ALTER EVENT TRIGGER pgrst_ddl_watch OWNER TO supabase_admin;

--
-- Name: pgrst_drop_watch; Type: EVENT TRIGGER; Schema: -; Owner: supabase_admin
--

CREATE EVENT TRIGGER pgrst_drop_watch ON sql_drop
   EXECUTE FUNCTION extensions.pgrst_drop_watch();


ALTER EVENT TRIGGER pgrst_drop_watch OWNER TO supabase_admin;

--
-- PostgreSQL database dump complete
--

\unrestrict KJxVpFJ92EqOWvEgZT7RoNEB9bJJzoRaMnJoHjQGe2wATCiYg9Dwowhs14ihGxx

