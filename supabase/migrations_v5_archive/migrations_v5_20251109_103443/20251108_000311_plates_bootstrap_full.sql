BEGIN;

-- Clean up old mounts artifacts if present (safe to skip)
DROP VIEW IF EXISTS public.v_mounts;
DROP TABLE IF EXISTS public.mount_slots;
DROP TABLE IF EXISTS public.mounts;

-- 1) plate_formats (idempotent)
CREATE TABLE IF NOT EXISTS public.plate_formats (
  code       text PRIMARY KEY,
  name       text,
  n_rows     int  NOT NULL,
  n_cols     int  NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- seed formats (upsert)
INSERT INTO public.plate_formats(code,name,n_rows,n_cols) VALUES
  ('bruker_mount','Bruker mount',6,1),
  ('coverslip_25mm','Coverslip Ø25mm',10,3),
  ('plate_96_well','96-well plate',8,12)
ON CONFLICT (code) DO UPDATE
SET name=EXCLUDED.name, n_rows=EXCLUDED.n_rows, n_cols=EXCLUDED.n_cols;

-- 2) plates (idempotent)
CREATE TABLE IF NOT EXISTS public.plates (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plate_code  text UNIQUE,
  format_code text NOT NULL REFERENCES public.plate_formats(code),
  plate_name  text,
  created_by  text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- seq + default for plate_code (guarded)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relkind='S' AND relname='seq_plate_code') THEN
    CREATE SEQUENCE public.seq_plate_code;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='plates'
      AND column_name='plate_code' AND column_default IS NOT NULL
  ) THEN
    ALTER TABLE public.plates
    ALTER COLUMN plate_code SET DEFAULT (
      'PLT-'||to_char(now(),'YYYYMMDD')||'-'||lpad(nextval('public.seq_plate_code')::text, 4, '0')
    );
  END IF;
END$$;

-- trigger to assign plate_code/created_at on insert
CREATE OR REPLACE FUNCTION public.plates_bi_assign_code()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.plate_code IS NULL OR NEW.plate_code = '' THEN
    NEW.plate_code := 'PLT-'||to_char(now(),'YYYYMMDD')||'-'||lpad(nextval('public.seq_plate_code')::text, 4, '0');
  END IF;
  IF NEW.created_at IS NULL THEN
    NEW.created_at := now();
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_plates_bi_assign_code ON public.plates;
CREATE TRIGGER trg_plates_bi_assign_code
BEFORE INSERT ON public.plates
FOR EACH ROW EXECUTE FUNCTION public.plates_bi_assign_code();

-- 3) plate_slots (idempotent)
CREATE TABLE IF NOT EXISTS public.plate_slots (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plate_id           uuid NOT NULL REFERENCES public.plates(id) ON DELETE CASCADE,
  row_idx            int  NOT NULL,
  col_idx            int  NOT NULL,
  treated_clutch_id  uuid REFERENCES public.treated_clutches(id),
  fish_code          text,
  orientation        text,
  created_at         timestamptz NOT NULL DEFAULT now()
);

-- unique well per plate
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='plate_slots' AND indexname='uq_plate_slots_loc'
  ) THEN
    CREATE UNIQUE INDEX uq_plate_slots_loc ON public.plate_slots(plate_id, row_idx, col_idx);
  END IF;
END$$;

-- 4) DROP the dependent view first, then (re)create row_letter, then recreate the view
DROP VIEW IF EXISTS public.v_plate_layout;

-- drop old signature if present to allow parameter rename
DROP FUNCTION IF EXISTS public.row_letter(integer);

-- helper: row_letter(1)='A', …
CREATE FUNCTION public.row_letter(p_row integer)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT chr(64 + GREATEST(1, LEAST(26, p_row)))
$$;

-- 5) v_plate_layout
CREATE VIEW public.v_plate_layout AS
SELECT
  p.plate_code,
  COALESCE(p.plate_name,'') AS plate_name,
  p.format_code,
  pf.n_rows,
  pf.n_cols,
  s.row_idx,
  s.col_idx,
  public.row_letter(s.row_idx)                                   AS row_letter,
  (public.row_letter(s.row_idx) || lpad(s.col_idx::text,2,'0'))  AS well_label,
  s.treated_clutch_id,
  COALESCE(tc.treated_clutch_code,'')                            AS treated_clutch_code,
  COALESCE(s.fish_code,'')                                       AS fish_code,
  COALESCE(s.orientation,'')                                     AS orientation,
  s.created_at
FROM public.plate_slots s
JOIN public.plates        p  ON p.id = s.plate_id
JOIN public.plate_formats pf ON pf.code = p.format_code
LEFT JOIN public.treated_clutches tc ON tc.id = s.treated_clutch_id
ORDER BY p.plate_code, s.row_idx, s.col_idx;

COMMIT;
