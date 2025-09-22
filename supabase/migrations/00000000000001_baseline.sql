CREATE SCHEMA IF NOT EXISTS public;




CREATE SCHEMA IF NOT EXISTS "public";


ALTER SCHEMA "public" OWNER TO "postgres";


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE TYPE "public"."treatment_type_enum" AS ENUM (
    'injected_plasmid',
    'injected_rna',
    'dye'
);


ALTER TYPE "public"."treatment_type_enum" OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."_next_tank_code"() RETURNS "text"
    LANGUAGE "plpgsql"
    AS $$
declare y int := extract(year from now())::int;
        n int;
begin
  select nextval('public.seq_tank_code')::int into n;
  return format('TANK-%s-%04s', public._tank_code_year(y), n);
end;
$$;


ALTER FUNCTION "public"."_next_tank_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."_tank_code_year"("y" integer) RETURNS "text"
    LANGUAGE "sql" IMMUTABLE
    AS $$ select lpad((y % 100)::text, 2, '0') $$;


ALTER FUNCTION "public"."_tank_code_year"("y" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."assert_treatment_type"("expected" "text", "tid" "uuid") RETURNS "void"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."assert_treatment_type"("expected" "text", "tid" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."assert_unique_batch_key"("p_treatment_id" "uuid") RETURNS "void"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."assert_unique_batch_key"("p_treatment_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."detail_type_guard_v2"() RETURNS "trigger"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."detail_type_guard_v2"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."dye_code_autofill"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
begin if new.dye_code is null or btrim(new.dye_code)='' then new.dye_code:=public.gen_dye_code(); end if; return new; end $$;


ALTER FUNCTION "public"."dye_code_autofill"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."fish_code_autofill"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
begin if new.fish_code is null or btrim(new.fish_code)='' then new.fish_code := public.gen_fish_code(coalesce(new.created_at, now())); end if; return new; end $$;


ALTER FUNCTION "public"."fish_code_autofill"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."gen_dye_code"() RETURNS "text"
    LANGUAGE "plpgsql"
    AS $$
declare k int;
begin update public.dye_counters set n=n+1 returning n into k; return format('DYE-%04s', k); end $$;


ALTER FUNCTION "public"."gen_dye_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."gen_fish_code"("p_ts" timestamp with time zone DEFAULT "now"()) RETURNS "text"
    LANGUAGE "plpgsql"
    AS $$
declare y int := extract(year from p_ts);
declare k int;
begin insert into public.fish_year_counters(year,n) values (y,0) on conflict (year) do nothing;
update public.fish_year_counters set n=n+1 where year=y returning n into k;
return format('FSH-%s-%04s', y, k);
end $$;


ALTER FUNCTION "public"."gen_fish_code"("p_ts" timestamp with time zone) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."gen_plasmid_code"() RETURNS "text"
    LANGUAGE "plpgsql"
    AS $$
declare k int;
begin update public.plasmid_counters set n=n+1 returning n into k;
return format('PLM-%04s', k);
end $$;


ALTER FUNCTION "public"."gen_plasmid_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."gen_rna_code"() RETURNS "text"
    LANGUAGE "plpgsql"
    AS $$
declare k int;
begin update public.rna_counters set n=n+1 returning n into k; return format('RNA-%04s', k); end $$;


ALTER FUNCTION "public"."gen_rna_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."gen_tank_code"() RETURNS "text"
    LANGUAGE "sql"
    AS $$
          select 'TANK-' || to_char(now(),'YYYY') || '-' ||
                 lpad(nextval('public.tank_counters')::text, 4, '0');
        $$;


ALTER FUNCTION "public"."gen_tank_code"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."pg_raise"("name" "text", "msg" "text") RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
begin
  raise exception using errcode = 'P0001', message = msg, constraint = name;
end $$;


ALTER FUNCTION "public"."pg_raise"("name" "text", "msg" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."pg_raise"("name" "text", "msg" "text", "tid" "uuid") RETURNS "void"
    LANGUAGE "plpgsql"
    AS $$
begin
  raise exception using errcode = 'P0001', message = msg || ' ('||tid||')', constraint = name;
end $$;


ALTER FUNCTION "public"."pg_raise"("name" "text", "msg" "text", "tid" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."plasmid_code_autofill"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
begin if new.plasmid_code is null or btrim(new.plasmid_code)='' then new.plasmid_code := public.gen_plasmid_code(); end if; return new; end $$;


ALTER FUNCTION "public"."plasmid_code_autofill"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."rna_code_autofill"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
begin if new.rna_code is null or btrim(new.rna_code)='' then new.rna_code:=public.gen_rna_code(); end if; return new; end $$;


ALTER FUNCTION "public"."rna_code_autofill"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."set_updated_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
begin new.updated_at=now(); return new; end $$;


ALTER FUNCTION "public"."set_updated_at"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."treatment_batch_guard_v2"() RETURNS "trigger"
    LANGUAGE "plpgsql"
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


ALTER FUNCTION "public"."treatment_batch_guard_v2"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."trg_set_tank_code"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
begin
  if new.tank_code is null or btrim(new.tank_code) = '' then
    new.tank_code := public._next_tank_code();
  end if;
  return new;
end;
$$;


ALTER FUNCTION "public"."trg_set_tank_code"() OWNER TO "postgres";




CREATE TABLE IF NOT EXISTS "public"."_staging_fish_load" (
    "fish_name" "text" NOT NULL,
    "date_birth" "date",
    "n_new_tanks" integer DEFAULT 0 NOT NULL
);


ALTER TABLE "public"."_staging_fish_load" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."dye_counters" (
    "n" integer DEFAULT 0 NOT NULL
);


ALTER TABLE "public"."dye_counters" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."dye_treatments" (
    "amount" numeric,
    "units" "text",
    "route" "text",
    "id" "uuid" DEFAULT "gen_random_uuid"(),
    "treatment_id" "uuid" NOT NULL,
    "dye_id" "uuid" NOT NULL
);


ALTER TABLE "public"."dye_treatments" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."dyes" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "dye_code" "text",
    "name" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text"
);


ALTER TABLE "public"."dyes" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."fish" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "fish_code" "text",
    "name" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text",
    "date_birth" "date",
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "father_fish_id" "uuid",
    "mother_fish_id" "uuid"
);


ALTER TABLE "public"."fish" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."fish_tanks" (
    "fish_name" "text" NOT NULL,
    "linked_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "fish_id" "uuid",
    "tank_id" "uuid"
);


ALTER TABLE "public"."fish_tanks" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."fish_treatments" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "applied_at" timestamp with time zone,
    "notes" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text",
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_by" "text",
    "fish_id" "uuid" NOT NULL,
    "treatment_id" "uuid" NOT NULL
);


ALTER TABLE "public"."fish_treatments" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."fish_year_counters" (
    "year" integer NOT NULL,
    "n" integer DEFAULT 0 NOT NULL
);


ALTER TABLE "public"."fish_year_counters" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."genotypes" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "transgene_id_uuid" "uuid" NOT NULL,
    "zygosity" "text",
    "notes" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text",
    "fish_id" "uuid",
    CONSTRAINT "genotypes_zygosity_check" CHECK (("zygosity" = ANY (ARRAY['het'::"text", 'hom'::"text", 'wt'::"text", 'unk'::"text"])))
);


ALTER TABLE "public"."genotypes" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."injected_plasmid_treatments" (
    "concentration_ng_per_ul" numeric,
    "volume_nl" numeric,
    "injection_stage" "text",
    "vehicle" "text",
    "enzyme" "text",
    "id" "uuid" DEFAULT "gen_random_uuid"(),
    "treatment_id" "uuid" NOT NULL,
    "plasmid_id" "uuid" NOT NULL
);


ALTER TABLE "public"."injected_plasmid_treatments" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."injected_rna_treatments" (
    "concentration_ng_per_ul" numeric,
    "volume_nl" numeric,
    "injection_stage" "text",
    "vehicle" "text",
    "id" "uuid" DEFAULT "gen_random_uuid"(),
    "treatment_id" "uuid" NOT NULL,
    "rna_id" "uuid" NOT NULL
);


ALTER TABLE "public"."injected_rna_treatments" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."plasmid_counters" (
    "n" integer DEFAULT 0 NOT NULL
);


ALTER TABLE "public"."plasmid_counters" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."plasmids" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "plasmid_code" "text",
    "name" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text"
);


