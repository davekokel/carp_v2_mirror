BEGIN;

ALTER TABLE public.dyes
  ADD CONSTRAINT dyes_nickname_key UNIQUE (nickname);

COMMIT;
