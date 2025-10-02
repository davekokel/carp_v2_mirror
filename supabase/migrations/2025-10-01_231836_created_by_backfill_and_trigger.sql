DO $$
DECLARE has_operator_col boolean;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='load_log_fish' AND column_name='operator'
  ) INTO has_operator_col;

  IF has_operator_col THEN
    WITH latest AS (
      SELECT DISTINCT ON (llf.fish_id)
        llf.fish_id, NULLIF(TRIM(llf.operator),'') AS op
      FROM public.load_log_fish llf
      ORDER BY llf.fish_id, llf.logged_at DESC
    )
    UPDATE public.fish f
    SET created_by = l.op
    FROM latest l
    WHERE f.id_uuid = l.fish_id
      AND l.op IS NOT NULL
      AND (f.created_by IS NULL OR TRIM(f.created_by) = '');

    CREATE OR REPLACE FUNCTION public.tg_update_fish_created_by()
    RETURNS TRIGGER AS $f$
    BEGIN
      IF NEW.operator IS NOT NULL AND TRIM(NEW.operator) <> '' THEN
        UPDATE public.fish
        SET created_by = NEW.operator
        WHERE id_uuid = NEW.fish_id
          AND (created_by IS NULL OR TRIM(created_by) = '');
      END IF;
      RETURN NEW;
    END
    $f$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS trg_update_fish_created_by ON public.load_log_fish;
    CREATE TRIGGER trg_update_fish_created_by
    AFTER INSERT ON public.load_log_fish
    FOR EACH ROW EXECUTE FUNCTION public.tg_update_fish_created_by();
  END IF;
END$$;
