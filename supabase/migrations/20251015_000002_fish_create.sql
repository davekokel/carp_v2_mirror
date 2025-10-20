--
-- PostgreSQL database dump
--

\restrict 5BrA7FBPpLvrqMFvqQISch7Rmfbe9YgEZU3Do4r7Htq7HzQ0CrlqkTrGsEo5nTo

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
    birthday date,
    CONSTRAINT chk_fish_code_shape CHECK (((fish_code IS NULL) OR (fish_code ~ '^FSH-[0-9A-Z]{2}[0-9A-Z]+$'::text))),
    CONSTRAINT ck_fish_fish_code_format CHECK ((fish_code ~ '^FSH-[0-9]{2}[0-9A-Z]{4,}$'::text))
);


--
-- Name: COLUMN fish.genetic_background; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.fish.genetic_background IS 'Background genetic strain (from CSV: genetic_background).';


--
-- Name: fish fish_fish_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT fish_fish_code_key UNIQUE (fish_code);


--
-- Name: fish fish_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fish
    ADD CONSTRAINT fish_pkey PRIMARY KEY (id);


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
-- Name: fish bi_set_fish_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER bi_set_fish_code BEFORE INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.fish_bi_set_fish_code();


--
-- Name: fish trg_audit_del; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_del AFTER DELETE ON public.fish FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: fish trg_audit_ins; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_ins AFTER INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: fish trg_audit_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_audit_upd AFTER UPDATE ON public.fish FOR EACH ROW EXECUTE FUNCTION audit.fn_writes();


--
-- Name: fish trg_fish_autotank; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_fish_autotank AFTER INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.trg_fish_autotank();


--
-- Name: fish trg_fish_before_insert_code; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_fish_before_insert_code BEFORE INSERT ON public.fish FOR EACH ROW EXECUTE FUNCTION public.fish_before_insert_code();


--
-- Name: fish trg_fish_birthday_sync; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_fish_birthday_sync BEFORE INSERT OR UPDATE ON public.fish FOR EACH ROW EXECUTE FUNCTION public.fish_birthday_sync();


--
-- Name: fish trg_refresh_mv_overview_fish_daily_d; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_fish_daily_d AFTER DELETE ON public.fish FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_fish_daily();


--
-- Name: fish trg_refresh_mv_overview_fish_daily_i; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_fish_daily_i AFTER INSERT ON public.fish FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_fish_daily();


--
-- Name: fish trg_refresh_mv_overview_fish_daily_u; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_refresh_mv_overview_fish_daily_u AFTER UPDATE ON public.fish FOR EACH STATEMENT EXECUTE FUNCTION public.refresh_mv_overview_fish_daily();


--
-- Name: fish trg_set_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.fish FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: fish allow_read_auth; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY allow_read_auth ON public.fish FOR SELECT TO authenticated USING (true);


--
-- Name: fish app_rw_insert_fish; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_insert_fish ON public.fish FOR INSERT TO app_rw WITH CHECK (true);


--
-- Name: fish app_rw_select_fish; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_select_fish ON public.fish FOR SELECT TO app_rw USING (true);


--
-- Name: fish app_rw_update_fish; Type: POLICY; Schema: public; Owner: -
--

CREATE POLICY app_rw_update_fish ON public.fish FOR UPDATE TO app_rw USING (true) WITH CHECK (true);


--
-- Name: fish; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.fish ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

\unrestrict 5BrA7FBPpLvrqMFvqQISch7Rmfbe9YgEZU3Do4r7Htq7HzQ0CrlqkTrGsEo5nTo

