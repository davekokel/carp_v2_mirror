BEGIN;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE TABLE IF NOT EXISTS raw.dyes_upload (
  dye_name    text,
  alt_names   text,
  excitation_nm text,
  emission_nm   text,
  notes       text
);
COMMIT;
