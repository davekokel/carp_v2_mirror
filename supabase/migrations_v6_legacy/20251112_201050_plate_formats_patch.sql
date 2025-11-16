BEGIN;

-- 0) Create the table if it was removed earlier
CREATE TABLE IF NOT EXISTS public.plate_formats (
  code        text PRIMARY KEY,
  name        text NOT NULL,
  n_rows      int  NOT NULL CHECK (n_rows > 0),
  n_cols      int  NOT NULL CHECK (n_cols > 0),
  -- the following may get added below if they already existed we keep as-is
  label_style text,
  well_order  text,
  created_at  timestamptz
);

-- 1) Ensure columns exist with proper defaults
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='plate_formats' AND column_name='label_style'
  ) THEN
    ALTER TABLE public.plate_formats ADD COLUMN label_style text NOT NULL DEFAULT 'A01';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='plate_formats' AND column_name='well_order'
  ) THEN
    ALTER TABLE public.plate_formats ADD COLUMN well_order text NOT NULL DEFAULT 'row';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='plate_formats' AND column_name='created_at'
  ) THEN
    ALTER TABLE public.plate_formats ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
  END IF;
END$$;

-- 2) Seed / upsert exactly the three formats you want
INSERT INTO public.plate_formats (code, name, n_rows, n_cols, label_style, well_order)
VALUES
  ('bruker_1x6',                 'Bruker mount (1×6)',                  6,  1, 'A01', 'row'),
  ('coverslip_round_25mm_3x10',  'Coverslip round 25mm (3×10)',        10,  3, 'A01', 'row'),
  ('96',                         '96-well (8×12)',                       8, 12, 'A01', 'row')
ON CONFLICT (code) DO UPDATE
SET name        = EXCLUDED.name,
    n_rows      = EXCLUDED.n_rows,
    n_cols      = EXCLUDED.n_cols,
    label_style = EXCLUDED.label_style,
    well_order  = EXCLUDED.well_order;

COMMIT;
