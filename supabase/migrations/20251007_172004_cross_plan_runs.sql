BEGIN;

-- Instances of a cross plan (can be scheduled in bulk)
CREATE TABLE IF NOT EXISTS public.cross_plan_runs (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id      uuid NOT NULL REFERENCES public.cross_plans(id) ON DELETE CASCADE,
  seq          integer NOT NULL,              -- 1..N per plan
  planned_date date    NOT NULL,
  tank_a_id    uuid    NULL REFERENCES public.containers(id_uuid),
  tank_b_id    uuid    NULL REFERENCES public.containers(id_uuid),
  status       text    NOT NULL DEFAULT 'planned',
  note         text    NULL,
  created_by   text    NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE(plan_id, seq)
);

-- Enriched view (for reports & UI)
DROP VIEW IF EXISTS public.v_cross_plan_runs_enriched;
CREATE VIEW public.v_cross_plan_runs_enriched AS
SELECT
  r.id, r.plan_id, r.seq, r.planned_date, r.status, r.note, r.created_by, r.created_at,
  p.plan_title, p.plan_nickname, p.mother_fish_id, p.father_fish_id,
  fm.fish_code AS mother_fish_code,
  ff.fish_code AS father_fish_code,
  ca.label     AS tank_a_label,
  cb.label     AS tank_b_label
FROM public.cross_plan_runs r
JOIN public.cross_plans p  ON p.id = r.plan_id
LEFT JOIN public.fish fm   ON fm.id = p.mother_fish_id
LEFT JOIN public.fish ff   ON ff.id = p.father_fish_id
LEFT JOIN public.containers ca ON ca.id_uuid = r.tank_a_id
LEFT JOIN public.containers cb ON cb.id_uuid = r.tank_b_id;

CREATE INDEX IF NOT EXISTS idx_cross_plan_runs_plan ON public.cross_plan_runs(plan_id);
CREATE INDEX IF NOT EXISTS idx_cross_plan_runs_date ON public.cross_plan_runs(planned_date);

COMMIT;
