-- Re-drop any legacy views that older migrations might have re-created
drop view if exists public.v_cross_clutch_instances cascade;
drop view if exists public.v_clutches_overview cascade;
drop view if exists public.v_fish_overview cascade;
drop view if exists public.v_fish_overview_canonical cascade;
drop view if exists public.v_fish_overview_rich cascade;
drop view if exists public.v_fish_standard_clean cascade;
