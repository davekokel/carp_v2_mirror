begin;

create extension if not exists pgcrypto;

create table if not exists public.clutch_instance_treatments (
  id uuid primary key default gen_random_uuid(),
  clutch_instance_id uuid not null references public.clutch_instances(id) on delete cascade,
  material_type text,
  material_code text,
  material_name text,
  notes text,
  created_by text,
  created_at timestamptz not null default now()
);

create index if not exists ix_cit_clutch_instance_id
  on public.clutch_instance_treatments(clutch_instance_id);

create unique index if not exists uq_cit_instance_material
  on public.clutch_instance_treatments (
    clutch_instance_id,
    lower(coalesce(material_type,'')),
    lower(coalesce(material_code,''))
  );

create or replace function public._copy_plan_treatments_to_cit(p_clutch_instance_id uuid)
returns integer
language plpgsql
as $$
declare
  v_clutch_id uuid;
  v_cnt int := 0;
begin
  select cp.id
  into v_clutch_id
  from public.clutch_instances ci
  join public.cross_instances xi on xi.id = ci.cross_instance_id
  join public.crosses x          on x.id  = xi.cross_id
  join public.planned_crosses pc on pc.cross_id = x.id
  join public.clutch_plans cp    on cp.id = pc.clutch_id
  where ci.id = p_clutch_instance_id
  limit 1;

  if v_clutch_id is null then
    return 0;
  end if;

  insert into public.clutch_instance_treatments (
    clutch_instance_id, material_type, material_code, material_name, notes, created_by
  )
  select
    p_clutch_instance_id,
    coalesce(
      cpt.material_type,
      case
        when cpt.plasmid_code is not null then 'plasmid'
        when cpt.rna_code     is not null then 'rna'
        else 'generic'
      end
    ),
    coalesce(cpt.material_code, cpt.plasmid_code, cpt.rna_code),
    coalesce(cpt.material_name, cpt.plasmid_code, cpt.rna_code, cpt.material_code),
    cpt.notes,
    current_setting('app.user', true)
  from public.clutch_plan_treatments cpt
  where cpt.clutch_id = v_clutch_id
  on conflict (clutch_instance_id,
               lower(coalesce(material_type,'')),
               lower(coalesce(material_code,''))) do nothing;

  get diagnostics v_cnt = row_count;
  return v_cnt;
end
$$;

create or replace function public.trg_cit_on_insert_copy_template()
returns trigger
language plpgsql
as $$
begin
  perform public._copy_plan_treatments_to_cit(new.id);
  return new;
end
$$;

drop trigger if exists trg_cit_copy_template on public.clutch_instances;
create trigger trg_cit_copy_template
after insert on public.clutch_instances
for each row
execute function public.trg_cit_on_insert_copy_template();

do $$
declare
  r record;
begin
  for r in
    select ci.id
    from public.clutch_instances ci
    left join public.clutch_instance_treatments cit
      on cit.clutch_instance_id = ci.id
    where cit.clutch_instance_id is null
  loop
    perform public._copy_plan_treatments_to_cit(r.id);
  end loop;
end
$$;

commit;