ALTER TABLE "public"."plasmids" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."rna_counters" (
    "n" integer DEFAULT 0 NOT NULL
);


ALTER TABLE "public"."rna_counters" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."rnas" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "rna_code" "text",
    "name" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text"
);


ALTER TABLE "public"."rnas" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."seed_fish_tmp" (
    "fish_name" "text",
    "nickname" double precision,
    "date_birth" "text",
    "line_building_stage" "text",
    "strain" "text",
    "has_transgene" bigint,
    "has_mutation" bigint,
    "has_treatment_injected_plasmid" bigint,
    "has_treatment_injected_rna" bigint,
    "has_treatment_dye" bigint,
    "n_new_tanks" bigint,
    "seed_batch_id" "text"
);


ALTER TABLE "public"."seed_fish_tmp" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."seed_transgenes_tmp" (
    "fish_name" "text",
    "transgene_name" "text",
    "allele_name" "text",
    "zygosity" "text",
    "new_allele_note" double precision,
    "seed_batch_id" "text"
);


ALTER TABLE "public"."seed_transgenes_tmp" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."seed_treatment_dye_tmp" (
    "fish_name" "text",
    "dye_name" "text",
    "operator" "text",
    "performed_at" "text",
    "description" double precision,
    "notes" "text",
    "seed_batch_id" "text"
);


