BEGIN;

-- 0) ensure legacy mounts are gone (ignore if they never existed)
DROP VIEW  IF EXISTS public.v_mounts CASCADE;
DROP TABLE IF EXISTS public.mount_slots CASCADE;
DROP TABLE IF EXISTS public.mounts CASCADE;

-- 1) plate_formats
CREATE TABLE IF NOT EXISTS public.plate_formats (
  code    text PRIMARY KEY,
  name    text NOT NULL,
  n_rows  int  NOT NULL CHECK (n_rows BETWEEN 1 AND 24),
  n_cols  int  NOT NULL CHECK (n_cols BETWEEN 1 AND 24)
);

-- 2) plates
CREATE TABLE IF NOT EXISTS public.plates (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plate_code  text UNIQUE NOT NULL,
  format_code text NOT NULL REFERENCES public.plate_formats(code) ON DELETE RESTRICT,
  plate_name  text,
  created_by  text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE SEQUENCE IF NOT EXISTS public.seq_plate_code;

CREATE OR REPLACE FUNCTION public.plate_code_next()
RETURNS text LANGUAGE sql AS $$
  SELECT 'PLT-'||to_char(now(),'YYYYMMDD')||'-'||lpad(nextval('public.seq_plate_code')::text,6,'0')
$$;

CREATE OR REPLACE FUNCTION public.plates_bi_assign_code()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.plate_code IS NULL OR NEW.plate_code='' THEN
    NEW.plate_code := public.plate_code_next();
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_plates_bi_assign_code ON public.plates;
CREATE TRIGGER trg_plates_bi_assign_code
BEFORE INSERT ON public.plates
FOR EACH ROW EXECUTE FUNCTION public.plates_bi_assign_code();

-- 3) row index -> letter (A..)
CREATE OR REPLACE FUNCTION public.row_letter(i int)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT chr(64 + i)
$$;

-- 4) plate_slots (create if missing)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='plate_slots'
  ) THEN
    CREATE TABLE public.plate_slots (
      id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      plate_id      uuid NOT NULL REFERENCES public.plates(id) ON DELETE CASCADE,
      row_idx       int  NOT NULL CHECK (row_idx BETWEEN 1 AND 24),
      col_idx       int  NOT NULL CHECK (col_idx BETWEEN 1 AND 24),
      -- A01/A02 with LPAD
      well_label    text GENERATED ALWAYS AS (public.row_letter(row_idx) || lpad(col_idx::text,2,'0')) STORED,
      treated_clutch_id uuid REFERENCES public.treated_clutches(id) ON DELETE SET NULL,
      fish_code     text,
      orientation   text,
      created_at    timestamptz NOT NULL DEFAULT now(),
      UNIQUE(plate_id, row_idx, col_idx)
    );
  END IF;
END$$;

-- orientation constraint (replace if present)
ALTER TABLE public.plate_slots
  DROP CONSTRAINT IF EXISTS ck_plate_slots_orientation;

ALTER TABLE public.plate_slots
  ADD CONSTRAINT ck_plate_slots_orientation
  CHECK (
    orientation IS NULL OR orientation IN (
      'dorsal_head_top',
      'lateral_head_left',
      'lateral_head_right',
      'head_down_dorsal_top'
    )
  );

-- rebuild index on well_label
DROP INDEX IF EXISTS ix_plate_slots_label;
CREATE INDEX IF NOT EXISTS ix_plate_slots_label
  ON public.plate_slots(plate_id, well_label);

-- 5) slot generation function + trigger (idempotent)
CREATE OR REPLACE FUNCTION public.generate_slots_for_plate(p_plate_id uuid)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
  rrows int; rcols int;
BEGIN
  SELECT pf.n_rows, pf.n_cols
    INTO rrows, rcols
  FROM public.plates p
  JOIN public.plate_formats pf ON pf.code = p.format_code
  WHERE p.id = p_plate_id;

  IF rrows IS NULL OR rcols IS NULL THEN
    RAISE EXCEPTION 'Unknown plate or format for plate_id %', p_plate_id;
  END IF;

  INSERT INTO public.plate_slots (plate_id, row_idx, col_idx)
  SELECT p_plate_id, r, c
  FROM generate_series(1, rrows) r
  CROSS JOIN generate_series(1, rcols) c
  ON CONFLICT (plate_id, row_idx, col_idx) DO NOTHING;
END
$$;

CREATE OR REPLACE FUNCTION public.plates_ai_generate_slots()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM public.generate_slots_for_plate(NEW.id);
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_plates_ai_generate_slots ON public.plates;
CREATE TRIGGER trg_plates_ai_generate_slots
AFTER INSERT ON public.plates
FOR EACH ROW EXECUTE FUNCTION public.plates_ai_generate_slots();

-- 6) layout view (uses A01/A02 label)
DROP VIEW IF EXISTS public.v_plate_layout;
CREATE VIEW public.v_plate_layout AS
SELECT
  p.plate_code,
  p.plate_name,
  p.format_code,
  pf.n_rows,
  pf.n_cols,
  s.row_idx,
  s.col_idx,
  public.row_letter(s.row_idx) AS row_letter,
  s.well_label,                           -- A01 style
  s.treated_clutch_id,
  COALESCE(tc.treated_clutch_code,'') AS treated_clutch_code,
  s.fish_code,
  COALESCE(s.orientation,'') AS orientation,
  s.created_at
FROM public.plate_slots s
JOIN public.plates        p  ON p.id = s.plate_id
JOIN public.plate_formats pf ON pf.code = p.format_code
LEFT JOIN public.treated_clutches tc ON tc.id = s.treated_clutch_id
ORDER BY p.plate_code, s.row_idx, s.col_idx;

-- 7) seed formats
INSERT INTO public.plate_formats(code, name, n_rows, n_cols) VALUES
  ('bruker_mount',         'Bruker mount (1×6 as 6×1 grid)', 6, 1),
  ('coverslip_round_25mm', 'Coverslip round 25mm (10×3)',    10, 3),
  ('plate_96_well',        '96-well plate (8×12)',            8, 12)
ON CONFLICT (code) DO NOTHING;

COMMIT;
