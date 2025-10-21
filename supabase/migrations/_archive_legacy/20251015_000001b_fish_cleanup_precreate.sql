DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_fish_code' AND conrelid='public.fish'::regclass) THEN
    ALTER TABLE public.fish DROP CONSTRAINT uq_fish_code;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_fish_fish_code' AND conrelid='public.fish'::regclass) THEN
    ALTER TABLE public.fish DROP CONSTRAINT uq_fish_fish_code;
  END IF;
END$$;

DROP TRIGGER IF EXISTS bi_set_fish_code                          ON public.fish;
DROP TRIGGER IF EXISTS trg_audit_del                             ON public.fish;
DROP TRIGGER IF EXISTS trg_audit_ins                             ON public.fish;
DROP TRIGGER IF EXISTS trg_audit_upd                             ON public.fish;
DROP TRIGGER IF EXISTS trg_fish_autotank                         ON public.fish;
DROP TRIGGER IF EXISTS trg_fish_before_insert_code               ON public.fish;
DROP TRIGGER IF EXISTS trg_fish_birthday_sync                    ON public.fish;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_fish_daily_d      ON public.fish;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_fish_daily_i      ON public.fish;
DROP TRIGGER IF EXISTS trg_refresh_mv_overview_fish_daily_u      ON public.fish;
DROP TRIGGER IF EXISTS trg_set_updated_at                        ON public.fish;
