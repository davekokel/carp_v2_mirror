ALTER TABLE public.fish_tank_memberships
  ADD COLUMN IF NOT EXISTS left_at timestamptz;
