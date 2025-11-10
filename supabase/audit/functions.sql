enforce_join_aliases_fk|CREATE OR REPLACE FUNCTION public.enforce_join_aliases_fk()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE ok boolean := false;
BEGIN
  IF NEW.target_kind='fluor' THEN SELECT TRUE INTO ok FROM public.fluors WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='tag' THEN SELECT TRUE INTO ok FROM public.tags WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='dye' THEN SELECT TRUE INTO ok FROM public.dyes WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='rna' THEN SELECT TRUE INTO ok FROM public.rnas WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='plasmid' THEN SELECT TRUE INTO ok FROM public.plasmids WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='fish' THEN SELECT TRUE INTO ok FROM public.fish WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='tank' THEN SELECT TRUE INTO ok FROM public.tanks WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='cross' THEN SELECT TRUE INTO ok FROM public.crosses WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='clutch_inst' THEN SELECT TRUE INTO ok FROM public.clutch_instances WHERE id=NEW.target_id;
  ELSIF NEW.target_kind='treated_clutch' THEN SELECT TRUE INTO ok FROM public.treated_clutches WHERE id=NEW.target_id;
  ELSE ok := TRUE;
  END IF;
  IF NOT ok THEN RAISE EXCEPTION 'join_aliases target_id % not found for kind %', NEW.target_id, NEW.target_kind; END IF;
  RETURN NEW;
END$function$

ensure_fusion_id|CREATE OR REPLACE FUNCTION public.ensure_fusion_id(_fluor_sym text, _tag_sym text, _tag_pos text)
 RETURNS uuid
 LANGUAGE plpgsql
AS $function$
DECLARE
  fid uuid;
  tid uuid;
  pos text;
  existing_id uuid;
BEGIN
  IF _fluor_sym IS NULL OR btrim(_fluor_sym)='' THEN
    RETURN NULL;
  END IF;

  fid := public.resolve_symbol_id('fluor', _fluor_sym);
  IF fid IS NULL THEN
    RETURN NULL;  -- unknown fluor
  END IF;

  IF _tag_sym IS NULL OR btrim(_tag_sym)='' THEN
    tid := NULL;
    pos := NULL;  -- fluor-only: ignore tag_pos
  ELSE
    tid := public.resolve_symbol_id('tag', _tag_sym);
    IF tid IS NULL THEN
      RETURN NULL;  -- unknown tag
    END IF;
    pos := CASE WHEN upper(btrim(COALESCE(_tag_pos,''))) IN ('N','C')
                THEN upper(btrim(_tag_pos))
                ELSE NULL
           END;
  END IF;

  -- first try to find exact match (including pos)
  SELECT id INTO existing_id
  FROM public.fusions
  WHERE fluor_id=fid
    AND ( (tid IS NULL AND tag_id IS NULL)
          OR (tag_id=tid AND (tag_pos IS NOT DISTINCT FROM pos)) )
  LIMIT 1;

  IF existing_id IS NOT NULL THEN
    RETURN existing_id;
  END IF;

  -- if tag present and there exists a sibling (fid, tid, ANY pos),
  -- try to backfill only if safe (i.e., no row with desired pos)
  IF tid IS NOT NULL THEN
    IF pos IS NOT NULL THEN
      -- safe backfill: move NULL/other to desired pos if no exact row exists
      UPDATE public.fusions f
      SET tag_pos = pos
      WHERE f.fluor_id=fid
        AND f.tag_id  =tid
        AND f.tag_pos IS DISTINCT FROM pos
        AND NOT EXISTS (
          SELECT 1 FROM public.fusions f2
          WHERE f2.fluor_id=fid AND f2.tag_id=tid AND (f2.tag_pos IS NOT DISTINCT FROM pos)
        )
      RETURNING id INTO existing_id;

      IF existing_id IS NOT NULL THEN
        RETURN existing_id;
      END IF;
    END IF;
  END IF;

  -- insert the exact desired row
  INSERT INTO public.fusions(fluor_id, tag_id, tag_pos)
  VALUES (fid, tid, pos)
  ON CONFLICT DO NOTHING;

  -- return the id (now must exist)
  SELECT id INTO existing_id
  FROM public.fusions
  WHERE fluor_id=fid
    AND ( (tid IS NULL AND tag_id IS NULL)
          OR (tag_id=tid AND (tag_pos IS NOT DISTINCT FROM pos)) )
  LIMIT 1;

  RETURN existing_id;
