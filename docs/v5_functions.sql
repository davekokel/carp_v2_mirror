CREATE OR REPLACE FUNCTION public.clutch_instance_code_next()
 RETURNS text
 LANGUAGE sql
AS $function$
  SELECT 'CI-'||to_char(now(),'YYYYMMDD')||'-'||lpad(nextval('public.seq_clutch_instance_code')::text, 6, '0');
$function$
;
CREATE OR REPLACE FUNCTION public.clutch_instances_bi_assign_fields()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF NEW.clutch_instance_code IS NULL OR NEW.clutch_instance_code = '' THEN
    NEW.clutch_instance_code := public.clutch_instance_code_next();
  END IF;
  NEW.normalized_genotype := public.normalize_genotype(NEW.clutch_genotype_pretty);
  RETURN NEW;
END
$function$
;
CREATE OR REPLACE FUNCTION public.cross_run_code_next()
 RETURNS text
 LANGUAGE sql
AS $function$
  SELECT 'CR-'||to_char(now(),'YYYYMMDD')||'-'||lpad(nextval('public.seq_cross_run_code')::text, 6, '0');
$function$
;
CREATE OR REPLACE FUNCTION public.crosses_bi_assign_code()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF NEW.cross_run_code IS NULL OR NEW.cross_run_code = '' THEN
    NEW.cross_run_code := public.cross_run_code_next();
  END IF;
  RETURN NEW;
END
$function$
;
CREATE OR REPLACE FUNCTION public.digest(text, text)
 RETURNS bytea
 LANGUAGE sql
 IMMUTABLE PARALLEL SAFE
AS $function$
  SELECT digest(convert_to($1,'UTF8'), $2)
