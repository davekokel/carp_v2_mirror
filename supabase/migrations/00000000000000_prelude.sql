-- Ensure schema + sequences exist before any SQL-language functions are created
SET search_path = public, pg_catalog;
CREATE SCHEMA IF NOT EXISTS public;

-- Sequences referenced by functions/views
CREATE SEQUENCE IF NOT EXISTS public.tank_counters;
CREATE SEQUENCE IF NOT EXISTS public.seq_tank_code;

-- auto-generated: sequences referenced by baseline
CREATE SEQUENCE IF NOT EXISTS public.seq_tank_code;
CREATE SEQUENCE IF NOT EXISTS public.tank_counters;
