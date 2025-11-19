BEGIN;

----------------------------------------------------------------------
-- v8: fluor_aliases
--
-- One row per alias for a given fluor.
-- E.g. from alias.csv:
--   target_kind = 'fluor'
--   target_key  = canonical fluor_code (e.g. 'mStayGold')
--   alias       = alias (e.g. 'mSG')
--
-- This table lets loaders resolve fluor_code values that are aliases
-- (like 'mSG') to the canonical fluor row in public.fluors.
----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.fluor_aliases (
  fluor_id uuid NOT NULL
    REFERENCES public.fluors(id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  alias    text PRIMARY KEY
);

COMMIT;
