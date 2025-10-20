--
-- PostgreSQL database dump
--

\restrict 2D0tZhLNihdS2CRyWLzbNrw3hFaUGBYZiTQZdlbrQaCQyiyxTJYMpwaAhISiRpB

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
    cross_id uuid NOT NULL,
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
-- Name: planned_crosses planned_crosses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planned_crosses
    ADD CONSTRAINT planned_crosses_pkey PRIMARY KEY (id);


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
-- Name: ix_pc_clutch_cross; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pc_clutch_cross ON public.planned_crosses USING btree (clutch_id, cross_id);


--
-- Name: ix_planned_crosses_clutch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_planned_crosses_clutch_id ON public.planned_crosses USING btree (clutch_id);


--
-- Name: ix_planned_crosses_cross_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_planned_crosses_cross_id ON public.planned_crosses USING btree (cross_id);


--
-- Name: uq_planned_crosses_clutch_parents_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_planned_crosses_clutch_parents_canonical ON public.planned_crosses USING btree (clutch_id, mother_tank_id, father_tank_id) WHERE ((is_canonical = true) AND (mother_tank_id IS NOT NULL) AND (father_tank_id IS NOT NULL));


--
-- Name: uq_planned_crosses_cross_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_planned_crosses_cross_code ON public.planned_crosses USING btree (cross_code) WHERE (cross_code IS NOT NULL);


--
-- Name: ux_planned_crosses_cross_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_planned_crosses_cross_code ON public.planned_crosses USING btree (cross_code);


--
-- Name: planned_crosses trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.planned_crosses FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: planned_crosses fk_planned_crosses_cross; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planned_crosses
    ADD CONSTRAINT fk_planned_crosses_cross FOREIGN KEY (cross_id) REFERENCES public.crosses(id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;


--
-- Name: planned_crosses allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.planned_crosses FOR SELECT TO authenticated USING (true);


--
-- Name: planned_crosses app_rw_insert_planned_crosses; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_insert_planned_crosses ON public.planned_crosses FOR INSERT TO app_rw WITH CHECK (true);


--
-- Name: planned_crosses app_rw_select_planned_crosses; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_select_planned_crosses ON public.planned_crosses FOR SELECT TO app_rw USING (true);


--
-- Name: planned_crosses app_rw_update_planned_crosses; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_update_planned_crosses ON public.planned_crosses FOR UPDATE TO app_rw USING (true) WITH CHECK (true);


--
-- Name: planned_crosses; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.planned_crosses ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

\unrestrict 2D0tZhLNihdS2CRyWLzbNrw3hFaUGBYZiTQZdlbrQaCQyiyxTJYMpwaAhISiRpB

