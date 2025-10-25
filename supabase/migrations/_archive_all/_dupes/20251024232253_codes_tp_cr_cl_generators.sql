begin;

-- Reuse fixed to_base36(n bigint)
-- (assumes you already have the corrected function; keep for safety)
create or replace function public.to_base36(n bigint)
returns text language plpgsql immutable as $$
declare v bigint := n; s text := ''; a constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'; pos int;
begin
  if v < 0 then raise exception 'to_base36 expects nonnegative'; end if;
  if v = 0 then return '0'; end if;
  while v > 0 loop pos := (v % 36)::int + 1; s := substr(a, pos, 1) || s; v := v / 36; end loop;
  return s;
end $$;

-- ========== TANK PAIR: TP({FP})-NN =========================================
-- Per-FP counter (atomic upsert) for NN
create table if not exists public.tank_pair_counters (
  fish_pair_code text primary key,
  next_nn bigint not null default 1
);

create or replace function public.next_tp_suffix(p_fish_pair_code text)
returns text language plpgsql volatile as $$
declare v bigint; b text;
begin
  with up as (
    insert into public.tank_pair_counters(fish_pair_code, next_nn)
    values (p_fish_pair_code, 2)
    on conflict (fish_pair_code) do update
      set next_nn = tank_pair_counters.next_nn + 1
    returning next_nn
  )
  select next_nn - 1 into v from up;
  b := public.to_base36(v);
  return b; -- unwrapped base-36 (1,2..9,A..Z,10..)
end $$;

create or replace function public.make_tp_code(p_fish_pair_code text)
returns text language sql stable as $$
  select 'TP(' || p_fish_pair_code || ')-' || public.next_tp_suffix(p_fish_pair_code)
$$;

-- BEFORE INSERT trigger to set tank_pair_code
create or replace function public.trg_tank_pairs_set_code()
returns trigger language plpgsql as $$
declare fp text;
begin
  -- discover FP code from row
  if new.fish_pair_code is not null and new.fish_pair_code <> '' then
    fp := new.fish_pair_code;
  elsif new.fish_pair_id is not null then
    select fish_pair_code into fp from public.fish_pairs where fish_pair_id = new.fish_pair_id;
  end if;

  if (new.tank_pair_code is null or new.tank_pair_code = '') and fp is not null then
    new.tank_pair_code := public.make_tp_code(fp);
  end if;
  return new;
end $$;

drop trigger if exists trg_tank_pairs_set_code on public.tank_pairs;
create trigger trg_tank_pairs_set_code
before insert on public.tank_pairs
for each row execute function public.trg_tank_pairs_set_code();

-- Uniqueness / format (keep loose if legacy rows exist)
do $$
begin
  if not exists (select 1 from pg_indexes where schemaname='public' and indexname='uq_tank_pairs_code') then
    execute 'create unique index uq_tank_pairs_code on public.tank_pairs (tank_pair_code)';
  end if;
end $$;

alter table public.tank_pairs
  drop constraint if exists tank_pair_code_format_chk;
alter table public.tank_pairs
  add constraint tank_pair_code_format_chk
  check (tank_pair_code ~ '^TP\\(FP-[0-9A-Z]{5,}\\)-[0-9A-Z]+$');

-- ========== CROSS RUN: CR({TP})({NN}) ======================================
-- Per-TP counter (atomic upsert) for NN (two digits, 01..99 then 100.. allowed)
create table if not exists public.tp_run_counters (
  tank_pair_code text primary key,
  next_nn int not null default 1
);

create or replace function public.next_run_nn(p_tank_pair_code text)
returns text language plpgsql volatile as $$
declare v int;
begin
  with up as (
    insert into public.tp_run_counters(tank_pair_code, next_nn)
    values (p_tank_pair_code, 2)
    on conflict (tank_pair_code) do update
      set next_nn = tp_run_counters.next_nn + 1
    returning next_nn
  )
  select next_nn - 1 into v from up;
  return lpad(v::text, 2, '0');
