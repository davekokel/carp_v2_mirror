DO $$
BEGIN
  IF to_regclass('public.fish') IS NOT NULL THEN

    BEGIN
      ALTER TABLE public.fish ADD COLUMN IF NOT EXISTS fish_code text;
    EXCEPTION WHEN duplicate_column THEN
    END;

    CREATE OR REPLACE FUNCTION public.gen_fish_code()
    RETURNS trigger
    LANGUAGE plpgsql
    AS $FN$
    DECLARE
      yy       text := to_char(current_date, 'YY');
      prefix   text := 'FSH-'||yy||'-';
      latest   text;
      num_part int;
      letter   text;
    BEGIN
      IF NEW.fish_code IS NOT NULL AND NEW.fish_code <> '' THEN
        RETURN NEW;
      END IF;

      SELECT max(fish_code)
      INTO latest
      FROM public.fish
      WHERE fish_code LIKE prefix || '%'
        AND fish_code ~ ('^FSH-'||yy||'-[0-9]{2}[A-Z]$');

      IF latest IS NULL THEN
        NEW.fish_code := prefix || '01A';
        RETURN NEW;
      END IF;

      num_part := substring(latest from 8 for 2)::int;
      letter   := substring(latest from 10 for 1);

      IF letter < 'Z' THEN
        NEW.fish_code := prefix || lpad(num_part::text, 2, '0') || chr(ascii(letter) + 1);
      ELSE
        NEW.fish_code := prefix || lpad((num_part + 1)::text, 2, '0') || 'A';
      END IF;

      RETURN NEW;
    END;
    $FN$;

    DROP TRIGGER IF EXISTS fish_code_auto ON public.fish;
    CREATE TRIGGER fish_code_auto
    BEFORE INSERT ON public.fish
    FOR EACH ROW
    EXECUTE FUNCTION public.gen_fish_code();

  END IF;
END
$$;
