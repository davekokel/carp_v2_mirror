BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS public.fluors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_name text NOT NULL,
  nickname text,
  ex_nm integer,
  em_nm integer,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_fluors_canonical UNIQUE (canonical_name),
  CONSTRAINT uq_fluors_nickname UNIQUE (nickname)
);

CREATE TABLE IF NOT EXISTS public.fluor_aliases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fluor_id uuid NOT NULL REFERENCES public.fluors(id) ON DELETE CASCADE,
  alias text NOT NULL,
  CONSTRAINT uq_fluor_alias UNIQUE (alias)
);

CREATE TABLE IF NOT EXISTS raw.fluors_upload (
  fluor_nickname text,
  alt_names text,
  excitation_nm text,
  emission_nm text,
  notes text
);

CREATE OR REPLACE FUNCTION public.upsert_fluors_from_raw() RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
  r record;
  v_canonical text;
  v_nickname  text;
  v_ex int;
  v_em int;
  v_id uuid;
  v_alias text;
BEGIN
  FOR r IN
    SELECT
      NULLIF(trim(fluor_nickname), '') AS fluor_nickname,
      COALESCE(alt_names,'') AS alt_names,
      NULLIF(trim(excitation_nm), '') AS excitation_nm,
      NULLIF(trim(emission_nm), '') AS emission_nm,
      NULLIF(trim(notes), '') AS notes
    FROM raw.fluors_upload
  LOOP
    v_nickname  := r.fluor_nickname;
    v_canonical := r.fluor_nickname;
    IF v_canonical IS NULL THEN CONTINUE; END IF;

    BEGIN
      v_ex := CASE WHEN r.excitation_nm ~ '^[0-9]+$' THEN r.excitation_nm::int END;
      v_em := CASE WHEN r.emission_nm  ~ '^[0-9]+$' THEN r.emission_nm::int  END;
    EXCEPTION WHEN others THEN
      v_ex := NULL; v_em := NULL;
    END;

    INSERT INTO public.fluors (canonical_name, nickname, ex_nm, em_nm, notes)
    VALUES (v_canonical, v_nickname, v_ex, v_em, r.notes)
    ON CONFLICT (canonical_name) DO UPDATE
      SET nickname = COALESCE(EXCLUDED.nickname, public.fluors.nickname),
          ex_nm    = COALESCE(EXCLUDED.ex_nm,    public.fluors.ex_nm),
          em_nm    = COALESCE(EXCLUDED.em_nm,    public.fluors.em_nm),
          notes    = COALESCE(EXCLUDED.notes,    public.fluors.notes)
    RETURNING id INTO v_id;

    IF v_id IS NULL THEN
      SELECT id INTO v_id FROM public.fluors WHERE canonical_name = v_canonical;
    END IF;

    IF v_nickname IS NOT NULL AND v_nickname <> '' THEN
      INSERT INTO public.fluor_aliases (fluor_id, alias)
      VALUES (v_id, v_nickname)
      ON CONFLICT (alias) DO NOTHING;
    END IF;

    IF r.alt_names IS NOT NULL AND r.alt_names <> '' THEN
      FOR v_alias IN
        SELECT DISTINCT NULLIF(trim(x), '') AS alias
        FROM regexp_split_to_table(
          replace(replace(replace(replace(r.alt_names, '/', ';'), ',', ';'), '|', ';'), '; ', ';')
        , ';') AS x
      LOOP
        IF v_alias IS NULL THEN CONTINUE; END IF;
        INSERT INTO public.fluor_aliases (fluor_id, alias)
        VALUES (v_id, v_alias)
        ON CONFLICT (alias) DO NOTHING;
      END LOOP;
    END IF;
  END LOOP;
END$$;

COMMIT;
