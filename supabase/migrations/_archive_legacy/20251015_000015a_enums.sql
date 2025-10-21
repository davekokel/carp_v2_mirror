do $$ begin if not exists (select 1 from pg_type where typname='clutch_plan_status' and typnamespace='public'::regnamespace)
   then execute 'create type public.clutch_plan_status as enum ('draft','ready','scheduled','closed')'; end if; end$$;