ALTER TABLE "public"."seed_treatment_dye_tmp" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."seed_treatment_injected_plasmid_tmp" (
    "fish_name" "text",
    "plasmid_name" "text",
    "operator" "text",
    "performed_at" "text",
    "batch_label" "text",
    "injection_mix" "text",
    "injection_notes" double precision,
    "enzyme" "text",
    "seed_batch_id" "text"
);


ALTER TABLE "public"."seed_treatment_injected_plasmid_tmp" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."seed_treatment_injected_rna_tmp" (
    "fish_name" "text",
    "rna_name" "text",
    "operator" "text",
    "performed_at" "text",
    "description" double precision,
    "notes" "text",
    "seed_batch_id" "text"
);


ALTER TABLE "public"."seed_treatment_injected_rna_tmp" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."seq_tank_code"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."seq_tank_code" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."staging_links_dye" (
    "fish_code" "text",
    "dye_code" "text",
    "treatment_batch_id" "text",
    "performed_at" timestamp with time zone,
    "operator" "text",
    "amount" numeric,
    "units" "text",
    "route" "text",
    "notes" "text"
);


ALTER TABLE "public"."staging_links_dye" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."staging_links_dye_by_name" (
    "fish_name" "text",
    "dye_name" "text",
    "treatment_batch_id" "text",
    "performed_at" timestamp with time zone,
    "operator" "text",
    "amount" numeric,
    "units" "text",
    "route" "text",
    "notes" "text"
);


ALTER TABLE "public"."staging_links_dye_by_name" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."staging_links_injected_plasmid" (
    "fish_code" "text",
    "plasmid_code" "text",
    "treatment_batch_id" "text",
    "performed_at" timestamp with time zone,
    "operator" "text",
    "concentration_ng_per_ul" numeric,
    "volume_nl" numeric,
    "injection_stage" "text",
    "vehicle" "text",
    "notes" "text"
);


ALTER TABLE "public"."staging_links_injected_plasmid" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."staging_links_injected_plasmid_by_name" (
    "fish_name" "text",
    "plasmid_name" "text",
    "treatment_batch_id" "text",
    "performed_at" timestamp with time zone,
    "operator" "text",
    "concentration_ng_per_ul" numeric,
    "volume_nl" numeric,
    "injection_stage" "text",
    "vehicle" "text",
    "notes" "text",
    "enzyme" "text"
);


