-- Guard-safe backfill + labeled view (works with/without load_log_fish; uses fish.id)

DO $$
BEGIN
  -- Ensure base tables exist
  IF to_regclass('public.fish') IS NULL THEN
    RAISE NOTICE 'Skip: public.fish missing';
    RETURN;
  END IF;

  IF to_regclass('public.fish_seed_batches') IS NULL THEN
    EXECUTE '
      CREATE TABLE public.fish_seed_batches(
        fish_id uuid PRIMARY KEY REFERENCES public.fish(id) ON DELETE CASCADE,
        seed_batch_id text
      )';
  END IF;

  -- Backfill only if load_log_fish exists; upsert latest per fish_id
  IF to_regclass('public.load_log_fish') IS NOT NULL THEN
    EXECUTE $SQL$
      INSERT INTO public.fish_seed_batches (fish_id, seed_batch_id)
      SELECT DISTINCT ON (f.id)
        f.id,
        llf.seed_batch_id
      FROM public.load_log_fish llf
      JOIN public.fish f
        ON f.id = llf.fish_id
      WHERE llf.fish_id IS NOT NULL
      ORDER BY f.id, llf.logged_at DESC
      ON CONFLICT (fish_id) DO UPDATE
        SET seed_batch_id = EXCLUDED.seed_batch_id
    $SQL$;
  ELSE
    RAISE NOTICE 'load_log_fish not present; skipping backfill';
  END IF;

  -- Rebuild labeled overview (drop first to avoid replace shape issues)
  IF to_regclass('public.v_fish_overview') IS NOT NULL THEN
    EXECUTE 'DROP VIEW IF EXISTS public.vw_fish_overview_with_label CASCADE';
    EXECUTE '
      CREATE VIEW public.vw_fish_overview_with_label AS
      SELECT
        v.id,
        v.fish_code,
        v.name,
        v.transgene_base_code_filled,
        v.allele_code_filled,
        v.allele_name_filled,
        v.created_at,
        v.created_by,
        fsb.seed_batch_id
      FROM public.v_fish_overview v
      LEFT JOIN public.fish_seed_batches fsb
        ON fsb.fish_id = v.id
    ';
  END IF;
END
$$;
