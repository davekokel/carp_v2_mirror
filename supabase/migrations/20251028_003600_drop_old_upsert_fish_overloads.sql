-- Remove legacy overload(s) so only the 10-arg canonical function remains.
DROP FUNCTION IF EXISTS public.upsert_fish_by_batch_name_dob(
  text, text, date, text, text, text, text, text, text
);
-- If any accidental wrapper exists, drop it too:
-- DROP FUNCTION IF EXISTS public.upsert_fish_by_batch_name_dob(
--   text, text, date, text, text, text, text, text, text
-- );
