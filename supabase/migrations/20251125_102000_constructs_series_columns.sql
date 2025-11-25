BEGIN;

ALTER TABLE public.constructs
  ADD COLUMN series_prefix text,
  ADD COLUMN series_number int;

ALTER TABLE public.constructs
  ADD CONSTRAINT constructs_series_consistency CHECK (
    (series_prefix IS NULL AND series_number IS NULL)
    OR
    (series_prefix IS NOT NULL AND series_number IS NOT NULL)
  );

COMMIT;
