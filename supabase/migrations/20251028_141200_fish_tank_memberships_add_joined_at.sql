ALTER TABLE public.fish_tank_memberships
  ADD COLUMN IF NOT EXISTS joined_at timestamptz;
UPDATE public.fish_tank_memberships
  SET joined_at = COALESCE(joined_at, created_at);
