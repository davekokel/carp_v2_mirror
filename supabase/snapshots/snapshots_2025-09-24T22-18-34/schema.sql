--
-- PostgreSQL database dump
--

\restrict 3igHr9aAfJ7EeVLfFlsmIfswxHuZ98tZ48Jo5oao5LIifMdJU8AsSpmmGvqecSc

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
-- Name: _realtime; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA _realtime;


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
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


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
-- Name: oauth_registration_type; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.oauth_registration_type AS ENUM (
    'dynamic',
    'manual'
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
-- Name: tank_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.tank_status AS ENUM (
    'inactive',
    'alive',
    'to_kill',
    'dead'
);


--
-- Name: treatment_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.treatment_type_enum AS ENUM (
    'injected_plasmid',
    'injected_rna',
    'dye'
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
-- Name: _next_tank_code(); Type: FUNCTION; Schema: public; Owner: -
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


--
-- Name: _tank_code_year(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public._tank_code_year(y integer) RETURNS text
    LANGUAGE sql IMMUTABLE
    AS $$ select lpad((y % 100)::text, 2, '0') $$;


--
-- Name: assert_treatment_type(text, uuid); Type: FUNCTION; Schema: public; Owner: -
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


--
-- Name: assert_unique_batch_key(uuid); Type: FUNCTION; Schema: public; Owner: -
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


--
-- Name: detail_type_guard_v2(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.detail_type_guard_v2() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  ttype text;
  n int := 0;
BEGIN
  -- Verify treatment type matches the detail table
  SELECT treatment_type INTO ttype
  FROM public.treatments
  WHERE id = NEW.treatment_id;

  IF ttype IS NULL THEN
    RAISE EXCEPTION 'No treatments.id = % found for detail row', NEW.treatment_id;
  END IF;

  IF TG_TABLE_NAME = 'injected_plasmid_treatments' AND ttype <> 'injected_plasmid' THEN
    RAISE EXCEPTION 'treatment % has type %, expected injected_plasmid', NEW.treatment_id, ttype;
  ELSIF TG_TABLE_NAME = 'injected_rna_treatments' AND ttype <> 'injected_rna' THEN
    RAISE EXCEPTION 'treatment % has type %, expected injected_rna', NEW.treatment_id, ttype;
  ELSIF TG_TABLE_NAME = 'dye_treatments' AND ttype <> 'dye' THEN
    RAISE EXCEPTION 'treatment % has type %, expected dye', NEW.treatment_id, ttype;
  END IF;

  -- Count existing detail rows across all three tables, excluding self on UPDATE
  n :=
    (SELECT COUNT(*) FROM public.injected_plasmid_treatments
      WHERE treatment_id = NEW.treatment_id
        AND NOT (TG_TABLE_NAME='injected_plasmid_treatments' AND TG_OP='UPDATE' AND id = NEW.id))
  + (SELECT COUNT(*) FROM public.injected_rna_treatments
      WHERE treatment_id = NEW.treatment_id
        AND NOT (TG_TABLE_NAME='injected_rna_treatments' AND TG_OP='UPDATE' AND id = NEW.id))
  + (SELECT COUNT(*) FROM public.dye_treatments
      WHERE treatment_id = NEW.treatment_id
        AND NOT (TG_TABLE_NAME='dye_treatments' AND TG_OP='UPDATE' AND id = NEW.id));

  IF TG_OP = 'INSERT' AND n > 0 THEN
    RAISE EXCEPTION 'treatment % already has a detail row in another table', NEW.treatment_id;
  ELSIF TG_OP = 'UPDATE' AND n > 1 THEN
    RAISE EXCEPTION 'treatment % already has a detail row in another table', NEW.treatment_id;
  END IF;

  RETURN NEW;
END;
$$;


--
-- Name: dye_code_autofill(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.dye_code_autofill() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin if new.dye_code is null or btrim(new.dye_code)='' then new.dye_code:=public.gen_dye_code(); end if; return new; end $$;


--
-- Name: fish_code_autofill(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fish_code_autofill() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin if new.fish_code is null or btrim(new.fish_code)='' then new.fish_code := public.gen_fish_code(coalesce(new.created_at, now())); end if; return new; end $$;


--
-- Name: gen_dye_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_dye_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
declare k int;
begin update public.dye_counters set n=n+1 returning n into k; return format('DYE-%04s', k); end $$;


--
-- Name: gen_fish_code(timestamp with time zone); Type: FUNCTION; Schema: public; Owner: -
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


--
-- Name: gen_plasmid_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_plasmid_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
declare k int;
begin update public.plasmid_counters set n=n+1 returning n into k;
return format('PLM-%04s', k);
end $$;


--
-- Name: gen_rna_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_rna_code() RETURNS text
    LANGUAGE plpgsql
    AS $$
declare k int;
begin update public.rna_counters set n=n+1 returning n into k; return format('RNA-%04s', k); end $$;


--
-- Name: gen_tank_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.gen_tank_code() RETURNS text
    LANGUAGE sql
    AS $$
          select 'TANK-' || to_char(now(),'YYYY') || '-' ||
                 lpad(nextval('public.tank_counters')::text, 4, '0');
        $$;


--
-- Name: next_auto_fish_code(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.next_auto_fish_code() RETURNS text
    LANGUAGE sql
    AS $$
  SELECT 'FSH-' || to_char(now(), 'YYYY') || '-' ||
         to_char(nextval('public.auto_fish_seq'), 'FM000');
$$;


--
-- Name: next_tank_code(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.next_tank_code(prefix text) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
  n bigint;
BEGIN
  n := nextval('public.tank_label_seq');
  RETURN prefix || to_char(n, 'FM000');
END
$$;


--
-- Name: pg_raise(text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.pg_raise(name text, msg text) RETURNS void
    LANGUAGE plpgsql
    AS $$
begin
  raise exception using errcode = 'P0001', message = msg, constraint = name;
end $$;


--
-- Name: pg_raise(text, text, uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.pg_raise(name text, msg text, tid uuid) RETURNS void
    LANGUAGE plpgsql
    AS $$
begin
  raise exception using errcode = 'P0001', message = msg || ' ('||tid||')', constraint = name;
end $$;


--
-- Name: plasmid_code_autofill(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.plasmid_code_autofill() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin if new.plasmid_code is null or btrim(new.plasmid_code)='' then new.plasmid_code := public.gen_plasmid_code(); end if; return new; end $$;


--
-- Name: rna_code_autofill(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.rna_code_autofill() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin if new.rna_code is null or btrim(new.rna_code)='' then new.rna_code:=public.gen_rna_code(); end if; return new; end $$;


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
begin new.updated_at=now(); return new; end $$;


--
-- Name: treatment_batch_guard_v2(); Type: FUNCTION; Schema: public; Owner: -
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


--
-- Name: trg_set_tank_code(); Type: FUNCTION; Schema: public; Owner: -
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
-- Name: extension(text); Type: FUNCTION; Schema: storage; Owner: -
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
    LANGUAGE plpgsql
    AS $$
DECLARE
_parts text[];
BEGIN
	select string_to_array(name, '/') into _parts;
	return _parts[1:array_length(_parts,1)-1];
END
$$;


--
-- Name: get_size_by_bucket(); Type: FUNCTION; Schema: storage; Owner: -
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
-- Name: search(text, text, integer, integer, integer, text, text, text); Type: FUNCTION; Schema: storage; Owner: -
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


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: extensions; Type: TABLE; Schema: _realtime; Owner: -
--

CREATE TABLE _realtime.extensions (
    id uuid NOT NULL,
    type text,
    settings jsonb,
    tenant_external_id text,
    inserted_at timestamp(0) without time zone NOT NULL,
    updated_at timestamp(0) without time zone NOT NULL
);


--
-- Name: schema_migrations; Type: TABLE; Schema: _realtime; Owner: -
--

CREATE TABLE _realtime.schema_migrations (
    version bigint NOT NULL,
    inserted_at timestamp(0) without time zone
);


--
-- Name: tenants; Type: TABLE; Schema: _realtime; Owner: -
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
-- Name: oauth_clients; Type: TABLE; Schema: auth; Owner: -
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
    tag text
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
-- Name: _stag_dye; Type: TABLE; Schema: public; Owner: -
--

CREATE UNLOGGED TABLE public._stag_dye (
    fish_name text,
    treatment_date date,
    material_code text,
    treatment_type text,
    operator text,
    notes text
);


--
-- Name: _stag_plasmid; Type: TABLE; Schema: public; Owner: -
--

CREATE UNLOGGED TABLE public._stag_plasmid (
    fish_name text,
    treatment_date date,
    material_code text,
    treatment_type text,
    operator text,
    notes text
);


--
-- Name: _stag_rna; Type: TABLE; Schema: public; Owner: -
--

CREATE UNLOGGED TABLE public._stag_rna (
    fish_name text,
    treatment_date date,
    material_code text,
    treatment_type text,
    operator text,
    notes text
);


--
-- Name: _staging_fish_load; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public._staging_fish_load (
    fish_name text NOT NULL,
    date_birth date,
    n_new_tanks integer DEFAULT 0 NOT NULL
);


--
-- Name: _tmp_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public._tmp_links (
    fish_code text,
    transgene_base_code text,
    allele_number text,
    zygosity text
);


--
-- Name: auto_fish_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auto_fish_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dye_counters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dye_counters (
    n integer DEFAULT 0 NOT NULL
);


--
-- Name: dye_treatments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dye_treatments (
    amount numeric,
    units text,
    route text,
    id uuid DEFAULT gen_random_uuid(),
    treatment_id uuid NOT NULL,
    dye_id uuid NOT NULL
);


--
-- Name: dyes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dyes (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    dye_code text,
    name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text
);


--
-- Name: fish; Type: TABLE; Schema: public; Owner: -
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
    auto_fish_code text,
    batch_label text,
    line_building_stage text,
    nickname text,
    description text,
    strain text,
    date_of_birth date,
    CONSTRAINT chk_auto_fish_code_format CHECK (((auto_fish_code IS NULL) OR (auto_fish_code ~ '^FSH-\d{4}-\d{3}$'::text)))
);


--
-- Name: fish_tanks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish_tanks (
    fish_name text NOT NULL,
    linked_at timestamp with time zone DEFAULT now() NOT NULL,
    fish_id uuid,
    tank_id uuid
);


--
-- Name: fish_transgene_alleles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish_transgene_alleles (
    fish_id uuid NOT NULL,
    transgene_base_code text NOT NULL,
    allele_number text NOT NULL,
    zygosity text
);


--
-- Name: fish_transgenes; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.fish_transgenes AS
 SELECT DISTINCT fish_id,
    transgene_base_code AS transgene_code
   FROM public.fish_transgene_alleles fta;


--
-- Name: fish_treatments; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: fish_year_counters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fish_year_counters (
    year integer NOT NULL,
    n integer DEFAULT 0 NOT NULL
);


--
-- Name: genotypes; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: injected_plasmid_treatments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.injected_plasmid_treatments (
    concentration_ng_per_ul numeric,
    volume_nl numeric,
    injection_stage text,
    vehicle text,
    enzyme text,
    id uuid DEFAULT gen_random_uuid(),
    treatment_id uuid NOT NULL,
    plasmid_id uuid NOT NULL
);


--
-- Name: injected_rna_treatments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.injected_rna_treatments (
    concentration_ng_per_ul numeric,
    volume_nl numeric,
    injection_stage text,
    vehicle text,
    id uuid DEFAULT gen_random_uuid(),
    treatment_id uuid NOT NULL,
    rna_id uuid NOT NULL
);


--
-- Name: plasmid_counters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plasmid_counters (
    n integer DEFAULT 0 NOT NULL
);


--
-- Name: plasmids; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plasmids (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    plasmid_code text,
    name text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text
);


--
-- Name: rna_counters; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rna_counters (
    n integer DEFAULT 0 NOT NULL
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
-- Name: seed_fish_tmp; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: seed_transgenes_tmp; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.seed_transgenes_tmp (
    fish_name text,
    transgene_name text,
    allele_name text,
    zygosity text,
    new_allele_note double precision,
    seed_batch_id text
);


--
-- Name: seed_treatment_dye_tmp; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: seed_treatment_injected_plasmid_tmp; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: seed_treatment_injected_rna_tmp; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: seq_tank_code; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.seq_tank_code
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: staging_links_dye; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: staging_links_dye_by_name; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: staging_links_injected_plasmid; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: staging_links_injected_plasmid_by_name; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: staging_links_injected_rna; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: staging_links_injected_rna_by_name; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: stg_dye; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stg_dye (
    fish_name text,
    dye_name text,
    operator text,
    performed_at timestamp with time zone,
    notes text,
    source text
);


--
-- Name: stg_inj_plasmid; Type: TABLE; Schema: public; Owner: -
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


--
-- Name: stg_inj_rna; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stg_inj_rna (
    fish_name text,
    rna_name text,
    operator text,
    performed_at timestamp with time zone,
    notes text,
    source text
);


--
-- Name: tank_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tank_assignments (
    fish_id uuid NOT NULL,
    tank_label text NOT NULL,
    status public.tank_status DEFAULT 'inactive'::public.tank_status NOT NULL
);


--
-- Name: tank_counters; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tank_counters
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tank_label_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tank_label_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tanks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tanks (
    id bigint NOT NULL,
    tank_code text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    id_uuid uuid
);


--
-- Name: tanks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tanks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tanks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tanks_id_seq OWNED BY public.tanks.id;


--
-- Name: transgene_allele_catalog; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transgene_allele_catalog (
    transgene_base_code text NOT NULL,
    allele_number text NOT NULL,
    allele_name text,
    description text
);


--
-- Name: transgene_alleles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transgene_alleles (
    transgene_base_code text NOT NULL,
    allele_number text NOT NULL,
    description text
);


--
-- Name: transgenes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transgenes (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    allele_num text,
    transgene_base_code text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    name text
);


--
-- Name: treatments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.treatments (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    treatment_type public.treatment_type_enum NOT NULL,
    batch_id text,
    performed_at timestamp with time zone,
    operator text,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text,
    batch_label text,
    performed_on_date date GENERATED ALWAYS AS (((performed_at AT TIME ZONE 'America/Los_Angeles'::text))::date) STORED,
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code text
);


--
-- Name: v_dye_treatments; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_dye_treatments AS
 SELECT ft.fish_id,
    dt.treatment_id,
    d.name AS dye_name
   FROM ((public.fish_treatments ft
     JOIN public.dye_treatments dt ON ((dt.treatment_id = ft.treatment_id)))
     JOIN public.dyes d ON ((d.id_uuid = dt.dye_id)));


--
-- Name: v_fish_overview_v1; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_fish_overview_v1 AS
 WITH tg AS (
         SELECT fta.fish_id,
            string_agg(DISTINCT t.transgene_base_code, ', '::text ORDER BY t.transgene_base_code) AS transgenes
           FROM (public.fish_transgene_alleles fta
             JOIN public.transgenes t ON ((t.transgene_base_code = fta.transgene_base_code)))
          GROUP BY fta.fish_id
        ), alle AS (
         SELECT x.fish_id,
            string_agg(DISTINCT x.allele_label, ', '::text ORDER BY x.allele_label) AS alleles
           FROM ( SELECT fta.fish_id,
                    TRIM(BOTH FROM concat(fta.transgene_base_code,
                        CASE
                            WHEN (NULLIF(fta.allele_number, ''::text) IS NOT NULL) THEN (('('::text || fta.allele_number) || ')'::text)
                            ELSE ''::text
                        END)) AS allele_label
                   FROM public.fish_transgene_alleles fta) x
          GROUP BY x.fish_id
        ), tx AS (
         SELECT ft.fish_id,
            count(DISTINCT ft.treatment_id) AS n_treatments,
            (max(t.performed_at))::date AS last_treatment_on
           FROM (public.fish_treatments ft
             JOIN public.treatments t ON ((t.id = ft.treatment_id)))
          GROUP BY ft.fish_id
        )
 SELECT f.id,
    f.name AS fish_name,
    f.auto_fish_code,
    f.batch_label AS batch,
    f.line_building_stage,
    f.nickname,
    f.date_of_birth,
    f.description,
    COALESCE(tg.transgenes, ''::text) AS transgenes,
    COALESCE(alle.alleles, ''::text) AS alleles,
    COALESCE(tx.n_treatments, (0)::bigint) AS n_treatments,
    tx.last_treatment_on
   FROM (((public.fish f
     LEFT JOIN tg ON ((tg.fish_id = f.id)))
     LEFT JOIN alle ON ((alle.fish_id = f.id)))
     LEFT JOIN tx ON ((tx.fish_id = f.id)));


--
-- Name: v_plasmid_treatments; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_plasmid_treatments AS
 SELECT ft.fish_id,
    ipt.treatment_id,
    p.name AS plasmid_name
   FROM ((public.fish_treatments ft
     JOIN public.injected_plasmid_treatments ipt ON ((ipt.treatment_id = ft.treatment_id)))
     JOIN public.plasmids p ON ((p.id_uuid = ipt.plasmid_id)));


--
-- Name: v_rna_treatments; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_rna_treatments AS
 SELECT ft.fish_id,
    irt.treatment_id,
    r.name AS rna_name
   FROM ((public.fish_treatments ft
     JOIN public.injected_rna_treatments irt ON ((irt.treatment_id = ft.treatment_id)))
     JOIN public.rnas r ON ((r.id_uuid = irt.rna_id)));


--
-- Name: v_treatments_with_code; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.v_treatments_with_code AS
 SELECT id_uuid,
    treatment_type,
    batch_id,
    performed_at,
    operator,
    notes,
    created_at,
    created_by,
    batch_label,
    performed_on_date,
    id,
    COALESCE((to_jsonb(t.*) ->> 'plasmid_code'::text), (to_jsonb(t.*) ->> 'rna_code'::text), (to_jsonb(t.*) ->> 'dye_code'::text), (to_jsonb(t.*) ->> 'material_code'::text), (to_jsonb(t.*) ->> 'code'::text)) AS code_like
   FROM public.treatments t;


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
    owner_id text
);


--
-- Name: COLUMN buckets.owner; Type: COMMENT; Schema: storage; Owner: -
--

COMMENT ON COLUMN storage.buckets.owner IS 'Field is deprecated, use owner_id instead';


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
    user_metadata jsonb
);


--
-- Name: COLUMN objects.owner; Type: COMMENT; Schema: storage; Owner: -
--

COMMENT ON COLUMN storage.objects.owner IS 'Field is deprecated, use owner_id instead';


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
-- Name: refresh_tokens id; Type: DEFAULT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.refresh_tokens ALTER COLUMN id SET DEFAULT nextval('auth.refresh_tokens_id_seq'::regclass);


--
-- Name: tanks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tanks ALTER COLUMN id SET DEFAULT nextval('public.tanks_id_seq'::regclass);


--
-- Name: hooks id; Type: DEFAULT; Schema: supabase_functions; Owner: -
--

ALTER TABLE ONLY supabase_functions.hooks ALTER COLUMN id SET DEFAULT nextval('supabase_functions.hooks_id_seq'::regclass);


--
-- Name: extensions extensions_pkey; Type: CONSTRAINT; Schema: _realtime; Owner: -
--

ALTER TABLE ONLY _realtime.extensions
    ADD CONSTRAINT extensions_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: _realtime; Owner: -
--

ALTER TABLE ONLY _realtime.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: _realtime; Owner: -
--

ALTER TABLE ONLY _realtime.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


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
-- Name: oauth_clients oauth_clients_client_id_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_clients
    ADD CONSTRAINT oauth_clients_client_id_key UNIQUE (client_id);


--
-- Name: oauth_clients oauth_clients_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.oauth_clients
    ADD CONSTRAINT oauth_clients_pkey PRIMARY KEY (id);


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
-- Name: dyes dyes_dye_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dyes
    ADD CONSTRAINT dyes_dye_code_key UNIQUE (dye_code);


--
-- Name: dyes dyes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dyes
    ADD CONSTRAINT dyes_pkey PRIMARY KEY (id_uuid);


--
-- Name: fish fish_fish_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT fish_fish_code_key UNIQUE (fish_code);


--
-- Name: fish fish_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT fish_name_key UNIQUE (name);


--
-- Name: fish fish_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT fish_pkey PRIMARY KEY (id_uuid);


--
-- Name: fish_transgene_alleles fish_transgene_alleles_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_transgene_alleles
    ADD CONSTRAINT fish_transgene_alleles_pk PRIMARY KEY (fish_id, transgene_base_code, allele_number);


--
-- Name: fish_treatments fish_treatments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_treatments
    ADD CONSTRAINT fish_treatments_pkey PRIMARY KEY (id_uuid);


--
-- Name: fish_year_counters fish_year_counters_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_year_counters
    ADD CONSTRAINT fish_year_counters_pkey PRIMARY KEY (year);


--
-- Name: genotypes genotypes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.genotypes
    ADD CONSTRAINT genotypes_pkey PRIMARY KEY (id_uuid);


--
-- Name: plasmids plasmids_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plasmids
    ADD CONSTRAINT plasmids_pkey PRIMARY KEY (id_uuid);


--
-- Name: plasmids plasmids_plasmid_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plasmids
    ADD CONSTRAINT plasmids_plasmid_code_key UNIQUE (plasmid_code);


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
-- Name: tank_assignments tank_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_assignments
    ADD CONSTRAINT tank_assignments_pkey PRIMARY KEY (fish_id);


--
-- Name: tanks tanks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tanks
    ADD CONSTRAINT tanks_pkey PRIMARY KEY (id);


--
-- Name: tanks tanks_tank_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tanks
    ADD CONSTRAINT tanks_tank_code_key UNIQUE (tank_code);


--
-- Name: transgene_allele_catalog transgene_allele_catalog_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgene_allele_catalog
    ADD CONSTRAINT transgene_allele_catalog_pkey PRIMARY KEY (transgene_base_code, allele_number);


--
-- Name: transgene_alleles transgene_alleles_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgene_alleles
    ADD CONSTRAINT transgene_alleles_pk PRIMARY KEY (transgene_base_code, allele_number);


--
-- Name: transgenes transgenes_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgenes
    ADD CONSTRAINT transgenes_name_key UNIQUE (transgene_base_code);


--
-- Name: transgenes transgenes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgenes
    ADD CONSTRAINT transgenes_pkey PRIMARY KEY (id_uuid);


--
-- Name: treatments treatments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.treatments
    ADD CONSTRAINT treatments_pkey PRIMARY KEY (id_uuid);


--
-- Name: dye_treatments uq_dt_treatment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dye_treatments
    ADD CONSTRAINT uq_dt_treatment UNIQUE (treatment_id);


--
-- Name: injected_plasmid_treatments uq_ipt_treatment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.injected_plasmid_treatments
    ADD CONSTRAINT uq_ipt_treatment UNIQUE (treatment_id);


--
-- Name: injected_rna_treatments uq_irt_treatment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.injected_rna_treatments
    ADD CONSTRAINT uq_irt_treatment UNIQUE (treatment_id);


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
-- Name: extensions_tenant_external_id_index; Type: INDEX; Schema: _realtime; Owner: -
--

CREATE INDEX extensions_tenant_external_id_index ON _realtime.extensions USING btree (tenant_external_id);


--
-- Name: extensions_tenant_external_id_type_index; Type: INDEX; Schema: _realtime; Owner: -
--

CREATE UNIQUE INDEX extensions_tenant_external_id_type_index ON _realtime.extensions USING btree (tenant_external_id, type);


--
-- Name: tenants_external_id_index; Type: INDEX; Schema: _realtime; Owner: -
--

CREATE UNIQUE INDEX tenants_external_id_index ON _realtime.tenants USING btree (external_id);


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
-- Name: oauth_clients_client_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX oauth_clients_client_id_idx ON auth.oauth_clients USING btree (client_id);


--
-- Name: oauth_clients_deleted_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX oauth_clients_deleted_at_idx ON auth.oauth_clients USING btree (deleted_at);


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
-- Name: idx_fish_name_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_fish_name_unique ON public.fish USING btree (name);


--
-- Name: ix_dye_treatments_dye; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_dye_treatments_dye ON public.dye_treatments USING btree (dye_id);


--
-- Name: ix_fish_description_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fish_description_trgm ON public.fish USING gin (description public.gin_trgm_ops);


--
-- Name: ix_fish_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fish_name ON public.fish USING btree (name);


--
-- Name: ix_fish_name_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fish_name_trgm ON public.fish USING gin (name public.gin_trgm_ops);


--
-- Name: ix_fish_nickname_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fish_nickname_trgm ON public.fish USING gin (nickname public.gin_trgm_ops);


--
-- Name: ix_fish_strain_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fish_strain_trgm ON public.fish USING gin (strain public.gin_trgm_ops);


--
-- Name: ix_fish_treatments_treatment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fish_treatments_treatment ON public.fish_treatments USING btree (treatment_id);


--
-- Name: ix_ft_fish; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ft_fish ON public.fish_treatments USING btree (fish_id);


--
-- Name: ix_fta_fish; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fta_fish ON public.fish_transgene_alleles USING btree (fish_id);


--
-- Name: ix_fta_transgene; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fta_transgene ON public.fish_transgene_alleles USING btree (transgene_base_code, allele_number);


--
-- Name: ix_genotypes_transgene; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_genotypes_transgene ON public.genotypes USING btree (transgene_id_uuid);


--
-- Name: ix_injected_plasmid_treatments_plasmid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_injected_plasmid_treatments_plasmid ON public.injected_plasmid_treatments USING btree (plasmid_id);


--
-- Name: ix_injected_rna_treatments_rna; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_injected_rna_treatments_rna ON public.injected_rna_treatments USING btree (rna_id);


--
-- Name: ix_ipt_enzyme_ci; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ipt_enzyme_ci ON public.injected_plasmid_treatments USING btree (lower(enzyme)) WHERE (enzyme IS NOT NULL);


--
-- Name: ix_tank_assignments_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tank_assignments_status ON public.tank_assignments USING btree (status);


--
-- Name: ix_treatments_batch; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_treatments_batch ON public.treatments USING btree (batch_id);


--
-- Name: ix_treatments_operator_ci; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_treatments_operator_ci ON public.treatments USING btree (lower(operator)) WHERE (operator IS NOT NULL);


--
-- Name: ix_treatments_performed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_treatments_performed_at ON public.treatments USING btree (performed_at);


--
-- Name: ix_treatments_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_treatments_type ON public.treatments USING btree (treatment_type);


--
-- Name: ix_treatments_type_time_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_treatments_type_time_code ON public.treatments USING btree (treatment_type, performed_at, code);


--
-- Name: uq_dye_name_ci; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_dye_name_ci ON public.dyes USING btree (lower(name)) WHERE (name IS NOT NULL);


--
-- Name: uq_fish_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_fish_id ON public.fish USING btree (id);


--
-- Name: uq_fish_name_ci; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_fish_name_ci ON public.fish USING btree (lower(name)) WHERE (name IS NOT NULL);


--
-- Name: uq_fish_tg_allele; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_fish_tg_allele ON public.fish_transgene_alleles USING btree (fish_id, transgene_base_code, allele_number);


--
-- Name: uq_fish_treatments; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_fish_treatments ON public.fish_treatments USING btree (fish_id, treatment_id);


--
-- Name: uq_fish_treatments_pair; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_fish_treatments_pair ON public.fish_treatments USING btree (fish_id, treatment_id);


--
-- Name: uq_genotypes_fish_transgene; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_genotypes_fish_transgene ON public.genotypes USING btree (fish_id, transgene_id_uuid);


--
-- Name: uq_plasmids_name_ci; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_plasmids_name_ci ON public.plasmids USING btree (lower(name)) WHERE (name IS NOT NULL);


--
-- Name: uq_rna_name_ci; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_rna_name_ci ON public.rnas USING btree (lower(name)) WHERE (name IS NOT NULL);


--
-- Name: uq_tanks_id_uuid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_tanks_id_uuid ON public.tanks USING btree (id_uuid);


--
-- Name: uq_tanks_tank_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_tanks_tank_code ON public.tanks USING btree (tank_code);


--
-- Name: uq_treatments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_treatments_id ON public.treatments USING btree (id);


--
-- Name: ix_realtime_subscription_entity; Type: INDEX; Schema: realtime; Owner: -
--

CREATE INDEX ix_realtime_subscription_entity ON realtime.subscription USING btree (entity);


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
-- Name: idx_objects_bucket_id_name; Type: INDEX; Schema: storage; Owner: -
--

CREATE INDEX idx_objects_bucket_id_name ON storage.objects USING btree (bucket_id, name COLLATE "C");


--
-- Name: name_prefix_search; Type: INDEX; Schema: storage; Owner: -
--

CREATE INDEX name_prefix_search ON storage.objects USING btree (name text_pattern_ops);


--
-- Name: supabase_functions_hooks_h_table_id_h_name_idx; Type: INDEX; Schema: supabase_functions; Owner: -
--

CREATE INDEX supabase_functions_hooks_h_table_id_h_name_idx ON supabase_functions.hooks USING btree (hook_table_id, hook_name);


--
-- Name: supabase_functions_hooks_request_id_idx; Type: INDEX; Schema: supabase_functions; Owner: -
--

CREATE INDEX supabase_functions_hooks_request_id_idx ON supabase_functions.hooks USING btree (request_id);


--
-- Name: messages_2025_09_20_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_09_20_pkey;


--
-- Name: messages_2025_09_21_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_09_21_pkey;


--
-- Name: messages_2025_09_22_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_09_22_pkey;


--
-- Name: messages_2025_09_23_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_09_23_pkey;


--
-- Name: messages_2025_09_24_pkey; Type: INDEX ATTACH; Schema: realtime; Owner: -
--

ALTER INDEX realtime.messages_pkey ATTACH PARTITION realtime.messages_2025_09_24_pkey;


--
-- Name: dye_treatments trg_batch_guard_dye; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_batch_guard_dye AFTER INSERT OR UPDATE ON public.dye_treatments FOR EACH ROW EXECUTE FUNCTION public.treatment_batch_guard_v2();


--
-- Name: injected_plasmid_treatments trg_batch_guard_plasmid; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_batch_guard_plasmid AFTER INSERT OR UPDATE ON public.injected_plasmid_treatments FOR EACH ROW EXECUTE FUNCTION public.treatment_batch_guard_v2();


--
-- Name: injected_rna_treatments trg_batch_guard_rna; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_batch_guard_rna AFTER INSERT OR UPDATE ON public.injected_rna_treatments FOR EACH ROW EXECUTE FUNCTION public.treatment_batch_guard_v2();


--
-- Name: treatments trg_batch_guard_treat; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_batch_guard_treat AFTER INSERT OR UPDATE ON public.treatments FOR EACH ROW EXECUTE FUNCTION public.treatment_batch_guard_v2();


--
-- Name: dyes trg_dye_code_autofill; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_dye_code_autofill BEFORE INSERT ON public.dyes FOR EACH ROW EXECUTE FUNCTION public.dye_code_autofill();


--
-- Name: fish trg_fish_code_autofill; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_fish_code_autofill BEFORE INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.fish_code_autofill();


--
-- Name: fish_treatments trg_ft_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_ft_updated_at BEFORE UPDATE ON public.fish_treatments FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


--
-- Name: plasmids trg_plasmid_code_autofill; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_plasmid_code_autofill BEFORE INSERT ON public.plasmids FOR EACH ROW EXECUTE FUNCTION public.plasmid_code_autofill();


--
-- Name: rnas trg_rna_code_autofill; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_rna_code_autofill BEFORE INSERT ON public.rnas FOR EACH ROW EXECUTE FUNCTION public.rna_code_autofill();


--
-- Name: tanks trg_set_tank_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_tank_code BEFORE INSERT ON public.tanks FOR EACH ROW EXECUTE FUNCTION public.trg_set_tank_code();


--
-- Name: dye_treatments trg_type_guard_dye; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_type_guard_dye BEFORE INSERT OR UPDATE ON public.dye_treatments FOR EACH ROW EXECUTE FUNCTION public.detail_type_guard_v2();


--
-- Name: injected_plasmid_treatments trg_type_guard_plasmid; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_type_guard_plasmid BEFORE INSERT OR UPDATE ON public.injected_plasmid_treatments FOR EACH ROW EXECUTE FUNCTION public.detail_type_guard_v2();


--
-- Name: injected_rna_treatments trg_type_guard_rna; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_type_guard_rna BEFORE INSERT OR UPDATE ON public.injected_rna_treatments FOR EACH ROW EXECUTE FUNCTION public.detail_type_guard_v2();


--
-- Name: subscription tr_check_filters; Type: TRIGGER; Schema: realtime; Owner: -
--

CREATE TRIGGER tr_check_filters BEFORE INSERT OR UPDATE ON realtime.subscription FOR EACH ROW EXECUTE FUNCTION realtime.subscription_check_filters();


--
-- Name: objects update_objects_updated_at; Type: TRIGGER; Schema: storage; Owner: -
--

CREATE TRIGGER update_objects_updated_at BEFORE UPDATE ON storage.objects FOR EACH ROW EXECUTE FUNCTION storage.update_updated_at_column();


--
-- Name: extensions extensions_tenant_external_id_fkey; Type: FK CONSTRAINT; Schema: _realtime; Owner: -
--

ALTER TABLE ONLY _realtime.extensions
    ADD CONSTRAINT extensions_tenant_external_id_fkey FOREIGN KEY (tenant_external_id) REFERENCES _realtime.tenants(external_id) ON DELETE CASCADE;


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
-- Name: dye_treatments dye_treatments_dye_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dye_treatments
    ADD CONSTRAINT dye_treatments_dye_fk FOREIGN KEY (dye_id) REFERENCES public.dyes(id_uuid) ON DELETE CASCADE;


--
-- Name: dye_treatments dye_treatments_treatment_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dye_treatments
    ADD CONSTRAINT dye_treatments_treatment_fk FOREIGN KEY (treatment_id) REFERENCES public.treatments(id) ON DELETE CASCADE;


--
-- Name: fish fish_father_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT fish_father_fk FOREIGN KEY (father_fish_id) REFERENCES public.fish(id) ON DELETE SET NULL;


--
-- Name: fish fish_mother_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT fish_mother_fk FOREIGN KEY (mother_fish_id) REFERENCES public.fish(id) ON DELETE SET NULL;


--
-- Name: fish_tanks fish_tanks_tank_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_tanks
    ADD CONSTRAINT fish_tanks_tank_fk FOREIGN KEY (tank_id) REFERENCES public.tanks(id_uuid) ON DELETE SET NULL;


--
-- Name: fish_transgene_alleles fish_transgene_alleles_fk_allele; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_transgene_alleles
    ADD CONSTRAINT fish_transgene_alleles_fk_allele FOREIGN KEY (transgene_base_code, allele_number) REFERENCES public.transgene_alleles(transgene_base_code, allele_number) ON DELETE CASCADE;


--
-- Name: fish_transgene_alleles fish_transgene_alleles_fk_fish; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_transgene_alleles
    ADD CONSTRAINT fish_transgene_alleles_fk_fish FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;


--
-- Name: fish_treatments fish_treatments_fish_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_treatments
    ADD CONSTRAINT fish_treatments_fish_fk FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;


--
-- Name: fish_treatments fish_treatments_treatment_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_treatments
    ADD CONSTRAINT fish_treatments_treatment_fk FOREIGN KEY (treatment_id) REFERENCES public.treatments(id) ON DELETE CASCADE;


--
-- Name: fish_transgene_alleles fk_fta_allele; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_transgene_alleles
    ADD CONSTRAINT fk_fta_allele FOREIGN KEY (transgene_base_code, allele_number) REFERENCES public.transgene_alleles(transgene_base_code, allele_number) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: fish_transgene_alleles fk_fta_fish; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish_transgene_alleles
    ADD CONSTRAINT fk_fta_fish FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;


--
-- Name: genotypes genotypes_fish_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.genotypes
    ADD CONSTRAINT genotypes_fish_fk FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;


--
-- Name: genotypes genotypes_transgene_id_uuid_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.genotypes
    ADD CONSTRAINT genotypes_transgene_id_uuid_fkey FOREIGN KEY (transgene_id_uuid) REFERENCES public.transgenes(id_uuid) ON DELETE CASCADE;


--
-- Name: injected_rna_treatments injected_rna_treatments_rna_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.injected_rna_treatments
    ADD CONSTRAINT injected_rna_treatments_rna_fk FOREIGN KEY (rna_id) REFERENCES public.rnas(id_uuid) ON DELETE CASCADE;


--
-- Name: injected_rna_treatments injected_rna_treatments_treatment_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.injected_rna_treatments
    ADD CONSTRAINT injected_rna_treatments_treatment_fk FOREIGN KEY (treatment_id) REFERENCES public.treatments(id) ON DELETE CASCADE;


--
-- Name: injected_plasmid_treatments ipt_plasmid_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.injected_plasmid_treatments
    ADD CONSTRAINT ipt_plasmid_fk FOREIGN KEY (plasmid_id) REFERENCES public.plasmids(id_uuid);


--
-- Name: injected_plasmid_treatments ipt_treatment_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.injected_plasmid_treatments
    ADD CONSTRAINT ipt_treatment_fk FOREIGN KEY (treatment_id) REFERENCES public.treatments(id) ON DELETE CASCADE;


--
-- Name: tank_assignments tank_assignments_fish_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tank_assignments
    ADD CONSTRAINT tank_assignments_fish_id_fkey FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE;


--
-- Name: transgene_alleles transgene_alleles_fk_transgene; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transgene_alleles
    ADD CONSTRAINT transgene_alleles_fk_transgene FOREIGN KEY (transgene_base_code) REFERENCES public.transgenes(transgene_base_code) ON DELETE CASCADE;


--
-- Name: objects objects_bucketId_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.objects
    ADD CONSTRAINT "objects_bucketId_fkey" FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


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
-- Name: messages; Type: ROW SECURITY; Schema: realtime; Owner: -
--

ALTER TABLE realtime.messages ENABLE ROW LEVEL SECURITY;

--
-- Name: buckets; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.buckets ENABLE ROW LEVEL SECURITY;

--
-- Name: migrations; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: objects; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

--
-- Name: s3_multipart_uploads; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.s3_multipart_uploads ENABLE ROW LEVEL SECURITY;

--
-- Name: s3_multipart_uploads_parts; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.s3_multipart_uploads_parts ENABLE ROW LEVEL SECURITY;

--
-- Name: supabase_realtime; Type: PUBLICATION; Schema: -; Owner: -
--

CREATE PUBLICATION supabase_realtime WITH (publish = 'insert, update, delete, truncate');


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

\unrestrict 3igHr9aAfJ7EeVLfFlsmIfswxHuZ98tZ48Jo5oao5LIifMdJU8AsSpmmGvqecSc

