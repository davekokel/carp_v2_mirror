BEGIN;

-- 1) Backfill existing plate_code values to PLT-YYYYMMDD-#NN where not already in that pattern
WITH numbered AS (
  SELECT
    id,
    to_char(created_at::date, 'YYYYMMDD') AS d,
    row_number() OVER (
      PARTITION BY created_at::date
      ORDER BY created_at, id
    ) AS n
  FROM public.plates
  WHERE plate_code IS NULL
     OR plate_code = ''
     OR plate_code NOT LIKE 'PLT-%'
)
UPDATE public.plates p
SET plate_code = format('PLT-%s-#%02s', numbered.d, numbered.n)
FROM numbered
WHERE p.id = numbered.id;

-- 2) Create/replace a trigger function that assigns PLT-YYYYMMDD-#NN
CREATE OR REPLACE FUNCTION public.trg_plate_code_plt_yyyymmdd()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  d text;
  n int;
BEGIN
  -- Only set/override if code is empty or legacy-style (format% etc.)
  IF NEW.plate_code IS NULL OR NEW.plate_code = '' OR NEW.plate_code LIKE 'format%' THEN
    d := to_char(COALESCE(NEW.created_at, now())::date, 'YYYYMMDD');

    SELECT COALESCE(
             MAX( (regexp_match(plate_code, 'PLT-'||d||'-#(\\d+)$'))[1]::int ),
             0
           )
      INTO n
      FROM public.plates
     WHERE plate_code LIKE 'PLT-'||d||'-%';

    NEW.plate_code := format('PLT-%s-#%02s', d, n + 1);
  END IF;

  RETURN NEW;
END
$$;

-- 3) Attach the trigger; name it so it runs after any older triggers
DROP TRIGGER IF EXISTS zzz_plate_code_plt_yyyymmdd ON public.plates;
CREATE TRIGGER zzz_plate_code_plt_yyyymmdd
BEFORE INSERT ON public.plates
FOR EACH ROW
EXECUTE FUNCTION public.trg_plate_code_plt_yyyymmdd();

COMMIT;
