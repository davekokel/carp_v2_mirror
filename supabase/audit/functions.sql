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

