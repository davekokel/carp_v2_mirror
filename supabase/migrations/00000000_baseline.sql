BEGIN;

CREATE SCHEMA IF NOT EXISTS public;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS public.fluors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fluor_code text UNIQUE NOT NULL,
  fluor_name text,
  excitation_nm integer,
  emission_nm integer,
  alt_names text[],
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.tags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tag_code text UNIQUE NOT NULL,
  tag_name text,
  alt_names text[],
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.rnas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rna_code text UNIQUE NOT NULL,
  nickname text,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.fusions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fluor_id uuid NOT NULL REFERENCES public.fluors(id),
  tag_id uuid NULL REFERENCES public.tags(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname='public' AND tablename='fusions' AND indexname='uq_fusions_fluor_tag_notnull'
  ) THEN
    CREATE UNIQUE INDEX uq_fusions_fluor_tag_notnull
      ON public.fusions(fluor_id, tag_id)
      WHERE tag_id IS NOT NULL;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname='public' AND tablename='fusions' AND indexname='uq_fusions_fluor_when_tag_null'
  ) THEN
    CREATE UNIQUE INDEX uq_fusions_fluor_when_tag_null
      ON public.fusions(fluor_id)
      WHERE tag_id IS NULL;
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS public.join_rna_fusions (
  rna_id uuid NOT NULL REFERENCES public.rnas(id) ON DELETE CASCADE,
  fusion_id uuid NOT NULL REFERENCES public.fusions(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (rna_id, fusion_id)
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='alias_target_kind') THEN
    CREATE TYPE public.alias_target_kind AS ENUM ('fluor','tag','dye','rna','plasmid','fish','tank','cross','clutch_inst','treated_clutch');
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS public.join_aliases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  target_kind public.alias_target_kind NOT NULL,
  target_id uuid NOT NULL,
  alias text NOT NULL,
  alias_norm text GENERATED ALWAYS AS (lower(btrim(alias))) STORED,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (target_kind, target_id, alias_norm)
);

CREATE OR REPLACE FUNCTION public.enforce_join_aliases_fk() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  ok boolean := false;
BEGIN
  IF NEW.target_kind='fluor' THEN
    SELECT TRUE INTO ok FROM public.fluors WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='tag' THEN
    SELECT TRUE INTO ok FROM public.tags WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='rna' THEN
    SELECT TRUE INTO ok FROM public.rnas WHERE id=NEW.target_id;
  ELSE
    ok := TRUE;
  END IF;
  IF NOT ok THEN
    RAISE EXCEPTION 'join_aliases target_id % not found for kind %', NEW.target_id, NEW.target_kind;
  END IF;
  RETURN NEW;
END$$;

DROP TRIGGER IF EXISTS trg_enforce_join_aliases_fk ON public.join_aliases;
CREATE TRIGGER trg_enforce_join_aliases_fk
BEFORE INSERT OR UPDATE ON public.join_aliases
FOR EACH ROW EXECUTE FUNCTION public.enforce_join_aliases_fk();

CREATE OR REPLACE FUNCTION public.resolve_fluor_id(sym text) RETURNS uuid LANGUAGE sql STABLE AS $$
  WITH s AS (
    SELECT lower(btrim(sym)) AS k
  )
  SELECT id FROM public.fluors f JOIN s ON lower(f.fluor_code)=s.k OR lower(COALESCE(f.fluor_name,''))=s.k
  UNION
  SELECT ja.target_id FROM public.join_aliases ja JOIN s ON ja.alias_norm=s.k WHERE ja.target_kind='fluor'::public.alias_target_kind
  LIMIT 1
$$;

CREATE OR REPLACE FUNCTION public.resolve_tag_id(sym text) RETURNS uuid LANGUAGE sql STABLE AS $$
  WITH s AS (
    SELECT lower(btrim(sym)) AS k
  )
  SELECT id FROM public.tags t JOIN s ON lower(t.tag_code)=s.k OR lower(COALESCE(t.tag_name,''))=s.k
  UNION
  SELECT ja.target_id FROM public.join_aliases ja JOIN s ON ja.alias_norm=s.k WHERE ja.target_kind='tag'::public.alias_target_kind
  LIMIT 1
$$;

CREATE OR REPLACE FUNCTION public.resolve_fusion_id(combo text) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
  raw text := btrim(COALESCE(combo,''));
  leftp text;
  rightp text;
  fid uuid;
  tid uuid;
  existing uuid;
BEGIN
  IF raw='' THEN
    RETURN NULL;
  END IF;

  IF raw ILIKE '%::%' OR raw ~ '[:/@+]' THEN
    leftp  := split_part(regexp_replace(raw,'\s+','','g'),'::',1);
    rightp := split_part(regexp_replace(raw,'\s+','','g'),'::',2);
    IF rightp='' THEN
      leftp  := split_part(regexp_replace(raw,'\s+','','g'),'[:/@+]',1);
      rightp := split_part(regexp_replace(raw,'\s+','','g'),'[:/@+]',2);
    END IF;
    fid := public.resolve_fluor_id(leftp);
    IF fid IS NULL THEN
      fid := public.resolve_fluor_id(rightp);
      tid := public.resolve_tag_id(leftp);
    ELSE
      tid := public.resolve_tag_id(rightp);
    END IF;
  ELSE
    fid := public.resolve_fluor_id(raw);
    tid := NULL;
  END IF;

  IF fid IS NULL THEN
    RETURN NULL;
  END IF;

  SELECT id INTO existing
  FROM public.fusions
  WHERE fluor_id=fid AND ((tid IS NULL AND tag_id IS NULL) OR tag_id=tid)
  LIMIT 1;

  IF existing IS NOT NULL THEN
    RETURN existing;
  END IF;

  INSERT INTO public.fusions(fluor_id, tag_id) VALUES (fid, tid) ON CONFLICT DO NOTHING;

  SELECT id INTO existing
  FROM public.fusions
  WHERE fluor_id=fid AND ((tid IS NULL AND tag_id IS NULL) OR tag_id=tid)
  LIMIT 1;

  RETURN existing;
END$$;

DROP VIEW IF EXISTS public.v_rnas CASCADE;
CREATE VIEW public.v_rnas AS
WITH jf AS (
  SELECT
    j.rna_id,
    f.id AS fusion_id,
    fl.fluor_code,
    tg.tag_code
  FROM public.join_rna_fusions j
  JOIN public.fusions f ON f.id=j.fusion_id
  JOIN public.fluors fl ON fl.id=f.fluor_id
  LEFT JOIN public.tags tg ON tg.id=f.tag_id
),
agg AS (
  SELECT
    rna_id,
    (
      SELECT string_agg(s.fluor_code, ', ' ORDER BY s.fluor_code)
      FROM (SELECT DISTINCT fluor_code FROM jf x WHERE x.rna_id=jf.rna_id) s
    ) AS fluors,
    (
      SELECT COALESCE(string_agg(s.tag_code, ', ' ORDER BY s.tag_code),'')
      FROM (SELECT DISTINCT tag_code FROM jf x WHERE x.rna_id=jf.rna_id AND x.tag_code IS NOT NULL) s
    ) AS tags
  FROM jf
  GROUP BY rna_id
)
SELECT
  r.rna_code,
  r.nickname,
  r.notes,
  COALESCE(agg.fluors,'') AS fluors,
  COALESCE(agg.tags,'')   AS tags,
  r.created_at
FROM public.rnas r
LEFT JOIN agg ON agg.rna_id=r.id;

COMMIT;
