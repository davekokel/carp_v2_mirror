BEGIN;

CREATE TABLE IF NOT EXISTS public.genetic_backgrounds (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  bg_code         text UNIQUE NOT NULL,
  bg_name         text,
  bg_category     text,
  source_system   text,
  description     text,
  created_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.genetic_backgrounds IS
  'Canonical vocabulary of genetic backgrounds (casper, casper/rnf, pIGLET 14a, etc.).';

COMMENT ON COLUMN public.genetic_backgrounds.bg_code IS
  'Primary text key used in fish_instance.genetic_background.';

COMMIT;
