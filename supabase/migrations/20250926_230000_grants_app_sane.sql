-- Migration: app grants hardening (idempotent, safe to re-run)
-- Requires: role carp_app already exists.
-- Run as owner/superuser (postgres) in database "postgres".

-- Basic access
GRANT CONNECT ON DATABASE postgres TO carp_app;
GRANT USAGE   ON SCHEMA public   TO carp_app;

-- Existing relations (tables/views/foreign tables)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES    IN SCHEMA public TO carp_app;
GRANT USAGE  ON ALL SEQUENCES IN SCHEMA public        TO carp_app;

-- Future relations owned by postgres (so new objects are accessible automatically)
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO carp_app;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT USAGE ON SEQUENCES TO carp_app;
