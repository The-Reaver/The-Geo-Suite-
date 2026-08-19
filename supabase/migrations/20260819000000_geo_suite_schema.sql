-- GEO Suite v1 schema. Adapted 2026-08-19 from Stag-GEO-Platform's proven,
-- already-working migrations (20250101000000_schema.sql, 20250101000100_rls.sql,
-- 20260725192000_sales_prospects.sql + its three follow-ups) for this
-- repo's own independent Supabase project -- not a guess, the schema the
-- working sales/auth code already runs against in production. Deliberately
-- excludes the tool-set tables (tools, entitlements, phone_numbers,
-- messages, jobs) and the never-migrated client-dashboard tables (sites,
-- audit_results, leads, content_pages, subscriptions) per the operator's
-- decision to defer that dashboard until it's a real, current requirement.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- clients: the tenant accounts
-- ---------------------------------------------------------------------------
create table public.clients (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- users: profile rows that mirror auth.users
-- The operator flag lives here, on the user, fully separate from any client
-- role. It is never grantable through signup or invitation. A trigger below
-- blocks the anon, authenticated, and service_role roles from setting it, so
-- only a direct database statement run as postgres can flip it.
-- ---------------------------------------------------------------------------
create table public.users (
  id           uuid primary key references auth.users (id) on delete cascade,
  email        text not null unique,
  full_name    text,
  is_operator  boolean not null default false,
  created_at   timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- memberships: which user belongs to which client, and in what role
-- ---------------------------------------------------------------------------
create type public.membership_role as enum ('owner', 'staff');

create table public.memberships (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.users (id) on delete cascade,
  client_id   uuid not null references public.clients (id) on delete cascade,
  role        public.membership_role not null default 'staff',
  created_at  timestamptz not null default now(),
  unique (user_id, client_id)
);

-- ---------------------------------------------------------------------------
-- events: append-only activity log with a jsonb payload
-- client_id is nullable so system-level events can land here too
-- ---------------------------------------------------------------------------
create table public.events (
  id          uuid primary key default gen_random_uuid(),
  client_id   uuid references public.clients (id) on delete cascade,
  event_type  text not null,
  payload     jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- prospects: the sales console's saved leads
-- Columns match app/routers/sales_preview.py's save_lead()/customize_prospect()
-- exactly, folding in the three follow-up migrations the source repo applied
-- incrementally (website_url, note/selected_gap_indices/customized_at).
-- ---------------------------------------------------------------------------
create table public.prospects (
  id                     uuid primary key default gen_random_uuid(),
  agent_id               uuid references public.users (id),
  business_name          text not null,
  contact_name           text,
  contact_email          text,
  city                   text,
  current_score          integer,
  preview_id             uuid,
  website_url            text,
  note                   text,
  selected_gap_indices   jsonb not null default '[]'::jsonb,
  customized_at          timestamptz,
  created_at             timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- indexes
-- ---------------------------------------------------------------------------
create index memberships_user_idx on public.memberships (user_id);
create index memberships_client_idx on public.memberships (client_id);
create index events_client_idx on public.events (client_id, created_at desc);
create index events_payload_idx on public.events using gin (payload);
create index prospects_agent_idx on public.prospects (agent_id);

-- ---------------------------------------------------------------------------
-- trigger: create a public.users row whenever auth creates a user
-- ---------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.users (id, email, full_name)
  values (new.id, new.email, coalesce(new.raw_user_meta_data ->> 'full_name', ''));
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- trigger: guard the operator flag
-- Blocks every API-facing role, including service_role, from setting or
-- changing is_operator. Only a direct statement run as postgres passes.
-- ---------------------------------------------------------------------------
create or replace function public.guard_operator_flag()
returns trigger
language plpgsql
as $$
begin
  if tg_op = 'INSERT' then
    if new.is_operator
       and current_user in ('anon', 'authenticated', 'service_role') then
      raise exception 'The operator flag is set only by a direct database statement.'
        using errcode = '42501';
    end if;
  elsif tg_op = 'UPDATE' then
    if new.is_operator is distinct from old.is_operator
       and current_user in ('anon', 'authenticated', 'service_role') then
      raise exception 'The operator flag is set only by a direct database statement.'
        using errcode = '42501';
    end if;
  end if;
  return new;
end;
$$;

create trigger users_guard_operator_flag
  before insert or update on public.users
  for each row execute function public.guard_operator_flag();

-- ---------------------------------------------------------------------------
-- RLS helper functions (security definer avoids recursive policy evaluation)
-- ---------------------------------------------------------------------------
create or replace function public.is_operator()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select coalesce(
    (select u.is_operator from public.users u where u.id = auth.uid()),
    false
  );
$$;

create or replace function public.is_member_of(target_client uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.memberships m
    where m.user_id = auth.uid()
      and m.client_id = target_client
  );
$$;

create or replace function public.is_owner_of(target_client uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.memberships m
    where m.user_id = auth.uid()
      and m.client_id = target_client
      and m.role = 'owner'
  );
$$;

create or replace function public.shares_client_with(target_user uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.memberships mine
    join public.memberships theirs on theirs.client_id = mine.client_id
    where mine.user_id = auth.uid()
      and theirs.user_id = target_user
  );
$$;

grant execute on function public.is_operator() to anon, authenticated;
grant execute on function public.is_member_of(uuid) to anon, authenticated;
grant execute on function public.is_owner_of(uuid) to anon, authenticated;
grant execute on function public.shares_client_with(uuid) to anon, authenticated;

-- ---------------------------------------------------------------------------
-- table grants (RLS decides which rows pass through)
-- ---------------------------------------------------------------------------
grant usage on schema public to anon, authenticated, service_role;
grant select, insert, update, delete on all tables in schema public to authenticated, service_role;

-- ---------------------------------------------------------------------------
-- enable row-level security on every table
-- ---------------------------------------------------------------------------
alter table public.clients enable row level security;
alter table public.users enable row level security;
alter table public.memberships enable row level security;
alter table public.events enable row level security;
alter table public.prospects enable row level security;

-- ---------------------------------------------------------------------------
-- clients: members read their client, operators read every client, only
-- owners change/delete. Inserts run through the backend service role at
-- signup, so no insert policy exists here.
-- ---------------------------------------------------------------------------
create policy clients_select on public.clients
  for select using (public.is_operator() or public.is_member_of(id));

create policy clients_update on public.clients
  for update using (public.is_owner_of(id))
  with check (public.is_owner_of(id));

create policy clients_delete on public.clients
  for delete using (public.is_owner_of(id));

-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------
create policy users_select on public.users
  for select using (
    id = auth.uid()
    or public.is_operator()
    or public.shares_client_with(id)
  );

create policy users_update on public.users
  for update using (id = auth.uid())
  with check (id = auth.uid());

-- ---------------------------------------------------------------------------
-- memberships
-- ---------------------------------------------------------------------------
create policy memberships_select on public.memberships
  for select using (public.is_operator() or public.is_member_of(client_id));

create policy memberships_insert on public.memberships
  for insert with check (public.is_owner_of(client_id));

create policy memberships_update on public.memberships
  for update using (public.is_owner_of(client_id))
  with check (public.is_owner_of(client_id));

create policy memberships_delete on public.memberships
  for delete using (public.is_owner_of(client_id));

-- ---------------------------------------------------------------------------
-- events: members read their client's events, operators read everything
-- including system events with no client_id. Only the backend writes.
-- ---------------------------------------------------------------------------
create policy events_select on public.events
  for select using (
    public.is_operator()
    or (client_id is not null and public.is_member_of(client_id))
  );

-- ---------------------------------------------------------------------------
-- prospects: agents see their own leads, operators see every lead. Only the
-- backend writes prospects (service-role client in save_lead()), which
-- bypasses RLS regardless of policy -- no insert/update/delete policy is
-- defined, matching the events precedent.
-- ---------------------------------------------------------------------------
create policy prospects_select on public.prospects
  for select using (
    public.is_operator()
    or agent_id = auth.uid()
  );
