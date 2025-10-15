--
-- PostgreSQL database dump
--


-- Dumped from database version 16.10 (Homebrew)
-- Dumped by pg_dump version 18.0

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
-- SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: clutch_containers; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE IF NOT EXISTS public.clutch_containers (
    container_id uuid NOT NULL,
    clutch_id uuid NOT NULL,
    is_mixed boolean DEFAULT true NOT NULL,
    selection_label text,
    source_container_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text NOT NULL,
    note text
);


ALTER TABLE public.clutch_containers OWNER TO postgres;

--
-- Name: clutch_genotype_options; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE IF NOT EXISTS public.clutch_genotype_options (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    clutch_id uuid NOT NULL,
    allele_code text,
    transgene_base_code text
);


ALTER TABLE public.clutch_genotype_options OWNER TO postgres;

--
-- Name: clutch_plan_treatments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE IF NOT EXISTS public.clutch_plan_treatments (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    clutch_id uuid NOT NULL,
    material_type text NOT NULL,
    material_code text NOT NULL,
    material_name text,
    dose numeric,
    units text,
    at_hpf numeric,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT clutch_plan_treatments_material_type_check CHECK ((material_type = ANY (ARRAY['plasmid'::text, 'rna'::text])))
);


ALTER TABLE public.clutch_plan_treatments OWNER TO postgres;

--
-- Name: clutch_plans; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE IF NOT EXISTS public.clutch_plans (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    mom_code text NOT NULL,
    dad_code text NOT NULL,
    cross_date date DEFAULT CURRENT_DATE NOT NULL,
    note text,
    created_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    planned_name text,
    planned_nickname text,
    clutch_code text
);


ALTER TABLE public.clutch_plans OWNER TO postgres;

--
-- Name: clutch_treatments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE IF NOT EXISTS public.clutch_treatments (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    clutch_id uuid NOT NULL,
    type text NOT NULL,
    reagent_id uuid,
    amount numeric,
    units text,
    at_time timestamp with time zone,
    note text,
    created_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT clutch_treatments_type_check CHECK ((type = ANY (ARRAY['injected_plasmid'::text, 'injected_rna'::text])))
);


ALTER TABLE public.clutch_treatments OWNER TO postgres;

--
-- Name: clutches; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE IF NOT EXISTS public.clutches (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
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
    clutch_instance_code text
);


ALTER TABLE public.clutches OWNER TO postgres;

--
-- Name: cross_instances; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE IF NOT EXISTS public.cross_instances (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    cross_id uuid NOT NULL,
    cross_date date DEFAULT CURRENT_DATE NOT NULL,
    mother_tank_id uuid,
    father_tank_id uuid,
    note text,
    created_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    cross_run_code text
);


ALTER TABLE public.cross_instances OWNER TO postgres;

--
-- Name: cross_plan_genotype_alleles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE IF NOT EXISTS public.cross_plan_genotype_alleles (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    plan_id uuid NOT NULL,
    transgene_base_code text NOT NULL,
    allele_number integer NOT NULL,
    zygosity_planned text
);


ALTER TABLE public.cross_plan_genotype_alleles OWNER TO postgres;

--
-- Name: cross_plan_runs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE IF NOT EXISTS public.cross_plan_runs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    plan_id uuid NOT NULL,
    seq integer NOT NULL,
    planned_date date NOT NULL,
    tank_a_id uuid,
    tank_b_id uuid,
    status text DEFAULT 'planned'::text NOT NULL,
    note text,
    created_by text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.cross_plan_runs OWNER TO postgres;

--
-- Name: cross_plan_treatments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE IF NOT EXISTS public.cross_plan_treatments (
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
    CONSTRAINT chk_cpt_one_reagent CHECK (((((rna_id IS NOT NULL))::integer + ((plasmid_id IS NOT NULL))::integer) <= 1))
);


ALTER TABLE public.cross_plan_treatments OWNER TO postgres;

--
-- Name: cross_plans; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE IF NOT EXISTS public.cross_plans (
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
    plan_nickname text
);


ALTER TABLE public.cross_plans OWNER TO postgres;

