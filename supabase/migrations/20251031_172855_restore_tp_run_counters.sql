do $$
begin
  if to_regclass('trash_carp.tp_run_counters') is not null then
    execute 'alter table trash_carp.tp_run_counters set schema public';
  elsif to_regclass('public.tp_run_counters') is null then
    execute 'create table public.tp_run_counters (
      tank_pair_code text primary key,
      next_nn int not null default 1
    )';
  end if;
end
$$;

do $$
begin
  if to_regclass('public.tp_run_counters') is null then
    null;
  else
    if not exists (
      select 1 from information_schema.columns
      where table_schema='public' and table_name='tp_run_counters' and column_name='tank_pair_code'
    ) then
      execute 'alter table public.tp_run_counters add column tank_pair_code text';
    end if;

    if not exists (
      select 1 from information_schema.columns
      where table_schema='public' and table_name='tp_run_counters' and column_name='next_nn'
    ) then
      execute 'alter table public.tp_run_counters add column next_nn int default 1';
    end if;

    if not exists (
      select 1 from pg_constraint
      where conrelid='public.tp_run_counters'::regclass and contype='p'
    ) then
      begin
        execute 'alter table public.tp_run_counters add primary key (tank_pair_code)';
      exception when others then
        null;
      end;
    end if;
  end if;
end
$$;

create index if not exists idx_tp_run_counters_tpc on public.tp_run_counters(tank_pair_code);

comment on table public.tp_run_counters is
  'Maintains per-tank_pair_code run counters for cross_instances (used by make_cr_code/next_run_nn triggers).';