ALTER TABLE "public"."staging_links_injected_plasmid_by_name" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."staging_links_injected_rna" (
    "fish_code" "text",
    "rna_code" "text",
    "treatment_batch_id" "text",
    "performed_at" timestamp with time zone,
    "operator" "text",
    "concentration_ng_per_ul" numeric,
    "volume_nl" numeric,
    "injection_stage" "text",
    "vehicle" "text",
    "notes" "text"
);


ALTER TABLE "public"."staging_links_injected_rna" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."staging_links_injected_rna_by_name" (
    "fish_name" "text",
    "rna_name" "text",
    "treatment_batch_id" "text",
    "performed_at" timestamp with time zone,
    "operator" "text",
    "concentration_ng_per_ul" numeric,
    "volume_nl" numeric,
    "injection_stage" "text",
    "vehicle" "text",
    "notes" "text"
);


ALTER TABLE "public"."staging_links_injected_rna_by_name" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stg_dye" (
    "fish_name" "text",
    "dye_name" "text",
    "operator" "text",
    "performed_at" timestamp with time zone,
    "notes" "text",
    "source" "text"
);


ALTER TABLE "public"."stg_dye" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stg_inj_plasmid" (
    "fish_name" "text",
    "plasmid_name" "text",
    "operator" "text",
    "performed_at" "text",
    "batch_label" "text",
    "injection_mix" "text",
    "injection_notes" "text",
    "enzyme" "text"
);


ALTER TABLE "public"."stg_inj_plasmid" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."stg_inj_rna" (
    "fish_name" "text",
    "rna_name" "text",
    "operator" "text",
    "performed_at" timestamp with time zone,
    "notes" "text",
    "source" "text"
);


ALTER TABLE "public"."stg_inj_rna" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."tank_counters"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."tank_counters" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."tanks" (
    "id" bigint NOT NULL,
    "tank_code" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "id_uuid" "uuid"
);


ALTER TABLE "public"."tanks" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."tanks_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."tanks_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."tanks_id_seq" OWNED BY "public"."tanks"."id";



CREATE TABLE IF NOT EXISTS "public"."transgenes" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "base_code" "text" NOT NULL,
    "allele_num" "text",
    "name" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text"
);


ALTER TABLE "public"."transgenes" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."treatments" (
    "id_uuid" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "treatment_type" "public"."treatment_type_enum" NOT NULL,
    "batch_id" "text",
    "performed_at" timestamp with time zone,
    "operator" "text",
    "notes" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_by" "text",
    "batch_label" "text",
    "performed_on_date" "date" GENERATED ALWAYS AS ((("performed_at" AT TIME ZONE 'America/Los_Angeles'::"text"))::"date") STORED,
    "id" "uuid" NOT NULL
);


ALTER TABLE "public"."treatments" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_dye_treatments" AS
 SELECT "ft"."fish_id",
    "dt"."treatment_id",
    "d"."name" AS "dye_name"
   FROM (("public"."fish_treatments" "ft"
     JOIN "public"."dye_treatments" "dt" ON (("dt"."treatment_id" = "ft"."treatment_id")))
     JOIN "public"."dyes" "d" ON (("d"."id_uuid" = "dt"."dye_id")));


ALTER VIEW "public"."v_dye_treatments" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_plasmid_treatments" AS
 SELECT "ft"."fish_id",
    "ipt"."treatment_id",
    "p"."name" AS "plasmid_name"
   FROM (("public"."fish_treatments" "ft"
     JOIN "public"."injected_plasmid_treatments" "ipt" ON (("ipt"."treatment_id" = "ft"."treatment_id")))
     JOIN "public"."plasmids" "p" ON (("p"."id_uuid" = "ipt"."plasmid_id")));


ALTER VIEW "public"."v_plasmid_treatments" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_rna_treatments" AS
 SELECT "ft"."fish_id",
    "irt"."treatment_id",
    "r"."name" AS "rna_name"
   FROM (("public"."fish_treatments" "ft"
     JOIN "public"."injected_rna_treatments" "irt" ON (("irt"."treatment_id" = "ft"."treatment_id")))
     JOIN "public"."rnas" "r" ON (("r"."id_uuid" = "irt"."rna_id")));


