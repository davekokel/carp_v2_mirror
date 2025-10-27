BEGIN;

-- 1) Add fish_uuid column (if missing) and backfill from fish_id
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish_seed_batches_map' AND column_name='fish_uuid'
  ) THEN
    ALTER TABLE public.fish_seed_batches_map ADD COLUMN fish_uuid uuid;
  END IF;

  -- Backfill once (idempotent)
  UPDATE public.fish_seed_batches_map
     SET fish_uuid = COALESCE(fish_uuid, fish_id)
   WHERE fish_uuid IS NULL;
END$$;

-- 2) Add FK on fish_uuid → fish(fish_uuid) (if missing)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_fsbm_fish_uuid' AND conrelid = 'public.fish_seed_batches_map'::regclass
  ) THEN
    ALTER TABLE public.fish_seed_batches_map
      ADD CONSTRAINT fk_fsbm_fish_uuid
      FOREIGN KEY (fish_uuid) REFERENCES public.fish(fish_uuid) ON DELETE CASCADE;
  END IF;
END$$;

-- 3) Ensure unique (seed_batch_id, fish_uuid)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='uq_fsbm_seed_batch_uuid' AND conrelid='public.fish_seed_batches_map'::regclass
  ) THEN
    ALTER TABLE public.fish_seed_batches_map
      ADD CONSTRAINT uq_fsbm_seed_batch_uuid UNIQUE (seed_batch_id, fish_uuid);
  END IF;
END$$;

-- 4) Drop old unique constraints on fish_id, if present
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_fsbm_batch_fish' AND conrelid='public.fish_seed_batches_map'::regclass) THEN
    ALTER TABLE public.fish_seed_batches_map DROP CONSTRAINT uq_fsbm_batch_fish;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_fsbm_natural' AND conrelid='public.fish_seed_batches_map'::regclass) THEN
    ALTER TABLE public.fish_seed_batches_map DROP CONSTRAINT uq_fsbm_natural;
  END IF;
END$$;

-- 5) Drop fish_id column (only when fish_uuid is in place)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish_seed_batches_map' AND column_name='fish_id'
  ) THEN
    ALTER TABLE public.fish_seed_batches_map DROP COLUMN fish_id;
  END IF;
END$$;

-- 6) Replace the upsert to use fish_uuid everywhere
DROP FUNCTION IF EXISTS public.upsert_fish_by_batch_name_dob(text,text,date,text,text,text,text,text,text);

CREATE FUNCTION public.upsert_fish_by_batch_name_dob(
    p_seed_batch_id text,
    p_name          text,
    p_date_birth    date,
    p_genetic_background text,
    p_nickname      text,
    p_line_building_stage text,
    p_description   text,
    p_notes         text,
    p_created_by    text
)
RETURNS TABLE(fish_uuid uuid, fish_code text)
LANGUAGE plpgsql
AS $func$
DECLARE
  v_name_norm text := lower(trim(COALESCE(p_name,'')));
  v_fu uuid;
  v_fc text;
BEGIN
  -- A) In-batch by mapping (fish_seed_batches_map.fish_uuid)
  SELECT f.fish_uuid, f.fish_code
    INTO v_fu, v_fc
  FROM public.fish f
  JOIN public.fish_seed_batches_map m
    ON m.fish_uuid = f.fish_uuid
   AND m.seed_batch_id = p_seed_batch_id
  WHERE lower(trim(COALESCE(f.name,''))) = v_name_norm
    AND f.date_birth = p_date_birth
  LIMIT 1;

  -- B) Global reuse by (name_norm, dob, genetic_background)
  IF v_fu IS NULL THEN
    SELECT f.fish_uuid, f.fish_code
      INTO v_fu, v_fc
    FROM public.fish f
    WHERE lower(trim(COALESCE(f.name,''))) = v_name_norm
      AND f.date_birth = p_date_birth
      AND COALESCE(f.genetic_background,'') = COALESCE(p_genetic_background,'')
    LIMIT 1;
  END IF;

  -- C) Create new fish if still not found
  IF v_fu IS NULL THEN
    INSERT INTO public.fish (
      fish_code,
      name,
      nickname,
      genetic_background,
      line_building_stage,
      date_birth,
      description,
      notes,
      created_by
    )
    VALUES (
      public.gen_fish_code(),
      NULLIF(trim(p_name),''),
      NULLIF(trim(p_nickname),''),
      p_genetic_background,
      p_line_building_stage,
      p_date_birth,
      p_description,
      p_notes,
      p_created_by
    )
    RETURNING fish_uuid, fish_code INTO v_fu, v_fc;
  END IF;

  -- D) Ensure batch mapping exists (uuid-based)
  INSERT INTO public.fish_seed_batches_map(fish_uuid, seed_batch_id)
  VALUES (v_fu, p_seed_batch_id)
  ON CONFLICT ON CONSTRAINT uq_fsbm_seed_batch_uuid DO NOTHING;

  RETURN QUERY SELECT v_fu, v_fc;
END
$func$;

COMMIT;
