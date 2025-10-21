begin;

-- Replace ensure_rna_for_plasmid to use id (not id_uuid) everywhere.
-- Signature kept the same to avoid breaking callers (trigger uses PERFORM).
create or replace function public.ensure_rna_for_plasmid(
    p_plasmid_code text,
    p_rna_suffix text,
    p_rna_name text,
    p_created_by text,
    p_notes text
) returns table (rna_id uuid, rna_code text)
language plpgsql
as $$
declare
  v_plasmid_id uuid;
  v_code text;
begin
  -- find plasmid by code
  select id into v_plasmid_id
  from public.plasmids  where code = p_plasmid_code
  limit 1;

  if v_plasmid_id is null then
    raise exception 'ensure_rna_for_plasmid: plasmid code % not found', p_plasmid_code;
  end if;

  -- derive RNA code (simple: base + suffix) if name not given
  v_code := coalesce(nullif(p_rna_name, ''), p_plasmid_code || coalesce(p_rna_suffix, ''));

  -- upsert an RNA for this plasmid
  insert into public.rnas(code, name, source_plasmid_id, created_by, notes)
  values (v_code, v_code, v_plasmid_id, nullif(p_created_by, ''), nullif(p_notes, ''))
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
