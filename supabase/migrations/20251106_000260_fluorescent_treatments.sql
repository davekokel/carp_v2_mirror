BEGIN;
CREATE TABLE IF NOT EXISTS public.fluorescent_treatments (
  ft_code    text PRIMARY KEY,
  ft_text    text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMIT;
