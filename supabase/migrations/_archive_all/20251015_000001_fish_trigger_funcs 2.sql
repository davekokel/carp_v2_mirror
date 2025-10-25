CREATE OR REPLACE FUNCTION public.fish_before_insert_code()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF NEW.fish_code IS NULL
     OR btrim(NEW.fish_code) = ''
     OR NEW.fish_code !~ '^FSH-[0-9]{2}[0-9A-Z]{4,}$' THEN
    NEW.fish_code := public.make_fish_code_yy_seq36(now());
  END IF;
  RETURN NEW;
END $function$
;
CREATE OR REPLACE FUNCTION public.fish_bi_set_fish_code()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
  v bigint;
  r int;
  s text := '';
  yy text;
  digits constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
BEGIN
  IF NEW.fish_code IS NULL OR NEW.fish_code !~ '^FSH-\d{2}[0-9A-Z]{4}$' THEN
    -- two-digit UTC year
    yy := to_char(timezone('UTC', now()), 'YY');

    -- next sequence value → base36
    v := nextval('public.fish_code_seq');
    IF v = 0 THEN
      s := '0';
    ELSE
      WHILE v > 0 LOOP
        r := (v % 36)::int;
        s := substr(digits, r+1, 1) || s;
        v := v / 36;
      END LOOP;
    END IF;

    -- left-pad base36 to 4 chars
    s := lpad(s, 4, '0');

    NEW.fish_code := 'FSH-' || yy || s;
  END IF;
  RETURN NEW;
END;
$function$
;
CREATE OR REPLACE FUNCTION public.fish_birthday_sync()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
begin
  -- If 'birthday' provided, mirror to date_birth
  if tg_op in ('INSERT','UPDATE') then
    if new.birthday is not null and (new.date_birth is distinct from new.birthday) then
      new.date_birth := new.birthday;
    end if;
    -- If only date_birth provided (legacy writers), mirror to birthday
    if new.date_birth is not null and (new.birthday is distinct from new.date_birth) then
      new.birthday := new.date_birth;
    end if;
  end if;
  return new;
end;
$function$
;
CREATE OR REPLACE FUNCTION public.refresh_mv_overview_fish_daily()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  REFRESH MATERIALIZED VIEW public.mv_overview_fish_daily;
  RETURN NULL;
END
$function$
;
CREATE OR REPLACE FUNCTION public.trg_fish_autotank()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
  v_label text := COALESCE(NEW.nickname, NEW.name, 'Holding Tank');
  v_container_id uuid;
  v_code text;
BEGIN
  -- Derive the tank_code from this fish's code
  v_code := public.gen_tank_code_for_fish(NEW.fish_code);

  -- Create holding tank with per-fish code
  INSERT INTO public.containers (container_type, status, label, tank_code, created_by)
  VALUES ('holding_tank', 'new_tank', v_label, v_code, COALESCE(NEW.created_by, 'system'))
  RETURNING id INTO v_container_id;

  -- Link fish → tank (handle schema variants)
  BEGIN
    INSERT INTO public.fish_tank_memberships (fish_id, container_id, started_at)
    VALUES (NEW.id, v_container_id, now());
  EXCEPTION WHEN undefined_column THEN
    INSERT INTO public.fish_tank_memberships (fish_id, container_id, joined_at)
    VALUES (NEW.id, v_container_id, now());
  END;

  RETURN NEW;
END
$function$
;
CREATE OR REPLACE FUNCTION public.trg_set_updated_at()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END
$function$
;
