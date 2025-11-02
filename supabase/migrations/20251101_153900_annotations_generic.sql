-- 20251101_153900_annotations_generic.sql
BEGIN;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS public.annotations (
  kind_code       text PRIMARY KEY,
  value_type      text NOT NULL CHECK (value_type IN ('number','text','bool','json')),
  unit            text,
  description     text,
  min_num         numeric,
  max_num         numeric,
  allowed_values  jsonb,
  created_by      text,
  created_at      timestamptz NOT NULL DEFAULT now()
);

INSERT INTO public.annotations (kind_code, value_type, unit, description) VALUES
  ('green_intensity','number','au','Green channel intensity'),
  ('red_intensity','number','au','Red channel intensity'),
  ('green_frequency','number','%','Percent of embryos/larvae with green signal'),
  ('red_frequency','number','%','Percent of embryos/larvae with red signal'),
  ('n_animals','number','count','Number of embryos/larvae scored'),
  ('health','text',NULL,'Qualitative health/phenotype note'),
  ('notes','text',NULL,'Freeform note')
ON CONFLICT (kind_code) DO NOTHING;

CREATE TABLE IF NOT EXISTS public.join_annotations (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target_table   text    NOT NULL,                         -- e.g. 'clutch_instances','tanks','fish','crosses'
  target_id      uuid    NOT NULL,                         -- references <target_table>.id (validated by trigger below)
  kind_code      text    NOT NULL REFERENCES public.annotations(kind_code),
  value_num      numeric,
  value_text     text,
  value_bool     boolean,
  value_json     jsonb,
  value_unit     text,
  method         text,
  sample_size    integer,
  created_by     text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT join_annotations_value_ck CHECK (
    ((value_num  IS NOT NULL)::int +
     (value_text IS NOT NULL)::int +
     (value_bool IS NOT NULL)::int +
     (value_json IS NOT NULL)::int) >= 1
  )
);

CREATE INDEX IF NOT EXISTS ix_join_annotations_target_kind ON public.join_annotations (target_table, target_id, kind_code, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_join_annotations_kind ON public.join_annotations (kind_code);
CREATE INDEX IF NOT EXISTS ix_join_annotations_created_at ON public.join_annotations (created_at DESC);

CREATE OR REPLACE FUNCTION public.enforce_join_annotations_target_fk()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  ok int;
  sql text;
BEGIN
  sql := format('select 1 from %I.%I where id = $1', 'public', NEW.target_table);
  EXECUTE sql USING NEW.target_id INTO ok;
  IF ok IS DISTINCT FROM 1 THEN
    RAISE EXCEPTION 'join_annotations: target % not found for table %', NEW.target_id, NEW.target_table;
  END IF;
  RETURN NEW;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgname = 'trg_enforce_join_annotations_fk'
  ) THEN
    CREATE TRIGGER trg_enforce_join_annotations_fk
      BEFORE INSERT ON public.join_annotations
      FOR EACH ROW EXECUTE PROCEDURE public.enforce_join_annotations_f();
  END IF;
END$$;

CREATE OR REPLACE VIEW public.v_annotations_latest AS
SELECT DISTINCT ON (ja.target_table, ja.target_id, ja.kind_code)
       ja.target_table,
       ja.target_id,
       ja.kind_code,
       a.value_type,
       a.unit AS catalog_unit,
       a.description AS kind_description,
       ja.value_num,
       ja.value_text,
       ja.value_bool,
       ja.value_json,
       COALESCE(ja.value_unit, a.unit) AS value_unit,
       ja.method,
       ja.sample_size,
       ja.created_by,
       ja.created_at
FROM public.join_annotations AS ja
JOIN public.annotations AS a
  ON a.kind_code = ja.kind_code
ORDER BY ja.target_table, ja.target_id, ja.kind_code, ja.created_at DESC, ja.id DESC;

CREATE OR REPLACE VIEW public.v_clutch_annotations AS
SELECT
  ci.clutch_instance_id,
  ci.clutch_code,
  l.kind_code,
  l.value_type,
  l.value_num,
  l.value_text,
  l.value_bool,
  l.value_json,
  l.value_unit,
  l.method,
  l.sample_size,
  l.created_by,
  l.created_at
FROM (
  SELECT id AS clutch_instance_id, clutch_instance_code AS clutch_code
  FROM public.clutch_instances
) ci
LEFT JOIN public.v_annotations_lest l
  ON l.target_table = 'clutch_instances'
 AND l.target_id    = ci.clutch_instance_id;

CREATE OR REPLACE VIEW public.v_clutch_annotations_pivot AS
WITH la AS (
  SELECT *
  FROM public.v_annotations_lest
  WHERE target_table = 'clutch_instances'
),
ci AS (
  SELECT id AS clutch_instance_id, clutch_instance_code AS clutch_code
  FROM public.clutch_instances
)
SELECT
  ci.clutch_code,
  MAX(CASE WHEN la.kind_code='green_intensity' THEN la.value_num END) AS green_intensity,
  MAX(CASE WHEN la.kind_code='red_intensity'   THEN la.value_num END) AS red_intensity,
  MAX(CASE WHEN la.kind_code='green_frequency' THEN la.value_num END) AS green_frequency,
  MAX(CASE WHEN la.kind_code='red_frequency'   THEN la.value_num END) AS red_frequency,
  MAX(CASE WHEN la.kind_code='n_animals'       THEN la.value_num END) AS n_animals,
  MAX(CASE WHEN la.kind_code='health'          THEN la.value_text END) AS health,
  MAX(CASE WHEN la.kind_code='notes'           THEN la.value_text END) AS notes,
  MAX(la.created_at) AS annotations_last_at
FROM ci
LEFT JOIN la
  ON la.target_id = ci.clutch_instance_id
GROUP BY ci.clutch_code;

COMMIT;