END
$function$

resolve_dye_id|CREATE OR REPLACE FUNCTION public.resolve_dye_id(sym text)
 RETURNS uuid
 LANGUAGE sql
 STABLE
AS $function$
  WITH s AS (SELECT lower(btrim(sym)) k)
  SELECT id FROM public.dyes d JOIN s ON lower(d.dye_code)=s.k OR lower(COALESCE(d.dye_name,''))=s.k
  UNION
  SELECT target_id FROM public.join_aliases ja JOIN s ON ja.alias_norm=s.k WHERE ja.target_kind='dye'::public.alias_target_kind
  LIMIT 1
$function$

resolve_fluor_id|CREATE OR REPLACE FUNCTION public.resolve_fluor_id(sym text)
 RETURNS uuid
 LANGUAGE sql
 STABLE
AS $function$
  WITH s AS (SELECT lower(btrim(sym)) k)
  SELECT id FROM public.fluors f JOIN s ON lower(f.fluor_code)=s.k OR lower(COALESCE(f.fluor_name,''))=s.k
  UNION
  SELECT target_id FROM public.join_aliases ja JOIN s ON ja.alias_norm=s.k WHERE ja.target_kind='fluor'::public.alias_target_kind
  LIMIT 1
$function$

resolve_fusion_id|CREATE OR REPLACE FUNCTION public.resolve_fusion_id(combo text)
 RETURNS uuid
 LANGUAGE plpgsql
AS $function$
DECLARE
  raw     text := btrim(COALESCE(combo,''));
  no_ws   text;
  parts   text[];
  leftp   text;
  rightp  text;
  fid     uuid;
  tid     uuid;
  existing uuid;
BEGIN
  IF raw='' THEN
    RETURN NULL;
  END IF;

  no_ws := regexp_replace(raw, '\s+', '', 'g');
  parts := regexp_split_to_array(no_ws, '::|[:/@+]');

  IF array_length(parts,1) IS NULL THEN
    RETURN NULL;
  ELSIF array_length(parts,1) = 1 THEN
    fid := public.resolve_fluor_id(parts[1]);
    tid := NULL;
  ELSE
    leftp  := parts[1];
    rightp := parts[array_length(parts,1)];

    fid := public.resolve_fluor_id(leftp);
    IF fid IS NOT NULL THEN
      tid := public.resolve_tag_id(rightp);
    ELSE
      fid := public.resolve_fluor_id(rightp);
      tid := public.resolve_tag_id(leftp);
    END IF;
  END IF;

  IF fid IS NULL THEN
    RETURN NULL;
  END IF;

  SELECT id INTO existing
  FROM public.fusions
  WHERE fluor_id=fid
    AND ((tid IS NULL AND tag_id IS NULL) OR tag_id=tid)
  LIMIT 1;

  IF existing IS NOT NULL THEN
    RETURN existing;
  END IF;

  INSERT INTO public.fusions(fluor_id, tag_id)
  VALUES (fid, tid)
  ON CONFLICT DO NOTHING;

  SELECT id INTO existing
  FROM public.fusions
  WHERE fluor_id=fid
    AND ((tid IS NULL AND tag_id IS NULL) OR tag_id=tid)
  LIMIT 1;

  RETURN existing;
END
$function$

