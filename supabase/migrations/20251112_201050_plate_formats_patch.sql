BEGIN;

-- Add the new columns if they don't exist
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
    ALTER TABLE public.plate_formats ADD COLUMN well_order  text NOT NULL DEFAULT 'row';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='plate_formats' AND column_name='created_at'
  ) THEN
    ALTER TABLE public.plate_formats ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
  END IF;
END$$;

-- Seed / upsert the three formats
INSERT INTO public.plate_formats (code, name, n_rows, n_cols, label_style, well_order)
VALUES
  ('bruker_1x6',                 'Bruker mount (1×6)',                  6,  1, 'A01', 'row'),
  ('coverslip_round_25mm_3x10',  'Coverslip round 25mm (3×10)',        10,  3, 'A01', 'row'),
  ('96',                         '96-well (8×12)',                       8, 12, 'A01', 'row')
ON CONFLICT (code) DO UPDATE
SET name       = EXCLUDED.name,
    n_rows     = EXCLUDED.n_rows,
    n_cols     = EXCLUDED.n_cols,
    label_style= EXCLUDED.label_style,
    well_order = EXCLUDED.well_order;

COMMIT;