ALTER VIEW "public"."v_rna_treatments" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_fish_overview_v1" AS
 WITH "tanks" AS (
         SELECT "ft"."fish_id",
            "string_agg"(DISTINCT COALESCE("t"."tank_code", ("t"."id_uuid")::"text"), ', '::"text" ORDER BY COALESCE("t"."tank_code", ("t"."id_uuid")::"text")) AS "tanks"
           FROM ("public"."fish_tanks" "ft"
             JOIN "public"."tanks" "t" ON (("t"."id_uuid" = "ft"."tank_id")))
          GROUP BY "ft"."fish_id"
        ), "plas" AS (
         SELECT "vpt"."fish_id",
            "string_agg"(DISTINCT "vpt"."plasmid_name", ', '::"text" ORDER BY "vpt"."plasmid_name") AS "plasmids"
           FROM "public"."v_plasmid_treatments" "vpt"
          GROUP BY "vpt"."fish_id"
        ), "genos" AS (
         SELECT "g"."fish_id",
            "string_agg"(DISTINCT COALESCE("tg"."name", "tg"."base_code"), ', '::"text" ORDER BY COALESCE("tg"."name", "tg"."base_code")) AS "genotypes"
           FROM ("public"."genotypes" "g"
             JOIN "public"."transgenes" "tg" ON (("tg"."id_uuid" = "g"."transgene_id_uuid")))
          GROUP BY "g"."fish_id"
        ), "rnas" AS (
         SELECT "v"."fish_id",
            "string_agg"(DISTINCT "v"."rna_name", ', '::"text" ORDER BY "v"."rna_name") AS "rnas"
           FROM "public"."v_rna_treatments" "v"
          GROUP BY "v"."fish_id"
        ), "dyes" AS (
         SELECT "v"."fish_id",
            "string_agg"(DISTINCT "v"."dye_name", ', '::"text" ORDER BY "v"."dye_name") AS "dyes"
           FROM "public"."v_dye_treatments" "v"
          GROUP BY "v"."fish_id"
        ), "treats" AS (
         SELECT "s"."fish_id",
            "string_agg"(DISTINCT "s"."val", '; '::"text" ORDER BY "s"."val") AS "treatments"
           FROM ( SELECT "ft"."fish_id",
                    (COALESCE(("tr_1"."treatment_type")::"text", 'unknown'::"text") ||
                        CASE
                            WHEN (TRIM(BOTH FROM COALESCE("tr_1"."notes", ''::"text")) <> ''::"text") THEN ((' ('::"text" || TRIM(BOTH FROM "tr_1"."notes")) || ')'::"text")
                            ELSE ''::"text"
                        END) AS "val"
                   FROM ("public"."fish_treatments" "ft"
                     JOIN "public"."treatments" "tr_1" ON (("tr_1"."id" = "ft"."treatment_id")))) "s"
          GROUP BY "s"."fish_id"
        )
 SELECT "f"."id" AS "fish_id",
    "f"."name" AS "fish_name",
    "f"."date_birth",
    "f"."created_at",
    COALESCE("tn"."tanks", ''::"text") AS "tanks",
    COALESCE("tr"."treatments", ''::"text") AS "treatments",
    COALESCE("pl"."plasmids", ''::"text") AS "plasmids",
    COALESCE("gn"."genotypes", ''::"text") AS "genotypes",
    COALESCE("rn"."rnas", ''::"text") AS "rnas",
    COALESCE("dy"."dyes", ''::"text") AS "dyes"
   FROM (((((("public"."fish" "f"
     LEFT JOIN "tanks" "tn" ON (("tn"."fish_id" = "f"."id")))
     LEFT JOIN "treats" "tr" ON (("tr"."fish_id" = "f"."id")))
     LEFT JOIN "plas" "pl" ON (("pl"."fish_id" = "f"."id")))
     LEFT JOIN "genos" "gn" ON (("gn"."fish_id" = "f"."id")))
     LEFT JOIN "rnas" "rn" ON (("rn"."fish_id" = "f"."id")))
     LEFT JOIN "dyes" "dy" ON (("dy"."fish_id" = "f"."id")))
  ORDER BY "f"."created_at", "f"."name";


