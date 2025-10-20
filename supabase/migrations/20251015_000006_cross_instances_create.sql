--
-- PostgreSQL database dump
--

\restrict cVeCDveziYI8GRx5bGg5VKydSyub6wicosUtZ34fACSdIUh9lb7BiJ76RxgobOj

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
    clutch_birthday date GENERATED ALWAYS AS (((cross_date + '1 day'::interval))::date) STORED,
    tank_pair_id uuid,
    run_number integer
);


--
-- Name: COLUMN cross_instances.clutch_birthday; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.cross_instances.clutch_birthday IS 'Clutch birthday = cross_date + 1 day (stored generated column)';


--
-- Name: cross_instances cross_instances_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_instances
    ADD CONSTRAINT cross_instances_pkey PRIMARY KEY (id);


--
-- Name: cross_instances ux_cross_instances_tp_date; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_instances
    ADD CONSTRAINT ux_cross_instances_tp_date UNIQUE (tank_pair_id, cross_date);


--
-- Name: cross_instances ux_cross_instances_tp_run; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_instances
    ADD CONSTRAINT ux_cross_instances_tp_run UNIQUE (tank_pair_id, run_number);


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
-- Name: ix_ci_cross_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ci_cross_id ON public.cross_instances USING btree (cross_id);


--
-- Name: ix_cross_instances_clutch_birthday; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cross_instances_clutch_birthday ON public.cross_instances USING btree (clutch_birthday);


--
-- Name: ix_cross_instances_cross_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cross_instances_cross_id ON public.cross_instances USING btree (cross_id);


--
-- Name: ix_cross_instances_cross_run_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cross_instances_cross_run_code ON public.cross_instances USING btree (cross_run_code);


--
-- Name: ix_cross_instances_father_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cross_instances_father_id ON public.cross_instances USING btree (father_tank_id);


--
-- Name: ix_cross_instances_mother_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cross_instances_mother_id ON public.cross_instances USING btree (mother_tank_id);


--
-- Name: ix_cross_instances_tank_pair; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cross_instances_tank_pair ON public.cross_instances USING btree (tank_pair_id);


--
-- Name: uq_cross_instances_by_pair_date; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_cross_instances_by_pair_date ON public.cross_instances USING btree (tank_pair_id, cross_date) WHERE (tank_pair_id IS NOT NULL);


--
-- Name: cross_instances trg_cross_instance_auto_clutch; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cross_instance_auto_clutch AFTER INSERT ON public.cross_instances FOR EACH ROW EXECUTE FUNCTION public.ensure_clutch_for_cross_instance();


--
-- Name: cross_instances trg_cross_instances_set_codes; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cross_instances_set_codes BEFORE INSERT ON public.cross_instances FOR EACH ROW EXECUTE FUNCTION public.trg_cross_instances_set_codes();


--
-- Name: cross_instances trg_cross_run_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cross_run_code BEFORE INSERT ON public.cross_instances FOR EACH ROW EXECUTE FUNCTION public.trg_cross_run_code();


--
-- Name: cross_instances trg_refresh_mv_overview_crosses_daily_d; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_crosses_daily_d AFTER DELETE ON public.cross_instances FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_crosses_daily();


--
-- Name: cross_instances trg_refresh_mv_overview_crosses_daily_i; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_crosses_daily_i AFTER INSERT ON public.cross_instances FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_crosses_daily();


--
-- Name: cross_instances trg_refresh_mv_overview_crosses_daily_u; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_crosses_daily_u AFTER UPDATE ON public.cross_instances FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_crosses_daily();


--
-- Name: cross_instances trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.cross_instances FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: cross_instances cross_instances_tank_pair_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_instances
    ADD CONSTRAINT cross_instances_tank_pair_id_fkey FOREIGN KEY (tank_pair_id) REFERENCES public.tank_pairs(id);


--
-- Name: cross_instances fk_cross_instances_cross; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cross_instances
    ADD CONSTRAINT fk_cross_instances_cross FOREIGN KEY (cross_id) REFERENCES public.crosses(id) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;


--
-- Name: cross_instances allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.cross_instances FOR SELECT TO authenticated USING (true);


--
-- Name: cross_instances app_rw_insert_ci; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_insert_ci ON public.cross_instances FOR INSERT TO app_rw WITH CHECK (true);


--
-- Name: cross_instances app_rw_select_ci; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_select_ci ON public.cross_instances FOR SELECT TO app_rw USING (true);


--
-- Name: cross_instances app_rw_update_ci; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_update_ci ON public.cross_instances FOR UPDATE TO app_rw USING (true) WITH CHECK (true);


--
-- Name: cross_instances; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.cross_instances ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

\unrestrict cVeCDveziYI8GRx5bGg5VKydSyub6wicosUtZ34fACSdIUh9lb7BiJ76RxgobOj

