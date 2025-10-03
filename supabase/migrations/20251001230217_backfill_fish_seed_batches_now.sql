DO $$
BEGIN
  IF to_regclass('public.fish_seed_batches') IS NULL THEN
    RAISE NOTICE 'Skip: fish_seed_batches missing';
    RETURN;
  END IF;
  IF to_regclass('public.load_log_fish') IS NULL THEN
    RAISE NOTICE 'Skip backfill: load_log_fish missing';
    RETURN;
  END IF;

  EXECUTE $SQL$
    INSERT INTO public.fish_seed_batches (fish_id, seed_batch_id)
    SELECT DISTINCT ON (llf.fish_id)
      llf.fish_id, llf.seed_batch_id
    FROM public.load_log_fish llf
    WHERE llf.fish_id IS NOT NULL
    ORDER BY llf.fish_id, llf.logged_at DESC
    ON CONFLICT (fish_id) DO UPDATE SET seed_batch_id = EXCLUDED.seed_batch_id
  $SQL$;
END
$$;
