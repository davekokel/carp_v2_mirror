DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='parent_relation') THEN
    CREATE TYPE parent_relation AS ENUM ('mom','dad','surrogate','unknown');
  END IF;

  IF to_regclass('public.crosses') IS NULL THEN
    CREATE TABLE public.crosses (
      id_uuid    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      mom_id     uuid NOT NULL,
      dad_id     uuid NOT NULL,
      crossed_at timestamptz NOT NULL DEFAULT now(),
      notes      text,
      created_at timestamptz NOT NULL DEFAULT now(),
      created_by text
    );
  END IF;

  IF to_regclass('public.fish') IS NOT NULL THEN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='crosses_mom_fk') THEN
      ALTER TABLE public.crosses
        ADD CONSTRAINT crosses_mom_fk
        FOREIGN KEY (mom_id) REFERENCES public.fish(id_uuid) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='crosses_dad_fk') THEN
      ALTER TABLE public.crosses
        ADD CONSTRAINT crosses_dad_fk
        FOREIGN KEY (dad_id) REFERENCES public.fish(id_uuid) ON DELETE RESTRICT;
    END IF;
  END IF;

  IF to_regclass('public.fish') IS NOT NULL THEN
    PERFORM 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='fish' AND column_name='cross_id';
    IF NOT FOUND THEN
      ALTER TABLE public.fish ADD COLUMN cross_id uuid NULL;
    END IF;
    IF to_regclass('public.crosses') IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fish_cross_fk') THEN
      ALTER TABLE public.fish
        ADD CONSTRAINT fish_cross_fk
        FOREIGN KEY (cross_id) REFERENCES public.crosses(id_uuid);
    END IF;
  END IF;

  IF to_regclass('public.fish_parentage') IS NULL THEN
    CREATE TABLE public.fish_parentage (
      child_id   uuid NOT NULL,
      parent_id  uuid NOT NULL,
      relation   parent_relation NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      created_by text,
      PRIMARY KEY (child_id, parent_id, relation)
    );
  END IF;

  IF to_regclass('public.fish') IS NOT NULL THEN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fish_parentage_child_fk') THEN
      ALTER TABLE public.fish_parentage
        ADD CONSTRAINT fish_parentage_child_fk
        FOREIGN KEY (child_id) REFERENCES public.fish(id_uuid) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fish_parentage_parent_fk') THEN
      ALTER TABLE public.fish_parentage
        ADD CONSTRAINT fish_parentage_parent_fk
        FOREIGN KEY (parent_id) REFERENCES public.fish(id_uuid) ON DELETE RESTRICT;
    END IF;
  END IF;
END
$$;
