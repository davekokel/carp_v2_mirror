-- minimal join: fish ↔ tanks (dated)
CREATE TABLE IF NOT EXISTS public.fish_tank_memberships (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fish_id    uuid NOT NULL REFERENCES public.fish(id)   ON DELETE CASCADE,
  tank_id    uuid NOT NULL REFERENCES public.tanks(id)  ON DELETE CASCADE,
  started_at timestamptz NOT NULL DEFAULT now(),
  ended_at   timestamptz
);
CREATE INDEX IF NOT EXISTS idx_ftm_fish   ON public.fish_tank_memberships(fish_id);
CREATE INDEX IF NOT EXISTS idx_ftm_tank   ON public.fish_tank_memberships(tank_id);
CREATE INDEX IF NOT EXISTS idx_ftm_active ON public.fish_tank_memberships(tank_id, ended_at);

COMMENT ON TABLE public.fish_tank_memberships IS
  'Links a fish to a tank over time (started_at/ended_at).';