ALTER VIEW "public"."v_fish_overview_v1" OWNER TO "postgres";


ALTER TABLE ONLY "public"."tanks" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."tanks_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."dyes"
    ADD CONSTRAINT "dyes_dye_code_key" UNIQUE ("dye_code");



ALTER TABLE ONLY "public"."dyes"
    ADD CONSTRAINT "dyes_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."fish"
    ADD CONSTRAINT "fish_fish_code_key" UNIQUE ("fish_code");



ALTER TABLE ONLY "public"."fish"
    ADD CONSTRAINT "fish_name_key" UNIQUE ("name");



ALTER TABLE ONLY "public"."fish"
    ADD CONSTRAINT "fish_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."fish_treatments"
    ADD CONSTRAINT "fish_treatments_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."fish_year_counters"
    ADD CONSTRAINT "fish_year_counters_pkey" PRIMARY KEY ("year");



ALTER TABLE ONLY "public"."genotypes"
    ADD CONSTRAINT "genotypes_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."plasmids"
    ADD CONSTRAINT "plasmids_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."plasmids"
    ADD CONSTRAINT "plasmids_plasmid_code_key" UNIQUE ("plasmid_code");



ALTER TABLE ONLY "public"."rnas"
    ADD CONSTRAINT "rnas_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."rnas"
    ADD CONSTRAINT "rnas_rna_code_key" UNIQUE ("rna_code");



ALTER TABLE ONLY "public"."tanks"
    ADD CONSTRAINT "tanks_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."tanks"
    ADD CONSTRAINT "tanks_tank_code_key" UNIQUE ("tank_code");



ALTER TABLE ONLY "public"."transgenes"
    ADD CONSTRAINT "transgenes_name_key" UNIQUE ("name");



ALTER TABLE ONLY "public"."transgenes"
    ADD CONSTRAINT "transgenes_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."treatments"
    ADD CONSTRAINT "treatments_pkey" PRIMARY KEY ("id_uuid");



ALTER TABLE ONLY "public"."dye_treatments"
    ADD CONSTRAINT "uq_dt_treatment" UNIQUE ("treatment_id");



ALTER TABLE ONLY "public"."injected_plasmid_treatments"
    ADD CONSTRAINT "uq_ipt_treatment" UNIQUE ("treatment_id");



ALTER TABLE ONLY "public"."injected_rna_treatments"
    ADD CONSTRAINT "uq_irt_treatment" UNIQUE ("treatment_id");



CREATE UNIQUE INDEX "idx_fish_name_unique" ON "public"."fish" USING "btree" ("name");



CREATE INDEX "ix_dye_treatments_dye" ON "public"."dye_treatments" USING "btree" ("dye_id");



CREATE INDEX "ix_fish_name" ON "public"."fish" USING "btree" ("name");



CREATE INDEX "ix_fish_treatments_treatment" ON "public"."fish_treatments" USING "btree" ("treatment_id");



CREATE INDEX "ix_genotypes_transgene" ON "public"."genotypes" USING "btree" ("transgene_id_uuid");



CREATE INDEX "ix_injected_plasmid_treatments_plasmid" ON "public"."injected_plasmid_treatments" USING "btree" ("plasmid_id");



CREATE INDEX "ix_injected_rna_treatments_rna" ON "public"."injected_rna_treatments" USING "btree" ("rna_id");



CREATE INDEX "ix_ipt_enzyme_ci" ON "public"."injected_plasmid_treatments" USING "btree" ("lower"("enzyme")) WHERE ("enzyme" IS NOT NULL);



CREATE INDEX "ix_treatments_batch" ON "public"."treatments" USING "btree" ("batch_id");



CREATE INDEX "ix_treatments_operator_ci" ON "public"."treatments" USING "btree" ("lower"("operator")) WHERE ("operator" IS NOT NULL);



