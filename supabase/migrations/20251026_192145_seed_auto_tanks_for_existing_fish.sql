INSERT INTO public.tanks (tank_uuid, tank_code, fish_code, status, created_at)
SELECT gen_random_uuid(), 'TANK('||f.fish_code||')#1', f.fish_code, 'active', now()
FROM public.fish f
WHERE NOT EXISTS (
  SELECT 1 FROM public.tanks t WHERE t.fish_code = f.fish_code
);
COMMIT;
