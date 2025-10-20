--
-- PostgreSQL database dump
--

\restrict G5RMGLicTC7uvCtTPd8o2vMRr6uv0s8yzgJlQgiq6X4ssON0ElHE9MUFWYMp6wq

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
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: clutch_instance_treatments clutch_instance_treatments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutch_instance_treatments
    ADD CONSTRAINT clutch_instance_treatments_pkey PRIMARY KEY (id);


--
-- Name: ix_cit_clutch_instance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cit_clutch_instance_id ON public.clutch_instance_treatments USING btree (clutch_instance_id);


--
-- Name: uq_cit_instance_material; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_cit_instance_material ON public.clutch_instance_treatments USING btree (clutch_instance_id, lower(COALESCE(material_type, ''::text)), lower(COALESCE(material_code, ''::text)));


--
-- Name: clutch_instance_treatments clutch_instance_treatments_clutch_instance_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clutch_instance_treatments
    ADD CONSTRAINT clutch_instance_treatments_clutch_instance_id_fkey FOREIGN KEY (clutch_instance_id) REFERENCES public.clutch_instances(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict G5RMGLicTC7uvCtTPd8o2vMRr6uv0s8yzgJlQgiq6X4ssON0ElHE9MUFWYMp6wq