CREATE INDEX "ix_treatments_type" ON "public"."treatments" USING "btree" ("treatment_type");



CREATE UNIQUE INDEX "uq_dye_name_ci" ON "public"."dyes" USING "btree" ("lower"("name")) WHERE ("name" IS NOT NULL);



CREATE UNIQUE INDEX "uq_fish_id" ON "public"."fish" USING "btree" ("id");



CREATE UNIQUE INDEX "uq_fish_name_ci" ON "public"."fish" USING "btree" ("lower"("name")) WHERE ("name" IS NOT NULL);



CREATE UNIQUE INDEX "uq_fish_treatments_pair" ON "public"."fish_treatments" USING "btree" ("fish_id", "treatment_id");



CREATE UNIQUE INDEX "uq_genotypes_fish_transgene" ON "public"."genotypes" USING "btree" ("fish_id", "transgene_id_uuid");



CREATE UNIQUE INDEX "uq_plasmids_name_ci" ON "public"."plasmids" USING "btree" ("lower"("name")) WHERE ("name" IS NOT NULL);



CREATE UNIQUE INDEX "uq_rna_name_ci" ON "public"."rnas" USING "btree" ("lower"("name")) WHERE ("name" IS NOT NULL);



CREATE UNIQUE INDEX "uq_tanks_id_uuid" ON "public"."tanks" USING "btree" ("id_uuid");



CREATE UNIQUE INDEX "uq_tanks_tank_code" ON "public"."tanks" USING "btree" ("tank_code");



CREATE UNIQUE INDEX "uq_treatments_id" ON "public"."treatments" USING "btree" ("id");



CREATE OR REPLACE TRIGGER "trg_batch_guard_dye" AFTER INSERT OR UPDATE ON "public"."dye_treatments" FOR EACH ROW EXECUTE FUNCTION "public"."treatment_batch_guard_v2"();



CREATE OR REPLACE TRIGGER "trg_batch_guard_plasmid" AFTER INSERT OR UPDATE ON "public"."injected_plasmid_treatments" FOR EACH ROW EXECUTE FUNCTION "public"."treatment_batch_guard_v2"();



CREATE OR REPLACE TRIGGER "trg_batch_guard_rna" AFTER INSERT OR UPDATE ON "public"."injected_rna_treatments" FOR EACH ROW EXECUTE FUNCTION "public"."treatment_batch_guard_v2"();



CREATE OR REPLACE TRIGGER "trg_batch_guard_treat" AFTER INSERT OR UPDATE ON "public"."treatments" FOR EACH ROW EXECUTE FUNCTION "public"."treatment_batch_guard_v2"();



CREATE OR REPLACE TRIGGER "trg_dye_code_autofill" BEFORE INSERT ON "public"."dyes" FOR EACH ROW EXECUTE FUNCTION "public"."dye_code_autofill"();



CREATE OR REPLACE TRIGGER "trg_fish_code_autofill" BEFORE INSERT ON "public"."fish" FOR EACH ROW EXECUTE FUNCTION "public"."fish_code_autofill"();



CREATE OR REPLACE TRIGGER "trg_ft_updated_at" BEFORE UPDATE ON "public"."fish_treatments" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_plasmid_code_autofill" BEFORE INSERT ON "public"."plasmids" FOR EACH ROW EXECUTE FUNCTION "public"."plasmid_code_autofill"();



CREATE OR REPLACE TRIGGER "trg_rna_code_autofill" BEFORE INSERT ON "public"."rnas" FOR EACH ROW EXECUTE FUNCTION "public"."rna_code_autofill"();



CREATE OR REPLACE TRIGGER "trg_set_tank_code" BEFORE INSERT ON "public"."tanks" FOR EACH ROW EXECUTE FUNCTION "public"."trg_set_tank_code"();



CREATE OR REPLACE TRIGGER "trg_type_guard_dye" BEFORE INSERT OR UPDATE ON "public"."dye_treatments" FOR EACH ROW EXECUTE FUNCTION "public"."detail_type_guard_v2"();



