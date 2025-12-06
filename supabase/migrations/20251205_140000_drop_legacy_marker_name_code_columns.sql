BEGIN;

-- This migration used to drop fluor_code / tag_code / dye_base_code columns,
-- but that is now handled safely by later migrations:
--   20251205_150000_v_constructs_and_treatment_use_marker_labels_v11.sql
--   20251205_151000_drop_legacy_marker_code_name_columns.sql
--
-- Keep only a safe view cleanup so rebuilds don't break on obsolete deps.

DROP VIEW IF EXISTS public.v11_dyes_star;

COMMIT;
