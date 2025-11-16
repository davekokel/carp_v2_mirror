BEGIN;

DO $$
BEGIN
  IF to_regclass('public.legacy_pairs') IS NULL THEN
    RAISE NOTICE 'Creating public.legacy_pairs';
    CREATE TABLE public.legacy_pairs (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      dataset text NOT NULL,
      zf_female_genotype text NOT NULL,
      zf_male_genotype text NOT NULL,
      pair_code text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now()
    );
  ELSE
    RAISE NOTICE 'public.legacy_pairs already exists, skipping create.';
  END IF;

  IF to_regclass('public.legacy_clutches') IS NULL THEN
    RAISE NOTICE 'Creating public.legacy_clutches';
    CREATE TABLE public.legacy_clutches (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      legacy_pair_id uuid NOT NULL,
      dataset text NOT NULL,
      date_mount text,
      clutch_code text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now()
    );
  ELSE
    RAISE NOTICE 'public.legacy_clutches already exists, skipping create.';
  END IF;
END$$;

COMMIT;
