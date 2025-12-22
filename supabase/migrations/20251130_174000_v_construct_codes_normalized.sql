BEGIN;

-- DEPRECATED (2025-12-22):
-- v_construct_codes_normalized is no longer part of the schema/view spine.
-- Code now derives "code_normalized" directly from constructs + construct_aliases.
-- See: supabase/migrations/20251222_000200_drop_v_construct_codes_normalized.sql

COMMIT;