$function$
;
CREATE OR REPLACE FUNCTION public.enforce_join_annotations_fk()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE ok boolean;
BEGIN
  IF NEW.target_id IS NULL OR NEW.target_kind IS NULL THEN
    RAISE EXCEPTION 'join_annotations requires target_kind and target_id';
  END IF;

  CASE NEW.target_kind
    WHEN 'fish'        THEN SELECT EXISTS (SELECT 1 FROM public.fish             p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'clutch_inst' THEN SELECT EXISTS (SELECT 1 FROM public.clutch_instances p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'cross'       THEN SELECT EXISTS (SELECT 1 FROM public.crosses          p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'tank'        THEN SELECT EXISTS (SELECT 1 FROM public.tanks            p WHERE p.id=NEW.target_id) INTO ok;
    WHEN 'plasmid'     THEN SELECT EXISTS (SELECT 1 FROM public.plasmids         p WHERE p.id=NEW.target_id) INTO ok;
    ELSE
      RAISE EXCEPTION 'Unknown target_kind: %', NEW.target_kind;
  END CASE;

  IF NOT ok THEN
    RAISE EXCEPTION 'join_annotations % → % does not reference an existing row', NEW.target_kind, NEW.target_id;
  END IF;

  RETURN NEW;
END
$function$
;
CREATE OR REPLACE FUNCTION public.ensure_active_tank_for_fish(p_fish_code text)
 RETURNS uuid
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_existing uuid;
  v_next_num int;
  v_new_id   uuid;
BEGIN
  IF p_fish_code IS NULL OR btrim(p_fish_code) = '' THEN
    RAISE EXCEPTION 'ensure_active_tank_for_fish(): p_fish_code is required';
  END IF;

  -- return an existing active tank for this fish_code if present (most-recent)
  SELECT t.id INTO v_existing
  FROM public.tanks t
  WHERE t.tank_code LIKE 'TANK('||p_fish_code||')#%' AND COALESCE(t.status,'active') = 'active'
  ORDER BY t.created_at DESC
  LIMIT 1;

  IF v_existing IS NOT NULL THEN
    RETURN v_existing;
  END IF;

  -- compute next available #N for this fish_code from existing tank_code
  SELECT COALESCE(MAX( (regexp_replace(tank_code, '^.*#([0-9]+).*$', '\1'))::int ), 0)
    INTO v_next_num
  FROM public.tanks
  WHERE tank_code LIKE 'TANK('||p_fish_code||')#%';

  v_next_num := v_next_num + 1;

  INSERT INTO public.tanks (tank_code, status)
  VALUES ('TANK('||p_fish_code||')#'||v_next_num::text, 'active')
  RETURNING id INTO v_new_id;

  RETURN v_new_id;
END
$function$
;
CREATE OR REPLACE FUNCTION public.ensure_ft_markers_from_transgene(p_ft_code text)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
BEGIN
  -- 1) Ensure TF master (FK prerequisite)
  INSERT INTO public.treatments_fluorescent (ft_code, ft_text, created_by)
  VALUES (p_ft_code, ''::text, 'system')
  ON CONFLICT (ft_code) DO NOTHING;

  -- 2) Derive and upsert FT markers from plasmid → fusion → (fluor, tag)
  INSERT INTO public.ft_proteins (ft_code, fluor_code, tag_code)
  SELECT DISTINCT
         p_ft_code AS ft_code,
         fl.fluor_code,
         tg.tag_code
  FROM public.plasmids p
  LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
  LEFT JOIN public.fusions f               ON f.id = jpf.fusion_id
  LEFT JOIN public.fluors  fl              ON fl.id = f.fluor_id
  LEFT JOIN public.tags    tg              ON tg.id = f.tag_id
  WHERE p.code = p_ft_code
    AND (fl.fluor_code IS NOT NULL OR tg.tag_code IS NOT NULL)
  ON CONFLICT (ft_code, fluor_code, tag_code) DO NOTHING;
END;
$function$
;
CREATE OR REPLACE FUNCTION public.normalize_genotype(p text)
 RETURNS text
 LANGUAGE sql
AS $function$
  SELECT regexp_replace(lower(coalesce(p,'')), '[^a-z0-9]+', '-', 'g');
$function$
;
CREATE OR REPLACE FUNCTION public.plate_code_next()
 RETURNS text
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_day   text;   -- YYYYMMDD
  v_next  int;
BEGIN
  v_day := to_char(now(), 'YYYYMMDD');

  -- Prevent concurrent callers from generating the same number for this day
  PERFORM pg_advisory_xact_lock( hashtext('plate_code:' || v_day) );

  -- Compute the next daily number by scanning existing codes for this day
  SELECT COALESCE(
           MAX( (regexp_match(plate_code, '-([0-9]{3})$'))[1]::int ),
           0
         )
    INTO v_next
  FROM public.plates
  WHERE plate_code LIKE 'PLT-' || v_day || '-%';

  IF v_next >= 100 THEN
    RAISE EXCEPTION 'Daily plate-code limit (100) reached for %', v_day
      USING ERRCODE = 'check_violation';
  END IF;

  v_next := v_next + 1;

  RETURN 'PLT-' || v_day || '-' || lpad(v_next::text, 3, '0');
END
$function$
;
CREATE OR REPLACE FUNCTION public.plates_bi_assign_code()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF NEW.plate_code IS NULL OR NEW.plate_code = '' THEN
    NEW.plate_code := 'PLT-'||to_char(now(),'YYYYMMDD')||'-'||lpad(nextval('public.seq_plate_code')::text, 4, '0');
  END IF;
  IF NEW.created_at IS NULL THEN
    NEW.created_at := now();
  END IF;
  RETURN NEW;
END
$function$
;
CREATE OR REPLACE FUNCTION public.process_fish_alleles_upload(p_by text)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
DECLARE
  r record;
  v_fish_id uuid;
  v_up  record;
  v_zyg text;
BEGIN
  FOR r IN
    SELECT
      btrim(NULLIF(fish_code,''))           AS fish_code,
      btrim(NULLIF(transgene_base_code,'')) AS base_code,
      NULLIF(allele_nickname,'')            AS allele_nick_raw,
      NULLIF(zygosity,'')                   AS zyg_raw
    FROM raw.fish_alleles_upload
  LOOP
    IF r.fish_code IS NULL OR r.base_code IS NULL THEN
      CONTINUE;
    END IF;

    -- resolve fish_id from fish_code
    SELECT id INTO v_fish_id
    FROM public.fish
    WHERE fish_code = r.fish_code
    LIMIT 1;

    IF v_fish_id IS NULL THEN
      CONTINUE;
    END IF;

    -- normalize zygosity to het/hom/unk
    v_zyg := CASE
               WHEN r.zyg_raw IS NULL THEN NULL
               WHEN lower(btrim(r.zyg_raw)) IN ('het','hetero','heterozygous','h') THEN 'het'
               WHEN lower(btrim(r.zyg_raw)) IN ('hom','homo','homozygous') THEN 'hom'
               WHEN lower(btrim(r.zyg_raw)) IN ('unk','unknown','?','na','n/a','none','') THEN 'unk'
               ELSE 'unk'
             END;

    -- upsert allele (nickname kept as string; blank → defaults to guN)
    SELECT * INTO v_up
    FROM public.upsert_transgene_allele(r.base_code, r.allele_nick_raw);

    -- link fish → allele (upsert zygosity)
    INSERT INTO public.join_fish_transgene_alleles (fish_id, transgene_base_code, allele_number, zygosity)
    VALUES (v_fish_id, v_up.transgene_base_code, v_up.allele_number, v_zyg)
    ON CONFLICT (fish_id, transgene_base_code, allele_number) DO UPDATE
      SET zygosity = COALESCE(EXCLUDED.zygosity, public.join_fish_transgene_alleles.zygosity);
  END LOOP;
END
$function$
;
CREATE OR REPLACE FUNCTION public.row_letter(p_row integer)
 RETURNS text
 LANGUAGE sql
 IMMUTABLE
AS $function$
  SELECT chr(64 + GREATEST(1, LEAST(26, p_row)))
$function$
;
CREATE OR REPLACE FUNCTION public.tank_pair_code_next()
 RETURNS text
 LANGUAGE sql
AS $function$
  SELECT 'TP-'||to_char(now(),'YYYYMMDD')||'-'||lpad(nextval('public.seq_tank_pair_code')::text, 6, '0');
$function$
;
CREATE OR REPLACE FUNCTION public.tank_pairs_bi_assign_code()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF NEW.tank_pair_code IS NULL OR NEW.tank_pair_code = '' THEN
    NEW.tank_pair_code := public.tank_pair_code_next();
  END IF;
  RETURN NEW;
END
$function$
;
CREATE OR REPLACE FUNCTION public.tanks_bi_set_defaults()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF NEW.created_at IS NULL THEN NEW.created_at := now(); END IF;
  RETURN NEW;
END
$function$
;
CREATE OR REPLACE FUNCTION public.to_base36(n bigint)
 RETURNS text
 LANGUAGE plpgsql
 IMMUTABLE
AS $function$
DECLARE
  chars text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  result text := '';
  q bigint := n;
BEGIN
  IF q <= 0 THEN
    RETURN '0';
  END IF;
  WHILE q > 0 LOOP
    result := substr(chars, (q % 36) + 1, 1) || result;
    q := q / 36;
  END LOOP;
  RETURN result;
END;
$function$
;
CREATE OR REPLACE FUNCTION public.treated_clutch_code_next()
 RETURNS text
 LANGUAGE sql
AS $function$
  SELECT 'TCI-'||to_char(now(),'YYYYMMDD')||'-'||lpad(nextval('public.seq_treated_clutch_code')::text, 6, '0');
$function$
;
CREATE OR REPLACE FUNCTION public.treated_clutches_ai_baseline()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  INSERT INTO public.treated_clutches (clutch_instance_id, treated_clutch_code, created_by, created_at)
  VALUES (
    NEW.id,
    'T('||NEW.clutch_instance_code||')-0',
    COALESCE(current_setting('app.user', true), 'system'),
    COALESCE(NEW.created_at, now())
  )
  ON CONFLICT DO NOTHING;
  RETURN NEW;
END
$function$
;
CREATE OR REPLACE FUNCTION public.treated_clutches_bi_assign_code()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF NEW.treated_clutch_code IS NULL OR NEW.treated_clutch_code = '' THEN
    NEW.treated_clutch_code := public.treated_clutch_code_next();
  END IF;
  RETURN NEW;
END
$function$
;
CREATE OR REPLACE FUNCTION public.trg_set_fish_code_base36()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF NEW.fish_code IS NULL OR btrim(NEW.fish_code) = '' THEN
    NEW.fish_code := 'FSH-' || lpad(upper(public.to_base36(nextval('public.seq_fish_code'))), 8, '0');
  END IF;
  RETURN NEW;
END;
$function$
;
CREATE OR REPLACE FUNCTION public.trg_set_fish_code_from_uuid_base36_8()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
  code text := NULLIF(btrim(NEW.fish_code), '');
BEGIN
  IF NEW.id IS NULL THEN
    NEW.id := gen_random_uuid();
  END IF;

  -- Set if missing OR looks decimal (FSH-<digits>)
  IF code IS NULL OR code ~* '^FSH-\d+$' THEN
    NEW.fish_code := 'FSH-' || public.uuid_to_base36_8(NEW.id);
  END IF;

  RETURN NEW;
END
$function$
;
CREATE OR REPLACE FUNCTION public.upsert_fish_by_identity(p_seed_batch_id text, p_identity_key text, p_dob date, p_name_human text, p_bg text, p_nick text, p_stage text, p_desc text, p_notes text, p_by text)
 RETURNS TABLE(id uuid, fish_id uuid, fish_code text)
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_key  text;
  v_hash text;
  v_id   uuid;
  v_code text;
BEGIN
  v_key  := COALESCE(p_identity_key,'');
  v_hash := encode(digest(v_key,'sha256'), 'hex');

  SELECT f.id, f.fish_code
    INTO v_id, v_code
  FROM public.fish f
  WHERE f.identity_key = v_key
     OR f.identity_hash = v_hash
  LIMIT 1;

  IF v_id IS NOT NULL THEN
    id := v_id; fish_id := v_id; fish_code := v_code;
    RETURN NEXT; RETURN;
  END IF;

  v_code := 'FSH-'||lpad(nextval('public.seq_fish_code')::text, 8, '0');

  INSERT INTO public.fish (
    id, fish_code, nickname, dob,
    genetic_background, line_building_stage,
    identity_key, identity_hash, created_at
  )
  VALUES (
    gen_random_uuid(),
    v_code,
    NULLIF(p_nick,''),
    p_dob,
    NULLIF(p_bg,''),
    NULLIF(p_stage,''),
    v_key,
    v_hash,
    now()
  )
  RETURNING public.fish.id, public.fish.fish_code INTO v_id, v_code;

  id := v_id; fish_id := v_id; fish_code := v_code;
  RETURN NEXT;
END $function$
;
CREATE OR REPLACE FUNCTION public.upsert_transgene_allele(p_transgene_base_code text, p_allele_nickname text)
 RETURNS TABLE(out_base text, out_number bigint, out_name text)
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_base text := btrim(p_transgene_base_code);
  v_nick text := NULLIF(btrim(p_allele_nickname), '');
  v_num  bigint;
  v_name text;
BEGIN
  IF v_base IS NULL OR v_base = '' THEN
    RETURN;
  END IF;

  -- ensure a transgene row exists (only base column)
  INSERT INTO public.transgenes (transgene_base_code)
  VALUES (v_base)
  ON CONFLICT ON CONSTRAINT transgenes_pkey DO NOTHING;

  -- try reuse by nickname (within same base), case-insensitive
  IF v_nick IS NOT NULL THEN
    SELECT ta.allele_number, ta.allele_name
      INTO v_num, v_name
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = v_base
      AND lower(btrim(ta.allele_nickname)) = lower(btrim(v_nick))
    LIMIT 1;

    IF v_num IS NOT NULL THEN
      out_base := v_base; out_number := v_num; out_name := v_name;
      RETURN NEXT; RETURN;
    END IF;
  END IF;

  -- mint new global number (prefer sequence; fallback to MAX+1)
  BEGIN
    v_num := nextval('public.seq_global_allele_number');
  EXCEPTION
    WHEN undefined_table OR undefined_object THEN
      SELECT COALESCE(MAX(allele_number), 0) + 1 INTO v_num FROM public.transgene_alleles;
  END;

  v_name := 'gu' || v_num::text;

  INSERT INTO public.transgene_alleles (
    transgene_base_code, allele_number, allele_name, allele_nickname
  ) VALUES (
    v_base, v_num, v_name, COALESCE(v_nick, v_name)
  )
  ON CONFLICT ON CONSTRAINT transgene_alleles_pkey DO NOTHING;

  out_base := v_base; out_number := v_num; out_name := v_name;
  RETURN NEXT;
END
$function$
;
CREATE OR REPLACE FUNCTION public.uuid_to_base36_8(p uuid)
 RETURNS text
 LANGUAGE plpgsql
 IMMUTABLE
AS $function$
DECLARE
  b bytea := decode(replace(p::text, '-', ''), 'hex');  -- 16 bytes
  m bigint := 36^8;                                     -- 2,821,109,907,456
  rem bigint := 0;
  i int;
  v int;
  chars constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  out text := '';
BEGIN
  FOR i IN 0..15 LOOP
    v := get_byte(b, i);
    rem := (rem * 256 + v)::bigint % m;
  END LOOP;

  IF rem = 0 THEN
    out := '0';
  ELSE
    WHILE rem > 0 LOOP
      out := substr(chars, (rem % 36)::int + 1, 1) || out;
      rem := rem / 36;
    END LOOP;
  END IF;

  RETURN lpad(upper(out), 8, '0');
END
$function$
;
