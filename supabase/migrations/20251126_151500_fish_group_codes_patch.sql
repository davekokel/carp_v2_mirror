BEGIN;

-- 1) Add group_code to existing fish_groups
ALTER TABLE public.fish_groups
  ADD COLUMN group_code text;

ALTER TABLE public.fish_groups
  ADD CONSTRAINT fish_groups_group_code_unique
    UNIQUE (group_code);

ALTER TABLE public.fish_groups
  ADD CONSTRAINT fish_groups_group_code_format_chk
    CHECK (
      group_code IS NULL
      OR group_code ~ '^GROUP-[0-9a-fA-F]{8}$'
    );

-- 2) Add group_instance_code to fish_lines
ALTER TABLE public.fish_lines
  ADD COLUMN group_instance_code text;

ALTER TABLE public.fish_lines
  ADD CONSTRAINT fish_lines_group_instance_code_format_chk
    CHECK (
      group_instance_code IS NULL
      OR group_instance_code ~ '^GROUP-[0-9a-fA-F]{8}-[0-9]{3}$'
    );

COMMIT;
