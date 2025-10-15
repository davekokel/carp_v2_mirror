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
-- Name: containers; Type: TABLE; Schema: public; Owner: postgres
--
ALTER TABLE public.containers OWNER TO postgres;

--
-- Name: fish_tank_memberships; Type: TABLE; Schema: public; Owner: postgres
--
CREATE TABLE IF NOT EXISTS public.fish_tank_memberships (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    fish_id uuid NOT NULL,
    container_id uuid NOT NULL,
    joined_at timestamp with time zone DEFAULT now() NOT NULL,
    left_at timestamp with time zone,
    note text
);


ALTER TABLE public.fish_tank_memberships OWNER TO postgres;

--
-- Name: containers containers_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conrelid='public.containers'::regclass AND contype='p'
  ) THEN
    ALTER TABLE ONLY public.containers ADD CONSTRAINT containers_pkey PRIMARY KEY (id_uuid);
  END IF;
END;
$$ LANGUAGE plpgsql;


--
-- Name: fish_tank_memberships fish_tank_memberships_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conrelid='public.fish_tank_memberships'::regclass AND contype='p'
  ) THEN
    ALTER TABLE ONLY public.fish_tank_memberships ADD CONSTRAINT fish_tank_memberships_pkey PRIMARY KEY (id);
  END IF;
END;
$$ LANGUAGE plpgsql;


--
-- Name: idx_containers_created_desc; Type: INDEX; Schema: public; Owner: postgres
--
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='idx_containers_created_desc' AND relkind='i') THEN
    CREATE INDEX idx_containers_created_desc ON public.containers USING btree (created_at DESC);
  END IF;
END;
$$ LANGUAGE plpgsql;


--
-- Name: idx_containers_type_status; Type: INDEX; Schema: public; Owner: postgres
--
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='idx_containers_type_status' AND relkind='i') THEN
    CREATE INDEX idx_containers_type_status ON public.containers USING btree (container_type, status);
  END IF;
END;
$$ LANGUAGE plpgsql;


--
-- Name: idx_ftm_container; Type: INDEX; Schema: public; Owner: postgres
--
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='idx_ftm_container' AND relkind='i') THEN
    CREATE INDEX idx_ftm_container ON public.fish_tank_memberships USING btree (container_id);
  END IF;
END;
$$ LANGUAGE plpgsql;


--
-- Name: idx_ftm_fish; Type: INDEX; Schema: public; Owner: postgres
--
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='idx_ftm_fish' AND relkind='i') THEN
    CREATE INDEX idx_ftm_fish ON public.fish_tank_memberships USING btree (fish_id);
  END IF;
END;
$$ LANGUAGE plpgsql;


--
-- Name: idx_ftm_fish_id; Type: INDEX; Schema: public; Owner: postgres
--
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='idx_ftm_fish_id' AND relkind='i') THEN
    CREATE INDEX idx_ftm_fish_id ON public.fish_tank_memberships USING btree (fish_id);
  END IF;
END;
$$ LANGUAGE plpgsql;


--
-- Name: idx_vfltc_fish; Type: INDEX; Schema: public; Owner: postgres
--
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='idx_vfltc_fish' AND relkind='i') THEN
    CREATE INDEX idx_vfltc_fish ON public.fish_tank_memberships USING btree (fish_id);
  END IF;
END;
$$ LANGUAGE plpgsql;


--
-- Name: uq_containers_tank_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_containers_tank_code ON public.containers USING btree (tank_code) WHERE (tank_code IS NOT NULL);


--
-- Name: uq_ftm_fish_open; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_ftm_fish_open ON public.fish_tank_memberships USING btree (fish_id) WHERE (left_at IS NULL);


--
-- Name: containers trg_containers_activate_on_label; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_containers_activate_on_label BEFORE UPDATE OF label ON public.containers FOR EACH ROW EXECUTE FUNCTION public.trg_containers_activate_on_label();


--
-- Name: containers trg_containers_status_history; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_containers_status_history AFTER UPDATE OF status ON public.containers FOR EACH ROW EXECUTE FUNCTION public.trg_log_container_status();


--
-- Name: containers containers_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='containers_request_id_fkey') THEN
    ALTER TABLE ONLY public.containers ADD CONSTRAINT containers_request_id_fkey FOREIGN KEY (request_id) REFERENCES public.tank_requests (id_uuid) ON DELETE SET NULL;
  END IF;
END;
$$ LANGUAGE plpgsql;


--
-- Name: fish_tank_memberships fish_tank_memberships_container_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fish_tank_memberships_container_id_fkey') THEN
    ALTER TABLE ONLY public.fish_tank_memberships ADD CONSTRAINT fish_tank_memberships_container_id_fkey FOREIGN KEY (container_id) REFERENCES public.containers (id_uuid) ON DELETE RESTRICT;
  END IF;
END;
$$ LANGUAGE plpgsql;


--
-- Name: fish_tank_memberships fish_tank_memberships_fish_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fish_tank_memberships_fish_id_fkey') THEN
    ALTER TABLE ONLY public.fish_tank_memberships ADD CONSTRAINT fish_tank_memberships_fish_id_fkey FOREIGN KEY (fish_id) REFERENCES public.fish (id) ON DELETE CASCADE;
  END IF;
END;
$$ LANGUAGE plpgsql;


--
-- PostgreSQL database dump complete
--