--
-- Name: crosses; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE IF NOT EXISTS public.crosses (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    mother_code text NOT NULL,
    father_code text NOT NULL,
    created_by text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    note text,
    planned_for date,
    cross_code text,
    cross_name text,
    cross_nickname text
);


ALTER TABLE public.crosses OWNER TO postgres;

--
-- Name: planned_crosses; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE IF NOT EXISTS public.planned_crosses (
    id_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    clutch_id uuid NOT NULL,
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
    is_canonical boolean DEFAULT true NOT NULL
);


ALTER TABLE public.planned_crosses OWNER TO postgres;

--
-- Name: v_containers_crossing_candidates; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.v_containers_crossing_candidates AS
 SELECT id_uuid,
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
   FROM public.containers
  WHERE (container_type = ANY (ARRAY['inventory_tank'::text, 'crossing_tank'::text, 'holding_tank'::text, 'nursery_tank'::text, 'petri_dish'::text]));


ALTER VIEW public.v_containers_crossing_candidates OWNER TO postgres;

--
-- Name: v_cross_plan_runs_enriched; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.v_cross_plan_runs_enriched AS
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
     LEFT JOIN public.containers ca ON ((ca.id_uuid = r.tank_a_id)))
     LEFT JOIN public.containers cb ON ((cb.id_uuid = r.tank_b_id)));


ALTER VIEW public.v_cross_plan_runs_enriched OWNER TO postgres;

--
-- Name: v_cross_plans_enriched; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.v_cross_plans_enriched AS
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
     LEFT JOIN public.containers ca ON ((ca.id_uuid = p.tank_a_id)))
     LEFT JOIN public.containers cb ON ((cb.id_uuid = p.tank_b_id)));


ALTER VIEW public.v_cross_plans_enriched OWNER TO postgres;

--
-- Name: v_crosses_status; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.v_crosses_status AS
 SELECT id_uuid,
    mother_code,
    father_code,
    planned_for,
    created_by,
    created_at,
        CASE
            WHEN (EXISTS ( SELECT 1
               FROM public.clutches x
              WHERE (x.cross_id = c.id_uuid))) THEN 'realized'::text
            ELSE 'planned'::text
        END AS status
   FROM public.crosses c;


ALTER VIEW public.v_crosses_status OWNER TO postgres;

--
-- Name: vw_clutches_concept_overview; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.vw_clutches_concept_overview AS
 WITH base AS (
         SELECT cp.id_uuid AS clutch_plan_id,
            pc.id_uuid AS planned_cross_id,
            cp.clutch_code,
            cp.planned_name AS clutch_name,
            cp.planned_nickname AS clutch_nickname,
            pc.cross_date AS date_planned,
            COALESCE(cp.note, pc.note) AS note,
            cp.created_by,
            cp.created_at
           FROM (public.clutch_plans cp
             LEFT JOIN public.planned_crosses pc ON ((pc.clutch_id = cp.id_uuid)))
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
             JOIN public.clutch_containers cc ON ((cc.clutch_id = c.id_uuid)))
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


ALTER VIEW public.vw_clutches_concept_overview OWNER TO postgres;