resolve_symbol_id|CREATE OR REPLACE FUNCTION public.resolve_symbol_id(_kind text, _sym text)
 RETURNS uuid
 LANGUAGE sql
 STABLE
AS $function$
  SELECT target_id
  FROM public.v_symbol_map
  WHERE kind=_kind AND sym=lower(btrim(_sym))
  LIMIT 1
$function$

resolve_tag_id|CREATE OR REPLACE FUNCTION public.resolve_tag_id(sym text)
 RETURNS uuid
 LANGUAGE sql
 STABLE
AS $function$
  WITH s AS (SELECT lower(btrim(sym)) k)
  SELECT id FROM public.tags t JOIN s ON lower(t.tag_code)=s.k OR lower(COALESCE(t.tag_name,''))=s.k
  UNION
  SELECT target_id FROM public.join_aliases ja JOIN s ON ja.alias_norm=s.k WHERE ja.target_kind='tag'::public.alias_target_kind
  LIMIT 1
$function$

trg_clutch_default_treated|CREATE OR REPLACE FUNCTION public.trg_clutch_default_treated()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM public.treated_clutches tc
    WHERE tc.clutch_instance_id = NEW.id
  ) THEN
    INSERT INTO public.treated_clutches (id, treated_clutch_code, clutch_instance_id, created_at)
    VALUES (
      gen_random_uuid(),
      COALESCE(NULLIF(NEW.clutch_instance_code,''),'CI') || '#0',
      NEW.id,
      now()
    );
  END IF;
  RETURN NEW;
END;
$function$

upsert_fish_by_identity|CREATE OR REPLACE FUNCTION public.upsert_fish_by_identity(p_seed_batch_id text, p_identity_key text, p_bday date, p_name_human text, p_bg text, p_nick text, p_stage text, p_desc text, p_notes text, p_by text)
 RETURNS TABLE(id uuid, fish_code text)
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_hash text;
  v_row  public.fish%ROWTYPE;
BEGIN
  v_hash := encode(digest(coalesce(p_identity_key,''),'sha256'),'hex');

  -- Try to reuse an existing fish by identity
  SELECT * INTO v_row
  FROM public.fish
  WHERE identity_hash = v_hash OR identity_key = p_identity_key
  LIMIT 1;

  IF FOUND THEN
    id := v_row.id;
    fish_code := v_row.fish_code;
    RETURN NEXT;
    RETURN;
  END IF;

  -- Insert a new fish; assume helper public.uuid_base36_8(uuid) exists in your DB
  WITH new_id AS (SELECT gen_random_uuid() AS id)
  INSERT INTO public.fish
    (id, fish_code, birthday, genetic_background, in_breeding_stage,
     nickname, description, identity_key, identity_hash, created_at)
  SELECT
    nid.id,
    public.uuid_base36_8(nid.id),
    p_bday,
    NULLIF(p_bg,''),
    NULLIF(p_stage,''),
    NULLIF(p_nick,''),
    NULLIF(p_desc,''),
    p_identity_key,
    v_hash,
    now()
  FROM new_id nid
  RETURNING public.fish.id, public.fish.fish_code
  INTO id, fish_code;

  RETURN NEXT;
END;
$function$

upsert_transgene_allele|CREATE OR REPLACE FUNCTION public.upsert_transgene_allele(p_base text, p_nickname text)
 RETURNS TABLE(transgene_base_code text, allele_number integer, allele_name text, allele_nickname text)
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_base text := NULLIF(btrim(p_base), '');
  v_nick text := NULLIF(btrim(p_nickname), '');
  v_row  public.transgene_alleles%ROWTYPE;
  v_new  int;
  v_gu   text;
