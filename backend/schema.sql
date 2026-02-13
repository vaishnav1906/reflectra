-- Reflectra DB schema (PostgreSQL + pgvector)

create extension if not exists pgcrypto;
create extension if not exists vector;

create table if not exists users (
    id uuid primary key default gen_random_uuid(),
    email varchar(320) not null unique,
    display_name text,
    created_at timestamptz not null default now()
);

create table if not exists conversations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    title text,
    mode text not null default 'reflection',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_conversations_user_id on conversations(user_id);
create index if not exists idx_conversations_user_created on conversations(user_id, created_at desc);

create table if not exists messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references conversations(id) on delete cascade,
    user_id uuid not null references users(id) on delete cascade,
    role text not null,
    content text not null,
    embedding vector(1536),
    token_count integer,
    created_at timestamptz not null default now()
);

create index if not exists idx_messages_conversation_created on messages(conversation_id, created_at asc);
create index if not exists idx_messages_user_id on messages(user_id);
create index if not exists idx_messages_role on messages(role);

-- For embedding similarity search. Requires ANALYZE after data load.
create index if not exists idx_messages_embedding_ivfflat
    on messages using ivfflat (embedding vector_cosine_ops) with (lists = 100);

create table if not exists personality_profile (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null unique references users(id) on delete cascade,
    openness numeric(4,3),
    conscientiousness numeric(4,3),
    extraversion numeric(4,3),
    agreeableness numeric(4,3),
    neuroticism numeric(4,3),
    themes jsonb not null default '{}'::jsonb,
    traits jsonb not null default '{}'::jsonb,
    values jsonb not null default '{}'::jsonb,
    stressors jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

create index if not exists idx_personality_profile_user_id on personality_profile(user_id);

create table if not exists behavioral_insights (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    conversation_id uuid references conversations(id) on delete set null,
    insight_text text not null,
    tags text[] not null default '{}',
    confidence numeric(4,3),
    created_at timestamptz not null default now()
);

create index if not exists idx_behavioral_insights_user_created on behavioral_insights(user_id, created_at desc);
create index if not exists idx_behavioral_insights_conversation_id on behavioral_insights(conversation_id);

create table if not exists reflection_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    conversation_id uuid references conversations(id) on delete set null,
    prompt text not null,
    response text not null,
    sentiment numeric(4,3),
    created_at timestamptz not null default now()
);

create index if not exists idx_reflection_logs_user_created on reflection_logs(user_id, created_at desc);
create index if not exists idx_reflection_logs_conversation_id on reflection_logs(conversation_id);

-- Supabase RLS policies (optional). Enable if using auth.uid().
-- alter table users enable row level security;
-- alter table conversations enable row level security;
-- alter table messages enable row level security;
-- alter table personality_profile enable row level security;
-- alter table behavioral_insights enable row level security;
-- alter table reflection_logs enable row level security;
--
-- create policy "Users can view own record" on users
--   for select using (id = auth.uid());
--
-- create policy "Users can manage own conversations" on conversations
--   for all using (user_id = auth.uid()) with check (user_id = auth.uid());
--
-- create policy "Users can manage own messages" on messages
--   for all using (user_id = auth.uid()) with check (user_id = auth.uid());
--
-- create policy "Users can manage own personality profile" on personality_profile
--   for all using (user_id = auth.uid()) with check (user_id = auth.uid());
--
-- create policy "Users can manage own insights" on behavioral_insights
--   for all using (user_id = auth.uid()) with check (user_id = auth.uid());
--
-- create policy "Users can manage own reflections" on reflection_logs
--   for all using (user_id = auth.uid()) with check (user_id = auth.uid());
