BEGIN;

COMMENT ON TABLE public.constructs IS
'Constructs table expects canonical codes from v10_load_constructs_from_csv:
 lower-case letters + ''-'' + non-zero-padded integer (e.g. pdqm-5, mgco-35).';

-- Optional: if you want to enforce canonical shape at DB level,
-- uncomment this check constraint once you are confident loaders are correct.
-- ALTER TABLE public.constructs
--   ADD CONSTRAINT constructs_code_canonical_chk
--   CHECK (
--     construct_code ~ '^[a-z]+-[0-9]+$'
--     AND base_code  ~ '^[a-z]+-[0-9]+$'
--   );

COMMIT;
