begin;

-- Drop the exact overload that uses old param names (e.g., p_suffix)
drop function if exists public.ensure_rna_for_plasmid(text,text,text,text,text);

-- Recreate with same signature/param names so callers (and triggers) keep working.
-- Implement using 'id' everywhere; return id + code (OUT names don't matter to PERFORM).
create function public.ensure_rna_for_plasmid(
  p_plasmid_code text,
  p_suffix       text,
  p_name         text,
  p_created_by   text,
  p_notes        text
) returns table (rna_id uuid, rna_code text)
language plpgsql
as $$
declare
  v_plasmid_id uuid;
  v_code text;
begin
  select id into v_plasmid_id
  from public.plasmids
  where code = p_plasmid_code
  limit 1;

  if v_plasmid_id is null then
    raise exception 'ensure_rna_for_plasmid: plasmid code % not found', p_plasmid_code;
  end if;

  -- If no explicit name provided, generate from plasmid code + suffix
  v_code := coalesce(nullif(p_name,''), p_plasmid_code || coalesce(p_suffix,''));

  insert into public.rnas(code, name, source_plasmid_id, created_by, notes)
  values (v_code, v_code, v_plasmid_id, nullif(p_created_by,''), nullif(p_notes,''))
  on conflict (code) do update
    set name = excluded.name,
        source_plasmid_id = coalesce(excluded.source_plasmid_id, public.rnas.source_plasmid_id),
        created_by        = coalesce(excluded.created_by,        public.rnas.created_by),
        notes             = coalesce(excluded.notes,             public.rnas.notes)
  returning id, code
  into rna_id, rna_code;

  return next;
end;
$$;

commit;
