BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.annotations'::regclass
      AND contype = 'u'
      AND conname = 'uq_annotations_kind_code'
  ) THEN
    ALTER TABLE public.annotations
      ADD CONSTRAINT uq_annotations_kind_code UNIQUE (kind_code);
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.join_annotations'::regclass
      AND contype = 'f'
      AND conname = 'fk_join_annotations_kind_code'
  ) THEN
    IF EXISTS (
      SELECT 1
      FROM public.join_annotations ja
      LEFT JOIN public.annotations a
        ON a.kind_code = ja.kind_code
      WHERE ja.kind_code IS NOT NULL
        AND a.kind_code IS NULL
    ) THEN
      RAISE EXCEPTION
        'Cannot add FK join_annotations.kind_code -> annotations.kind_code; missing annotation kind(s)';
    END IF;

    ALTER TABLE public.join_annotations
      ADD CONSTRAINT fk_join_annotations_kind_code
        FOREIGN KEY (kind_code)
        REFERENCES public.annotations(kind_code);
  END IF;
END$$;

DO $$
BEGIN
  IF to_regclass('public.plates') IS NOT NULL
     AND to_regclass('public.plate_formats') IS NOT NULL THEN

    IF EXISTS (
      SELECT 1
      FROM public.plates p
      LEFT JOIN public.plate_formats pf
        ON pf.code = p.format_code
      WHERE p.format_code IS NOT NULL
        AND pf.code IS NULL
    ) THEN
      RAISE EXCEPTION
        'Cannot add FK plates.format_code -> plate_formats.code; missing plate_format code(s)';
    END IF;

    IF NOT EXISTS (
      SELECT 1
      FROM pg_constraint
      WHERE conrelid = 'public.plates'::regclass
        AND contype = 'f'
        AND conname = 'fk_plates_format_code'
    ) THEN
      ALTER TABLE public.plates
        ADD CONSTRAINT fk_plates_format_code
          FOREIGN KEY (format_code)
          REFERENCES public.plate_formats(code);
    END IF;

  END IF;
END$$;

COMMIT;
