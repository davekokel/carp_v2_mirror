-- Backfill one active tank per fish, but skip if the tank_code already exists
INSERT INTO public.tanks (tank_uuid, tank_code, fish_code, status, created_at)
SELECT gen_random_uuid(), 'TANK('||f.fish_code||')#1', f.fish_code, 'active', now()
FROM public.fish f
ON CONFLICT ON CONSTRAINT tanks_tank_code_key DO NOTHING;