CREATE OR REPLACE TRIGGER "trg_type_guard_plasmid" BEFORE INSERT OR UPDATE ON "public"."injected_plasmid_treatments" FOR EACH ROW EXECUTE FUNCTION "public"."detail_type_guard_v2"();



CREATE OR REPLACE TRIGGER "trg_type_guard_rna" BEFORE INSERT OR UPDATE ON "public"."injected_rna_treatments" FOR EACH ROW EXECUTE FUNCTION "public"."detail_type_guard_v2"();



ALTER TABLE ONLY "public"."dye_treatments"
    ADD CONSTRAINT "dye_treatments_dye_fk" FOREIGN KEY ("dye_id") REFERENCES "public"."dyes"("id_uuid") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."dye_treatments"
    ADD CONSTRAINT "dye_treatments_treatment_fk" FOREIGN KEY ("treatment_id") REFERENCES "public"."treatments"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."fish"
    ADD CONSTRAINT "fish_father_fk" FOREIGN KEY ("father_fish_id") REFERENCES "public"."fish"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."fish"
    ADD CONSTRAINT "fish_mother_fk" FOREIGN KEY ("mother_fish_id") REFERENCES "public"."fish"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."fish_tanks"
    ADD CONSTRAINT "fish_tanks_tank_fk" FOREIGN KEY ("tank_id") REFERENCES "public"."tanks"("id_uuid") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."fish_treatments"
    ADD CONSTRAINT "fish_treatments_fish_fk" FOREIGN KEY ("fish_id") REFERENCES "public"."fish"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."fish_treatments"
    ADD CONSTRAINT "fish_treatments_treatment_fk" FOREIGN KEY ("treatment_id") REFERENCES "public"."treatments"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."genotypes"
    ADD CONSTRAINT "genotypes_fish_fk" FOREIGN KEY ("fish_id") REFERENCES "public"."fish"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."genotypes"
    ADD CONSTRAINT "genotypes_transgene_id_uuid_fkey" FOREIGN KEY ("transgene_id_uuid") REFERENCES "public"."transgenes"("id_uuid") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."injected_rna_treatments"
    ADD CONSTRAINT "injected_rna_treatments_rna_fk" FOREIGN KEY ("rna_id") REFERENCES "public"."rnas"("id_uuid") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."injected_rna_treatments"
    ADD CONSTRAINT "injected_rna_treatments_treatment_fk" FOREIGN KEY ("treatment_id") REFERENCES "public"."treatments"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."injected_plasmid_treatments"
    ADD CONSTRAINT "ipt_plasmid_fk" FOREIGN KEY ("plasmid_id") REFERENCES "public"."plasmids"("id_uuid");



ALTER TABLE ONLY "public"."injected_plasmid_treatments"
    ADD CONSTRAINT "ipt_treatment_fk" FOREIGN KEY ("treatment_id") REFERENCES "public"."treatments"("id") ON DELETE CASCADE;



REVOKE USAGE ON SCHEMA "public" FROM PUBLIC;



GRANT SELECT ON TABLE "public"."v_dye_treatments" TO "anon";
GRANT SELECT ON TABLE "public"."v_dye_treatments" TO "authenticated";
GRANT SELECT ON TABLE "public"."v_dye_treatments" TO "service_role";



GRANT SELECT ON TABLE "public"."v_plasmid_treatments" TO "anon";
GRANT SELECT ON TABLE "public"."v_plasmid_treatments" TO "authenticated";
GRANT SELECT ON TABLE "public"."v_plasmid_treatments" TO "service_role";



GRANT SELECT ON TABLE "public"."v_rna_treatments" TO "anon";
GRANT SELECT ON TABLE "public"."v_rna_treatments" TO "authenticated";
GRANT SELECT ON TABLE "public"."v_rna_treatments" TO "service_role";



GRANT SELECT ON TABLE "public"."v_fish_overview_v1" TO "anon";
GRANT SELECT ON TABLE "public"."v_fish_overview_v1" TO "authenticated";
GRANT SELECT ON TABLE "public"."v_fish_overview_v1" TO "service_role";



RESET ALL;