BEGIN
  IF v_base IS NULL THEN
    RETURN;
  END IF;

  IF v_nick IS NOT NULL THEN
    IF lower(v_nick) IN ('unknown','unk','n/a','na','none','?','-') THEN
      v_nick := NULL;
    ELSIF v_nick ~ '^\d+(?:\.0+)?$' THEN
      v_nick := NULL;
    END IF;
  END IF;

  INSERT INTO public.transgenes(transgene_base_code) VALUES (v_base)
  ON CONFLICT DO NOTHING;

  IF v_nick IS NULL THEN
    SELECT * INTO v_row
    FROM public.transgene_alleles
    WHERE transgene_base_code = v_base
    ORDER BY allele_number
    LIMIT 1;

    IF FOUND THEN
      transgene_base_code := v_row.transgene_base_code;
      allele_number       := v_row.allele_number;
      allele_name         := COALESCE(v_row.allele_name, 'gu'||v_row.allele_number);
      allele_nickname     := COALESCE(v_row.allele_nickname, 'gu'||v_row.allele_number);
      RETURN NEXT;
      RETURN;
    END IF;
  ELSE
    SELECT * INTO v_row
    FROM public.transgene_alleles
    WHERE transgene_base_code = v_base
      AND lower(allele_nickname) = lower(v_nick)
    LIMIT 1;

    IF FOUND THEN
      transgene_base_code := v_row.transgene_base_code;
      allele_number       := v_row.allele_number;
      allele_name         := COALESCE(v_row.allele_name, 'gu'||v_row.allele_number);
      allele_nickname     := v_row.allele_nickname;
      RETURN NEXT;
      RETURN;
    END IF;
  END IF;

  LOOP
    v_new := nextval('public."transgene_allele_global"')::int;
    v_gu  := 'gu'||v_new;
    BEGIN
      INSERT INTO public.transgene_alleles
        (transgene_base_code, allele_number, allele_name, allele_nickname)
      VALUES
        (v_base, v_new, v_gu, COALESCE(v_nick, v_gu))
      ON CONFLICT DO NOTHING;

      SELECT * INTO v_row
      FROM public.transgene_alleles
      WHERE transgene_base_code = v_base AND allele_number = v_new
      LIMIT 1;

      IF FOUND THEN
        transgene_base_code := v_row.transgene_base_code;
        allele_number       := v_row.allele_number;
        allele_name         := v_row.allele_name;
        allele_nickname     := v_row.allele_nickname;
        RETURN NEXT;
        RETURN;
      END IF;
    EXCEPTION WHEN unique_violation THEN
    END;
  END LOOP;
END;
$function$

uuid_base36_8|CREATE OR REPLACE FUNCTION public.uuid_base36_8(u uuid)
 RETURNS text
 LANGUAGE plpgsql
AS $function$
DECLARE
  hex text := replace(u::text,'-','');
  h10 text := right(hex, 10);
  n   numeric := 0;
  i   int;
  c   text;
  v   int;
  alphabet constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  out text := '';
BEGIN
  FOR i IN 1..length(h10) LOOP
    c := substr(h10, i, 1);
    v := CASE c
           WHEN '0' THEN 0 WHEN '1' THEN 1 WHEN '2' THEN 2 WHEN '3' THEN 3
           WHEN '4' THEN 4 WHEN '5' THEN 5 WHEN '6' THEN 6 WHEN '7' THEN 7
           WHEN '8' THEN 8 WHEN '9' THEN 9
           WHEN 'a' THEN 10 WHEN 'b' THEN 11 WHEN 'c' THEN 12 WHEN 'd' THEN 13
           WHEN 'e' THEN 14 WHEN 'f' THEN 15
           WHEN 'A' THEN 10 WHEN 'B' THEN 11 WHEN 'C' THEN 12 WHEN 'D' THEN 13
           WHEN 'E' THEN 14 WHEN 'F' THEN 15
           ELSE 0
         END;
    n := n*16 + v;
  END LOOP;

  FOR i IN 1..8 LOOP
    v := mod(n, 36);
    out := substr(alphabet, v+1, 1) || out;
    n := trunc(n/36);
  END LOOP;

  RETURN 'FSH-' || out;
END
$function$