--
-- Name: vw_clutches_overview_human; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.vw_clutches_overview_human AS
 WITH base AS (
         SELECT c.id_uuid AS clutch_id,
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
             LEFT JOIN public.planned_crosses pc ON ((pc.id_uuid = c.planned_cross_id)))
             LEFT JOIN public.clutch_plans cp ON ((cp.id_uuid = pc.clutch_id)))
             LEFT JOIN public.containers mt ON ((mt.id_uuid = pc.mother_tank_id)))
             LEFT JOIN public.containers ft ON ((ft.id_uuid = pc.father_tank_id)))
        ), instances AS (
         SELECT cc.clutch_id,
            (count(*))::integer AS n_instances
           FROM public.clutch_containers cc
          GROUP BY cc.clutch_id
        ), crosses_via_clutches AS (
         SELECT b_1.clutch_id,
            (count(x.id_uuid))::integer AS n_crosses
           FROM (base b_1
             LEFT JOIN public.crosses x ON ((x.id_uuid = b_1.cross_id)))
          GROUP BY b_1.clutch_id
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
  ORDER BY COALESCE(((b.date_birth)::timestamp without time zone)::timestamp with time zone, b.created_at) DESC NULLS LAST;


ALTER VIEW public.vw_clutches_overview_human OWNER TO postgres;

--
-- Name: vw_cross_runs_overview; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.vw_cross_runs_overview AS
 WITH cl AS (
         SELECT clutches.cross_instance_id,
            (count(*))::integer AS n_clutches
           FROM public.clutches
          GROUP BY clutches.cross_instance_id
        ), cnt AS (
         SELECT c.cross_instance_id,
            (count(cc.*))::integer AS n_containers
           FROM (public.clutches c
             JOIN public.clutch_containers cc ON ((cc.clutch_id = c.id_uuid)))
          GROUP BY c.cross_instance_id
        )
 SELECT ci.id_uuid AS cross_instance_id,
    ci.cross_run_code,
    ci.cross_date,
    x.id_uuid AS cross_id,
    COALESCE(x.cross_code, (x.id_uuid)::text) AS cross_code,
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
     JOIN public.crosses x ON ((x.id_uuid = ci.cross_id)))
     LEFT JOIN public.containers cm ON ((cm.id_uuid = ci.mother_tank_id)))
     LEFT JOIN public.containers cf ON ((cf.id_uuid = ci.father_tank_id)))
     LEFT JOIN cl ON ((cl.cross_instance_id = ci.id_uuid)))
     LEFT JOIN cnt ON ((cnt.cross_instance_id = ci.id_uuid)))
  ORDER BY ci.cross_date DESC, ci.created_at DESC;


ALTER VIEW public.vw_cross_runs_overview OWNER TO postgres;

--
-- Name: vw_crosses_concept; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.vw_crosses_concept AS
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
             JOIN public.clutch_containers cc ON ((cc.clutch_id = c.id_uuid)))
          GROUP BY c.cross_id
        )
 SELECT x.id_uuid AS cross_id,
    COALESCE(x.cross_code, (x.id_uuid)::text) AS cross_code,
    x.mother_code AS mom_code,
    x.father_code AS dad_code,
    x.created_by,
    x.created_at,
    COALESCE(runs.n_runs, 0) AS n_runs,
    runs.latest_cross_date,
    COALESCE(cl.n_clutches, 0) AS n_clutches,
    COALESCE(cnt.n_containers, 0) AS n_containers
   FROM (((public.crosses x
     LEFT JOIN runs ON ((runs.cross_id = x.id_uuid)))
     LEFT JOIN cl ON ((cl.cross_id = x.id_uuid)))
     LEFT JOIN cnt ON ((cnt.cross_id = x.id_uuid)))
  ORDER BY x.created_at DESC;


ALTER VIEW public.vw_crosses_concept OWNER TO postgres;

--
-- Name: vw_planned_clutches_overview; Type: VIEW; Schema: public; Owner: postgres
--

