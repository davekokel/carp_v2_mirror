BEGIN;

CREATE TABLE IF NOT EXISTS public.fluor_aliases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fluor_id uuid NOT NULL REFERENCES public.fluors(id) ON DELETE CASCADE,
  alias text NOT NULL,
  alias_norm text GENERATED ALWAYS AS (lower(btrim(alias))) STORED,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (fluor_id, alias_norm)
);

CREATE TABLE IF NOT EXISTS public.tag_aliases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tag_id uuid NOT NULL REFERENCES public.tags(id) ON DELETE CASCADE,
  alias text NOT NULL,
  alias_norm text GENERATED ALWAYS AS (lower(btrim(alias))) STORED,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tag_id, alias_norm)
);

INSERT INTO public.fluor_aliases (fluor_id, alias)
SELECT f.id, x.alias
FROM public.fluors f
CROSS JOIN LATERAL unnest(COALESCE(f.alt_names, '{}'::text[])) AS x(alias)
WHERE COALESCE(btrim(x.alias),'') <> ''
ON CONFLICT DO NOTHING;

INSERT INTO public.tag_aliases (tag_id, alias)
SELECT t.id, x.alias
FROM public.tags t
CROSS JOIN LATERAL unnest(COALESCE(t.alt_names, '{}'::text[])) AS x(alias)
WHERE COALESCE(btrim(x.alias),'') <> ''
ON CONFLICT DO NOTHING;

COMMIT;
