--
-- PostgreSQL database dump
--

\restrict FUqHvPiJ4sGazzgET09mAG1wrV7mpxdWq5YtRqgmDazkdEC7rBDX4ZsC7Qw5SVU

-- Dumped from database version 17.4
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

SET default_tablespace = '';

SET default_table_access_method = heap;

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
-- Name: clutch_plans clutch_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutch_plans
    ADD CONSTRAINT clutch_plans_pkey PRIMARY KEY (id);


--
-- Name: ix_clutch_plans_clutch_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clutch_plans_clutch_code ON public.clutch_plans USING btree (clutch_code);


--
-- Name: ix_clutch_plans_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clutch_plans_id ON public.clutch_plans USING btree (id);


--
-- Name: ix_cp_id_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cp_id_code ON public.clutch_plans USING btree (id, clutch_code);


--
-- Name: uq_clutch_plans_clutch_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_clutch_plans_clutch_code ON public.clutch_plans USING btree (clutch_code);


--
-- Name: clutch_plans cp_require_planned_crosses; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER cp_require_planned_crosses BEFORE UPDATE ON public.clutch_plans FOR EACH ROW EXECUTE FUNCTION public.trg_cp_require_planned_crosses();


--
-- Name: clutch_plans trg_clutch_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_clutch_code BEFORE INSERT ON public.clutch_plans FOR EACH ROW EXECUTE FUNCTION public.trg_clutch_code();


--
-- Name: clutch_plans trg_clutch_plans_set_expected; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_clutch_plans_set_expected BEFORE INSERT OR UPDATE ON public.clutch_plans FOR EACH ROW EXECUTE FUNCTION public.trg_clutch_plans_set_expected();


--
-- Name: clutch_plans trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.clutch_plans FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: clutch_plans allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.clutch_plans FOR SELECT TO authenticated USING (true);


--
-- Name: clutch_plans; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.clutch_plans ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

\unrestrict FUqHvPiJ4sGazzgET09mAG1wrV7mpxdWq5YtRqgmDazkdEC7rBDX4ZsC7Qw5SVU

