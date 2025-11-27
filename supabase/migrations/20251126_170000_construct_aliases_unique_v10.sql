BEGIN;

ALTER TABLE public.construct_aliases
  ADD CONSTRAINT construct_aliases_unique_v10
  UNIQUE (construct_id, alias, alias_kind);

COMMIT;