end $$;

create or replace function public.make_cr_code(p_tank_pair_code text)
returns text language sql stable as $$
  select 'CR(' || p_tank_pair_code || ')(' || public.next_run_nn(p_tank_pair_code) || ')'
$$;

create or replace function public.trg_cross_instances_set_code()
returns trigger language plpgsql as $$
begin
  if new.cross_run_code is null or new.cross_run_code = '' then
    if new.tank_pair_code is null or new.tank_pair_code = '' then
      raise exception 'cross_instances.tank_pair_code required to generate CR code';
    end if;
    new.cross_run_code := public.make_cr_code(new.tank_pair_code);
  end if;
  return new;
end $$;

drop trigger if exists trg_cross_instances_set_code on public.cross_instances;
create trigger trg_cross_instances_set_code
before insert on public.cross_instances
for each row execute function public.trg_cross_instances_set_code();

do $$
begin
  if not exists (select 1 from pg_indexes where schemaname='public' and indexname='uq_cross_run_code') then
    execute 'create unique index uq_cross_run_code on public.cross_instances (cross_run_code)';
  end if;
end $$;

alter table public.cross_instances
  drop constraint if exists cross_run_code_format_chk;
alter table public.cross_instances
  add constraint cross_run_code_format_chk
  check (cross_run_code ~ '^CR\\(TP\\(FP-[0-9A-Z]{5,}\\)-[0-9A-Z]+\\)\\([0-9]{2,}\\)$');

-- ========== CLUTCH INSTANCE: CL({TP})({NN}) ================================
-- Prefer to mirror CR if linked; else generate like CR for the TP.
create or replace function public.make_cl_code_from_cr(p_cr text)
returns text language sql stable as $$
  -- Replace leading 'CR(' with 'CL(' — rest identical
  select 'CL' || substr(p_cr, 3)
$$;

create or replace function public.make_cl_code(p_tank_pair_code text)
returns text language sql stable as $$
  select 'CL(' || p_tank_pair_code || ')(' || public.next_run_nn(p_tank_pair_code) || ')'
$$;

create or replace function public.trg_clutch_instances_set_code()
returns trigger language plpgsql as $$
declare cr text;
begin
  if new.clutch_instance_code is null or new.clutch_instance_code = '' then
    -- If linked to cross row, mirror its CR → CL
    if new.cross_instance_id is not null then
      select cross_run_code into cr from public.cross_instances where id = new.cross_instance_id;
      if cr is not null then
        new.clutch_instance_code := public.make_cl_code_from_cr(cr);
        return new;
      end if;
    end if;
    -- Fallback: require tank_pair_code, generate new NN like cross does
    if new.tank_pair_code is null or new.tank_pair_code = '' then
      raise exception 'clutch_instances needs cross_instance_id or tank_pair_code to generate CL code';
    end if;
    new.clutch_instance_code := public.make_cl_code(new.tank_pair_code);
  end if;
  return new;
end $$;

drop trigger if exists trg_clutch_instances_set_code on public.clutch_instances;
create trigger trg_clutch_instances_set_code
before insert on public.clutch_instances
for each row execute function public.trg_clutch_instances_set_code();

do $$
begin
  if not exists (select 1 from pg_indexes where schemaname='public' and indexname='uq_clutch_instance_code') then
    execute 'create unique index uq_clutch_instance_code on public.clutch_instances (clutch_instance_code)';
  end if;
end $$;

alter table public.clutch_instances
  drop constraint if exists clutch_instance_code_format_chk;
alter table public.clutch_instances
  add constraint clutch_instance_code_format_chk
  check (clutch_instance_code ~ '^CL\\(TP\\(FP-[0-9A-Z]{5,}\\)-[0-9A-Z]+\\)\\([0-9]{2,}\\)$');

commit;
