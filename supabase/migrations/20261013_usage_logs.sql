-- Usage logging moved from the Render-local SQLite/Postgres store into Supabase.
-- Run once in the Supabase SQL editor. Safe to re-run.

create table if not exists public.usage_logs (
    id          bigint generated always as identity primary key,
    user_id     uuid        not null references auth.users (id) on delete cascade,
    user_email  text        not null,
    endpoint    text        not null,
    query_text  text,
    created_at  timestamptz not null default now()
);

create index if not exists usage_logs_user_email_created_idx
    on public.usage_logs (user_email, created_at desc);

-- Only the server (service role, which bypasses RLS) may read or write.
alter table public.usage_logs enable row level security;
revoke all on public.usage_logs from anon, authenticated;

-- Per-user request totals for the admin user list
create or replace view public.usage_counts
with (security_invoker = true) as
    select user_email, count(*)::bigint as total_requests, max(created_at) as last_request
    from public.usage_logs
    group by user_email;

revoke all on public.usage_counts from anon, authenticated;
