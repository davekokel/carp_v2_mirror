BEGIN;

-- 1) Base tables
CREATE TABLE IF NOT EXISTS public.transgenes (
  transgene_base_code text PRIMARY KEY,
  name                text
);

CREATE SEQUENCE IF NOT EXISTS public.seq_global_allele_number;

CREATE TABLE IF NOT EXISTS public.transgene_alleles (
  transgene_base_code text   NOT NULL REFERENCES public.transgenes(transgene_base_code) ON DELETE CASCADE,
  allele_number       bigint NOT NULL,                      -- global (seq)
  allele_name         text   NOT NULL,                      -- 'gu' || allele_number
  allele_nickname     text   NOT NULL,                      -- stored as text (even if looks numeric)
  created_at          timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (transgene_base_code, allele_number)
);

-- nickname reuse per transgene (case-insensitive, trimmed)
CREATE UNIQUE INDEX IF NOT EXISTS uq_ta_base_nickname_norm
  ON public.transgene_alleles (transgene_base_code, lower(btrim(allele_nickname)));

-- 2) Link fish ↔ alleles
CREATE TABLE IF NOT EXISTS public.join_fish_transgene_alleles (
  fish_id             uuid   NOT NULL REFERENCES public.fish(id) ON DELETE CASCADE,
  transgene_base_code text   NOT NULL,
  allele_number       bigint NOT NULL,
  zygosity            text,
  created_at          timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (fish_id, transgene_base_code, allele_number),
  FOREIGN KEY (transgene_base_code, allele_number)
    REFERENCES public.transgene_alleles(transgene_base_code, allele_number)
    ON DELETE CASCADE
);

-- 3) Upsert function (idempotent; global numbering; nickname-as-string)
CREATE OR REPLACE FUNCTION public.upsert_transgene_allele(
  p_base_code      text,
  p_allele_nick_in text
)
RETURNS TABLE (
  transgene_base_code text,
  allele_number       bigint,
  allele_name         text
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_base   text;
  v_nick   text;
  v_num    bigint;
  v_name   text;
BEGIN
  v_base := btrim(p_base_code);
  IF v_base IS NULL OR v_base = '' THEN
    RAISE EXCEPTION 'transgene base_code is required';
  END IF;

  INSERT INTO public.transgenes (transgene_base_code, name)
  VALUES (v_base, v_base)
  ON CONFLICT (transgene_base_code) DO NOTHING;

  v_nick := CASE
              WHEN p_allele_nick_in IS NULL THEN NULL
              ELSE NULLIF(btrim(p_allele_nick_in), '')
            END;

  IF v_nick IS NOT NULL THEN
    SELECT ta.allele_number, ta.allele_name
      INTO v_num, v_name
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = v_base
      AND lower(btrim(ta.allele_nickname)) = lower(btrim(v_nick))
    LIMIT 1;

    IF v_num IS NOT NULL THEN
      transgene_base_code := v_base; allele_number := v_num; allele_name := v_name; RETURN;
    END IF;
  END IF;

  v_num := nextval('public.seq_global_allele_number');
  v_name := 'gu' || v_num::text;

  INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, allele_name, allele_nickname)
  VALUES (v_base, v_num, v_name, COALESCE(v_nick, v_name));

  transgene_base_code := v_base; allele_number := v_num; allele_name := v_name; RETURN;
END
$$;

COMMIT;
