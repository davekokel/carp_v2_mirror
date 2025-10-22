--
-- PostgreSQL database dump
--

\restrict 28klzCMlQKZdbE3WMvUg3zEAUVztg2glbro5RIA2Vqjix4WYHvyoXzXACNjhqXL

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
    cross_name_code text NOT NULL,
    cross_name_genotype text,
    updated_at timestamp with time zone DEFAULT now(),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    cross_name text,
    CONSTRAINT chk_cross_code_shape CHECK (((cross_code IS NULL) OR (cross_code ~ '^CROSS-[0-9A-Z]{2}[0-9A-Z]{4,}$'::text)))
);


--
-- Name: crosses crosses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crosses
    ADD CONSTRAINT crosses_pkey PRIMARY KEY (id);


--
-- Name: crosses uq_cross_code; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crosses
    ADD CONSTRAINT uq_cross_code UNIQUE (cross_code);


--
-- Name: idx_crosses_created_desc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_crosses_created_desc ON public.crosses USING btree (created_at DESC);


--
-- Name: idx_crosses_parents_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_crosses_parents_code ON public.crosses USING btree (mother_code, father_code);


--
-- Name: ix_crosses_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_crosses_id ON public.crosses USING btree (id);


--
-- Name: uq_crosses_concept_pair; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_crosses_concept_pair ON public.crosses USING btree (upper(TRIM(BOTH FROM mother_code)), upper(TRIM(BOTH FROM father_code)));


--
-- Name: uq_crosses_cross_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_crosses_cross_code ON public.crosses USING btree (cross_code) WHERE (cross_code IS NOT NULL);


--
-- Name: crosses crosses_set_code_and_genotype; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER crosses_set_code_and_genotype BEFORE INSERT OR UPDATE OF mother_code, father_code, cross_name_genotype ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_crosses_set_code_and_genotype();


--
-- Name: crosses trg_cross_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cross_code BEFORE INSERT ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_cross_code();


--
-- Name: crosses trg_cross_code_fill; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cross_code_fill BEFORE INSERT OR UPDATE ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_cross_code_fill();


--
-- Name: crosses trg_cross_name_fill; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cross_name_fill BEFORE INSERT OR UPDATE ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_cross_name_fill();


--
-- Name: crosses trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: crosses zz_bi_normalize_cross_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER zz_bi_normalize_cross_code BEFORE INSERT OR UPDATE ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_cross_code_normalize();


--
-- Name: crosses allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.crosses FOR SELECT TO authenticated USING (true);


--
-- Name: crosses; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.crosses ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

\unrestrict 28klzCMlQKZdbE3WMvUg3zEAUVztg2glbro5RIA2Vqjix4WYHvyoXzXACNjhqXL