CREATE OR REPLACE VIEW public.vw_planned_clutches_overview AS
 WITH x AS (
         SELECT cp.id_uuid AS clutch_plan_id,
            pc.id_uuid AS planned_cross_id,
            cp.clutch_code,
            cp.planned_name AS clutch_name,
            cp.planned_nickname AS clutch_nickname,
            pc.cross_date,
            cp.created_by,
            cp.created_at,
            COALESCE(cp.note, pc.note) AS note
           FROM (public.clutch_plans cp
             LEFT JOIN public.planned_crosses pc ON ((pc.clutch_id = cp.id_uuid)))
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
  ORDER BY COALESCE(((x.cross_date)::timestamp without time zone)::timestamp with time zone, x.created_at) DESC NULLS LAST;


ALTER VIEW public.vw_planned_clutches_overview OWNER TO postgres;

--
-- Name: clutch_containers clutch_containers_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutch_containers
    ADD CONSTRAINT clutch_containers_pkey PRIMARY KEY (container_id);


--
-- Name: clutch_genotype_options clutch_genotype_options_clutch_id_allele_code_transgene_bas_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutch_genotype_options
    ADD CONSTRAINT clutch_genotype_options_clutch_id_allele_code_transgene_bas_key UNIQUE (clutch_id, allele_code, transgene_base_code);


--
-- Name: clutch_genotype_options clutch_genotype_options_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutch_genotype_options
    ADD CONSTRAINT clutch_genotype_options_pkey PRIMARY KEY (id_uuid);


--
-- Name: clutch_plan_treatments clutch_plan_treatments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutch_plan_treatments
    ADD CONSTRAINT clutch_plan_treatments_pkey PRIMARY KEY (id_uuid);


--
-- Name: clutch_plans clutch_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutch_plans
    ADD CONSTRAINT clutch_plans_pkey PRIMARY KEY (id_uuid);


--
-- Name: clutch_treatments clutch_treatments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutch_treatments
    ADD CONSTRAINT clutch_treatments_pkey PRIMARY KEY (id_uuid);


--
-- Name: clutches clutches_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutches
    ADD CONSTRAINT clutches_pkey PRIMARY KEY (id_uuid);


--
-- Name: cross_instances cross_instances_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_instances
    ADD CONSTRAINT cross_instances_pkey PRIMARY KEY (id_uuid);


--
-- Name: cross_plan_genotype_alleles cross_plan_genotype_alleles_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plan_genotype_alleles
    ADD CONSTRAINT cross_plan_genotype_alleles_pkey PRIMARY KEY (id);


--
-- Name: cross_plan_genotype_alleles cross_plan_genotype_alleles_plan_id_transgene_base_code_all_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plan_genotype_alleles
    ADD CONSTRAINT cross_plan_genotype_alleles_plan_id_transgene_base_code_all_key UNIQUE (plan_id, transgene_base_code, allele_number);


--
-- Name: cross_plan_runs cross_plan_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plan_runs
    ADD CONSTRAINT cross_plan_runs_pkey PRIMARY KEY (id);


--
-- Name: cross_plan_runs cross_plan_runs_plan_id_seq_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plan_runs
    ADD CONSTRAINT cross_plan_runs_plan_id_seq_key UNIQUE (plan_id, seq);


--
-- Name: cross_plan_treatments cross_plan_treatments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plan_treatments
    ADD CONSTRAINT cross_plan_treatments_pkey PRIMARY KEY (id);


--
-- Name: cross_plans cross_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plans
    ADD CONSTRAINT cross_plans_pkey PRIMARY KEY (id);


--
-- Name: crosses crosses_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crosses
    ADD CONSTRAINT crosses_pkey PRIMARY KEY (id_uuid);


--
-- Name: planned_crosses planned_crosses_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.planned_crosses
    ADD CONSTRAINT planned_crosses_pkey PRIMARY KEY (id_uuid);


--
-- Name: cross_plans uq_cross_plans_unique; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plans
    ADD CONSTRAINT uq_cross_plans_unique UNIQUE (plan_date, tank_a_id, tank_b_id);


--
-- Name: idx_cc_clutch; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cc_clutch ON public.clutch_containers USING btree (clutch_id);


--
-- Name: idx_cc_created_desc; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cc_created_desc ON public.clutch_containers USING btree (created_at DESC);


--
-- Name: idx_cc_selection; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cc_selection ON public.clutch_containers USING btree (selection_label);


--
-- Name: idx_cgo_clutch; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cgo_clutch ON public.clutch_genotype_options USING btree (clutch_id);


--
-- Name: idx_clutches_batch; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_clutches_batch ON public.clutches USING btree (batch_label);


--
-- Name: idx_clutches_created_desc; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_clutches_created_desc ON public.clutches USING btree (created_at DESC);


--
-- Name: idx_clutches_cross_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_clutches_cross_id ON public.clutches USING btree (cross_id);


--
-- Name: idx_clutches_run_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_clutches_run_id ON public.clutches USING btree (run_id);


--
-- Name: idx_clutches_seed; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_clutches_seed ON public.clutches USING btree (seed_batch_id);


--
-- Name: idx_cpga_plan; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cpga_plan ON public.cross_plan_genotype_alleles USING btree (plan_id);


--
-- Name: idx_cpt_plan; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cpt_plan ON public.cross_plan_treatments USING btree (plan_id);


--
-- Name: idx_cpt_plasmid; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cpt_plasmid ON public.cross_plan_treatments USING btree (plasmid_id);


--
-- Name: idx_cpt_rna; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cpt_rna ON public.cross_plan_treatments USING btree (rna_id);


--
-- Name: idx_cross_plan_runs_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cross_plan_runs_date ON public.cross_plan_runs USING btree (planned_date);


--
-- Name: idx_cross_plan_runs_plan; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cross_plan_runs_plan ON public.cross_plan_runs USING btree (plan_id);


--
-- Name: idx_cross_plans_created_by; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cross_plans_created_by ON public.cross_plans USING btree (created_by);


--
-- Name: idx_cross_plans_day_father; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cross_plans_day_father ON public.cross_plans USING btree (plan_date, father_fish_id);


--
-- Name: idx_cross_plans_day_mother; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cross_plans_day_mother ON public.cross_plans USING btree (plan_date, mother_fish_id);


--
-- Name: idx_cross_plans_father; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cross_plans_father ON public.cross_plans USING btree (father_fish_id);


--
-- Name: idx_cross_plans_mother; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cross_plans_mother ON public.cross_plans USING btree (mother_fish_id);


--
-- Name: idx_cross_plans_nick; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cross_plans_nick ON public.cross_plans USING btree (plan_nickname);


--
-- Name: idx_cross_plans_plan_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cross_plans_plan_date ON public.cross_plans USING btree (plan_date);


--
-- Name: idx_cross_plans_tank_a; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cross_plans_tank_a ON public.cross_plans USING btree (tank_a_id);


--
-- Name: idx_cross_plans_tank_b; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cross_plans_tank_b ON public.cross_plans USING btree (tank_b_id);


--
-- Name: idx_cross_plans_title; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cross_plans_title ON public.cross_plans USING btree (plan_title);


--
-- Name: idx_crosses_created_desc; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_crosses_created_desc ON public.crosses USING btree (created_at DESC);


--
-- Name: idx_crosses_parents_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_crosses_parents_code ON public.crosses USING btree (mother_code, father_code);


--
-- Name: idx_ct_clutch; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_ct_clutch ON public.clutch_treatments USING btree (clutch_id);


--
-- Name: idx_planned_crosses_clutch; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_planned_crosses_clutch ON public.planned_crosses USING btree (clutch_id);


--
-- Name: uq_clutch_plans_clutch_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_clutch_plans_clutch_code ON public.clutch_plans USING btree (clutch_code);


--
-- Name: uq_clutches_instance_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_clutches_instance_code ON public.clutches USING btree (clutch_instance_code) WHERE (clutch_instance_code IS NOT NULL);


--
-- Name: uq_clutches_planned_by_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_clutches_planned_by_date ON public.clutches USING btree (planned_cross_id, date_birth);


--
-- Name: uq_crosses_concept_pair; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_crosses_concept_pair ON public.crosses USING btree (upper(TRIM(BOTH FROM mother_code)), upper(TRIM(BOTH FROM father_code)));


--
-- Name: uq_crosses_cross_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_crosses_cross_code ON public.crosses USING btree (cross_code) WHERE (cross_code IS NOT NULL);


--
-- Name: uq_planned_crosses_clutch_parents_canonical; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_planned_crosses_clutch_parents_canonical ON public.planned_crosses USING btree (clutch_id, mother_tank_id, father_tank_id) WHERE ((is_canonical = true) AND (mother_tank_id IS NOT NULL) AND (father_tank_id IS NOT NULL));


--
-- Name: uq_planned_crosses_cross_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_planned_crosses_cross_code ON public.planned_crosses USING btree (cross_code) WHERE (cross_code IS NOT NULL);


--
-- Name: clutch_plans trg_clutch_code; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_clutch_code BEFORE INSERT ON public.clutch_plans FOR EACH ROW EXECUTE FUNCTION public.trg_clutch_code();


--
-- Name: clutches trg_clutch_instance_code; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_clutch_instance_code BEFORE INSERT ON public.clutches FOR EACH ROW EXECUTE FUNCTION public.trg_clutch_instance_code();


--
-- Name: crosses trg_cross_code; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_cross_code BEFORE INSERT ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_cross_code();


--
-- Name: crosses trg_cross_name_fill; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_cross_name_fill BEFORE INSERT ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_cross_name_fill();


--
-- Name: cross_instances trg_cross_run_code; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_cross_run_code BEFORE INSERT ON public.cross_instances FOR EACH ROW EXECUTE FUNCTION public.trg_cross_run_code();


--
-- Name: clutch_containers clutch_containers_clutch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutch_containers
    ADD CONSTRAINT clutch_containers_clutch_id_fkey FOREIGN KEY (clutch_id) REFERENCES public.clutches(id_uuid) ON DELETE CASCADE;


--
-- Name: clutch_containers clutch_containers_container_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutch_containers
    ADD CONSTRAINT clutch_containers_container_id_fkey FOREIGN KEY (container_id) REFERENCES public.containers(id_uuid) ON DELETE CASCADE;


--
-- Name: clutch_containers clutch_containers_source_container_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutch_containers
    ADD CONSTRAINT clutch_containers_source_container_id_fkey FOREIGN KEY (source_container_id) REFERENCES public.containers(id_uuid) ON DELETE SET NULL;


--
-- Name: clutch_genotype_options clutch_genotype_options_clutch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutch_genotype_options
    ADD CONSTRAINT clutch_genotype_options_clutch_id_fkey FOREIGN KEY (clutch_id) REFERENCES public.clutches(id_uuid) ON DELETE CASCADE;


--
-- Name: clutch_plan_treatments clutch_plan_treatments_clutch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutch_plan_treatments
    ADD CONSTRAINT clutch_plan_treatments_clutch_id_fkey FOREIGN KEY (clutch_id) REFERENCES public.clutch_plans(id_uuid) ON DELETE CASCADE;


--
-- Name: clutch_treatments clutch_treatments_clutch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutch_treatments
    ADD CONSTRAINT clutch_treatments_clutch_id_fkey FOREIGN KEY (clutch_id) REFERENCES public.clutches(id_uuid) ON DELETE CASCADE;


--
-- Name: clutches clutches_cross_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutches
    ADD CONSTRAINT clutches_cross_id_fkey FOREIGN KEY (cross_id) REFERENCES public.crosses(id_uuid) ON DELETE CASCADE;


--
-- Name: clutches clutches_cross_instance_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutches
    ADD CONSTRAINT clutches_cross_instance_id_fkey FOREIGN KEY (cross_instance_id) REFERENCES public.cross_instances(id_uuid) ON DELETE SET NULL;


--
-- Name: clutches clutches_planned_cross_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutches
    ADD CONSTRAINT clutches_planned_cross_id_fkey FOREIGN KEY (planned_cross_id) REFERENCES public.planned_crosses(id_uuid);


--
-- Name: clutches clutches_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clutches
    ADD CONSTRAINT clutches_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.cross_plan_runs(id) ON DELETE SET NULL;


--
-- Name: cross_instances cross_instances_cross_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_instances
    ADD CONSTRAINT cross_instances_cross_id_fkey FOREIGN KEY (cross_id) REFERENCES public.crosses(id_uuid) ON DELETE CASCADE;


--
-- Name: cross_instances cross_instances_father_tank_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_instances
    ADD CONSTRAINT cross_instances_father_tank_id_fkey FOREIGN KEY (father_tank_id) REFERENCES public.containers(id_uuid);


--
-- Name: cross_instances cross_instances_mother_tank_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_instances
    ADD CONSTRAINT cross_instances_mother_tank_id_fkey FOREIGN KEY (mother_tank_id) REFERENCES public.containers(id_uuid);


--
-- Name: cross_plan_genotype_alleles cross_plan_genotype_alleles_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plan_genotype_alleles
    ADD CONSTRAINT cross_plan_genotype_alleles_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES public.cross_plans(id) ON DELETE CASCADE;


--
-- Name: cross_plan_runs cross_plan_runs_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plan_runs
    ADD CONSTRAINT cross_plan_runs_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES public.cross_plans(id) ON DELETE CASCADE;


--
-- Name: cross_plan_runs cross_plan_runs_tank_a_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plan_runs
    ADD CONSTRAINT cross_plan_runs_tank_a_id_fkey FOREIGN KEY (tank_a_id) REFERENCES public.containers(id_uuid);


--
-- Name: cross_plan_runs cross_plan_runs_tank_b_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plan_runs
    ADD CONSTRAINT cross_plan_runs_tank_b_id_fkey FOREIGN KEY (tank_b_id) REFERENCES public.containers(id_uuid);


--
-- Name: cross_plan_treatments cross_plan_treatments_plan_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plan_treatments
    ADD CONSTRAINT cross_plan_treatments_plan_id_fkey FOREIGN KEY (plan_id) REFERENCES public.cross_plans(id) ON DELETE CASCADE;


--
-- Name: cross_plan_treatments cross_plan_treatments_plasmid_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plan_treatments
    ADD CONSTRAINT cross_plan_treatments_plasmid_id_fkey FOREIGN KEY (plasmid_id) REFERENCES public.plasmid_registry(id) ON DELETE RESTRICT;


--
-- Name: cross_plan_treatments cross_plan_treatments_rna_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plan_treatments
    ADD CONSTRAINT cross_plan_treatments_rna_id_fkey FOREIGN KEY (rna_id) REFERENCES public.rna_registry(id) ON DELETE RESTRICT;


--
-- Name: cross_plans cross_plans_father_fish_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plans
    ADD CONSTRAINT cross_plans_father_fish_id_fkey FOREIGN KEY (father_fish_id) REFERENCES public.fish(id) ON DELETE RESTRICT;


--
-- Name: cross_plans cross_plans_mother_fish_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plans
    ADD CONSTRAINT cross_plans_mother_fish_id_fkey FOREIGN KEY (mother_fish_id) REFERENCES public.fish(id) ON DELETE RESTRICT;


--
-- Name: cross_plan_genotype_alleles fk_cpga_transgene_allele; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plan_genotype_alleles
    ADD CONSTRAINT fk_cpga_transgene_allele FOREIGN KEY (transgene_base_code, allele_number) REFERENCES public.transgene_alleles(transgene_base_code, allele_number) ON DELETE RESTRICT;


--
-- Name: cross_plans fk_cross_plans_tank_a_cont; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plans
    ADD CONSTRAINT fk_cross_plans_tank_a_cont FOREIGN KEY (tank_a_id) REFERENCES public.containers(id_uuid) ON DELETE RESTRICT;


--
-- Name: cross_plans fk_cross_plans_tank_b_cont; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cross_plans
    ADD CONSTRAINT fk_cross_plans_tank_b_cont FOREIGN KEY (tank_b_id) REFERENCES public.containers(id_uuid) ON DELETE RESTRICT;


--
-- Name: planned_crosses planned_crosses_clutch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.planned_crosses
    ADD CONSTRAINT planned_crosses_clutch_id_fkey FOREIGN KEY (clutch_id) REFERENCES public.clutch_plans(id_uuid) ON DELETE CASCADE;


--
-- Name: planned_crosses planned_crosses_cross_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.planned_crosses
    ADD CONSTRAINT planned_crosses_cross_id_fkey FOREIGN KEY (cross_id) REFERENCES public.crosses(id_uuid) ON DELETE SET NULL;


--
-- Name: planned_crosses planned_crosses_cross_instance_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.planned_crosses
    ADD CONSTRAINT planned_crosses_cross_instance_id_fkey FOREIGN KEY (cross_instance_id) REFERENCES public.cross_instances(id_uuid) ON DELETE SET NULL;


--
-- Name: planned_crosses planned_crosses_father_tank_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.planned_crosses
    ADD CONSTRAINT planned_crosses_father_tank_id_fkey FOREIGN KEY (father_tank_id) REFERENCES public.containers(id_uuid);


--
-- Name: planned_crosses planned_crosses_mother_tank_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.planned_crosses
    ADD CONSTRAINT planned_crosses_mother_tank_id_fkey FOREIGN KEY (mother_tank_id) REFERENCES public.containers(id_uuid);


--
-- PostgreSQL database dump complete
--


