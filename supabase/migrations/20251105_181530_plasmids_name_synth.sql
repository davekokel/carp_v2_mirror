BEGIN;
CREATE OR REPLACE FUNCTION public.plasmid_pretty_fusion_rollup(p_plasmid_id uuid)
RETURNS text LANGUAGE sql STABLE AS $$
  SELECT NULLIF(
    (
      SELECT string_agg(
               DISTINCT
               CASE
                 WHEN COALESCE(fl.fluor_name,'')<>'' AND COALESCE(tg.tag_name,'')<>'' THEN fl.fluor_name||'::'||tg.tag_name
                 WHEN COALESCE(fl.fluor_name,'')<>'' THEN fl.fluor_name
                 WHEN COALESCE(tg.tag_name,'')<>'' THEN tg.tag_name
                 ELSE ''
               END
             , ', ' ORDER BY COALESCE(fl.fluor_name,''), COALESCE(tg.tag_name,''))
      FROM public.join_plasmid_fusions j
      JOIN public.fusions f ON f.id=j.fusion_id
      LEFT JOIN public.fluors fl ON fl.id=f.fluor_id
      LEFT JOIN public.tags   tg ON tg.id=f.tag_id
      WHERE j.plasmid_id = p_plasmid_id
    ), ''
  );
$$;
CREATE OR REPLACE FUNCTION public.compute_plasmid_display_name(p_plasmid_id uuid, p_nickname text, p_code text)
RETURNS text LANGUAGE plpgsql STABLE AS $$
DECLARE roll text;
BEGIN
  IF p_plasmid_id IS NOT NULL THEN
    roll := public.plasmid_pretty_fusion_rollup(p_plasmid_id);
    IF roll IS NOT NULL THEN
      RETURN roll;
    END IF;
  END IF;
  RETURN COALESCE(NULLIF(p_nickname,''), p_code);
END$$;
CREATE OR REPLACE FUNCTION public.trg_plasmids_set_name_before_ins()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.name IS NULL OR btrim(NEW.name)='' THEN
    NEW.name := public.compute_plasmid_display_name(NULL, NEW.nickname, NEW.code);
  END IF;
  RETURN NEW;
END$$;
DROP TRIGGER IF EXISTS trg_plasmids_set_name_before_ins ON public.plasmids;
CREATE TRIGGER trg_plasmids_set_name_before_ins
BEFORE INSERT ON public.plasmids
FOR EACH ROW EXECUTE PROCEDURE public.trg_plasmids_set_name_before_ins();
CREATE OR REPLACE FUNCTION public.trg_refresh_plasmid_name_from_links()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_plasmid_id uuid; v_nick text; v_code text;
BEGIN
  v_plasmid_id := COALESCE(NEW.plasmid_id, OLD.plasmid_id);
  SELECT nickname, code INTO v_nick, v_code FROM public.plasmids WHERE id=v_plasmid_id;
  UPDATE public.plasmids
     SET name = public.compute_plasmid_display_name(v_plasmid_id, v_nick, v_code)
   WHERE id = v_plasmid_id;
  RETURN NULL;
END$$;
DROP TRIGGER IF EXISTS trg_refresh_plasmid_name_from_links ON public.join_plasmid_fusions;
CREATE TRIGGER trg_refresh_plasmid_name_from_links
AFTER INSERT OR UPDATE OR DELETE ON public.join_plasmid_fusions
FOR EACH ROW EXECUTE PROCEDURE public.trg_refresh_plasmid_name_from_links();
CREATE OR REPLACE FUNCTION public.trg_refresh_plasmid_name_from_fusion_change()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE public.plasmids p
     SET name = public.compute_plasmid_display_name(p.id, p.nickname, p.code)
   WHERE EXISTS (
     SELECT 1 FROM public.join_plasmid_fusions j
     WHERE j.plasmid_id = p.id
       AND j.fusion_id  = (CASE WHEN TG_OP='DELETE' THEN OLD.id ELSE NEW.id END)
   );
  RETURN NULL;
END$$;
DROP TRIGGER IF EXISTS trg_refresh_plasmid_name_from_fusion_change ON public.fusions;
CREATE TRIGGER trg_refresh_plasmid_name_from_fusion_change
AFTER UPDATE OF fusion_name, fluor_id, tag_id ON public.fusions
FOR EACH ROW EXECUTE PROCEDURE public.trg_refresh_plasmid_name_from_fusion_change();
COMMIT;
