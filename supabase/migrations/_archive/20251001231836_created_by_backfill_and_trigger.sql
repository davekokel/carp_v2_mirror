DO $$
BEGIN
  IF to_regclass('public.fish') IS NULL THEN
    RAISE NOTICE 'Skip: fish missing';
    RETURN;
  END IF;

  IF to_regclass('public.load_log_fish') IS NOT NULL THEN
    -- optional fast backfill (if operator column exists)
    IF EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='load_log_fish' AND column_name='operator'
    ) THEN
      EXECUTE $SQL$
        UPDATE public.fish f
        SET created_by = llf.operator
        FROM (
          SELECT DISTINCT ON (fish_id) fish_id, operator
          FROM public.load_log_fish
          WHERE fish_id IS NOT NULL AND operator IS NOT NULL
          ORDER BY fish_id, logged_at ASC
        ) llf
        WHERE f.id = llf.fish_id AND (f.created_by IS NULL OR f.created_by = '')
      $SQL$;
    END IF;

    -- keep trigger idempotent
    EXECUTE 'DROP TRIGGER IF EXISTS trg_update_fish_created_by ON public.load_log_fish';
    EXECUTE $SQL$
      CREATE OR REPLACE FUNCTION public._on_load_log_fish_update_created_by()
      RETURNS trigger LANGUAGE plpgsql AS $FN$
      BEGIN
        IF NEW.fish_id IS NOT NULL AND (NEW.operator IS NOT NULL AND NEW.operator <> '') THEN
          UPDATE public.fish SET created_by = COALESCE(created_by, NEW.operator)
          WHERE id = NEW.fish_id AND (created_by IS NULL OR created_by = '');
        END IF;
        RETURN NEW;
      END
      $FN$;
      CREATE TRIGGER trg_update_fish_created_by
      AFTER INSERT ON public.load_log_fish
      FOR EACH ROW EXECUTE FUNCTION public._on_load_log_fish_update_created_by();
    $SQL$;
  ELSE
    RAISE NOTICE 'Skip created_by trigger: load_log_fish missing';
  END IF;
END
$$;
