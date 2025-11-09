BEGIN;

-- 1) Fluor aliases
CREATE TABLE IF NOT EXISTS public.fluor_aliases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fluor_id uuid NOT NULL REFERENCES public.fluors(id) DEFERRABLE INITIALLY DEFERRED,
  alias text NOT NULL,
  alias_norm text GENERATED ALWAYS AS (lower(btrim(alias))) STORED,
  created_at timestamptz DEFAULT now(),
  CONSTRAINT uq_fluor_alias UNIQUE (fluor_id, alias_norm)
);
CREATE INDEX IF NOT EXISTS idx_fluor_aliases_norm ON public.fluor_aliases(alias_norm);

-- 2) Tag aliases
CREATE TABLE IF NOT EXISTS public.tag_aliases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tag_id uuid NOT NULL REFERENCES public.tags(id) DEFERRABLE INITIALLY DEFERRED,
  alias text NOT NULL,
  alias_norm text GENERATED ALWAYS AS (lower(btrim(alias))) STORED,
  created_at timestamptz DEFAULT now(),
  CONSTRAINT uq_tag_alias UNIQUE (tag_id, alias_norm)
);
CREATE INDEX IF NOT EXISTS idx_tag_aliases_norm ON public.tag_aliases(alias_norm);

-- 3) Seed from existing columns (nicknames + alt_names text lists)
--    Fluors
WITH base AS (
  SELECT f.id, f.fluor_code, COALESCE(NULLIF(f.fluor_name,''), f.fluor_code) AS nm,
         COALESCE(NULLIF(f.alt_names,''),'') AS alts
  FROM public.fluors f
), toks AS (
  SELECT id, unnest(
           ARRAY[
             nm
           ] || CASE WHEN alts <> '' THEN string_to_array(alts, ';') ELSE ARRAY[]::text[] END
         ) AS alias
  FROM base
)
INSERT INTO public.fluor_aliases(fluor_id, alias)
SELECT id, btrim(alias) FROM toks
WHERE btrim(alias) <> ''
ON CONFLICT DO NOTHING;

--    Tags
WITH base AS (
  SELECT t.id, t.tag_code, COALESCE(NULLIF(t.tag_name,''), t.tag_code) AS nm
  FROM public.tags t
), toks AS (
  SELECT id, nm AS alias FROM base
)
INSERT INTO public.tag_aliases(tag_id, alias)
SELECT id, btrim(alias) FROM toks
WHERE btrim(alias) <> ''
ON CONFLICT DO NOTHING;

COMMIT;
