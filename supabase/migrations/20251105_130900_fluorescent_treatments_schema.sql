BEGIN;

CREATE TABLE IF NOT EXISTS public.fluorescent_treatments (
  ft_code   text PRIMARY KEY,
  ft_text   text NOT NULL,
  ft_meta   jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by text
);

CREATE TABLE IF NOT EXISTS public.ft_injection_mixes (
  ft_code       text PRIMARY KEY REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE,
  protocol_code text,
  protocol_text text,
  notes         text
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='ft_injection_mix_sources'
  ) THEN
    CREATE TABLE public.ft_injection_mix_sources (
      id          bigserial PRIMARY KEY,
      ft_code     text NOT NULL REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE,
      source_kind text NOT NULL CHECK (source_kind IN ('plasmid','enzyme','oligo','pcr_product','mrna','grna','protocol','other')),
      ref_code    text,
      ref_text    text,
      qty         numeric,
      units       text,
      role        text,
      notes       jsonb,
      CONSTRAINT ck_ftmix_src_ref_present CHECK (ref_code IS NOT NULL OR ref_text IS NOT NULL)
    );
    CREATE UNIQUE INDEX uq_ftmix_src
      ON public.ft_injection_mix_sources (ft_code, source_kind, COALESCE(ref_code,'∅'), COALESCE(ref_text,'∅'));
  END IF;
END$$;

-- Leave other objects in this file as-is or add guards like above if present

COMMIT;
