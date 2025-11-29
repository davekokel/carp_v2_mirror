BEGIN;

CREATE TABLE IF NOT EXISTS public.fish_line_aliases (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  line_id     uuid NOT NULL REFERENCES public.fish_lines(id) ON DELETE CASCADE,
  alias       text NOT NULL,
  alias_kind  text NOT NULL DEFAULT 'nickname', -- e.g. 'legacy_parent', 'lab_name'
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS fish_line_aliases_line_alias_uniq
  ON public.fish_line_aliases(line_id, alias);

COMMIT;
