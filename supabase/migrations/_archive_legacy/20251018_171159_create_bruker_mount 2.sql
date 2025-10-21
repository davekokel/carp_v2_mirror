create table if not exists public.bruker_mount (
    -- exactly the seven fields you requested
    mount_code text primary key,
    mount_date date not null,
    mount_time time,                    -- optional; may be NULL
    mount_orientation text not null,           -- e.g., dorsal_up / ventral_up / lateral_left / lateral_right / other
    mount_top_n integer not null default 0,
    mount_bottom_n integer not null default 0,
    mount_notes text
);
