-- Run this in Supabase Dashboard > SQL Editor.
create table if not exists public.conversations (
  user_id uuid not null references auth.users(id) on delete cascade,
  conversation_id text not null,
  title text not null default 'New conversation',
  messages jsonb not null default '[]'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (user_id, conversation_id)
);
create index if not exists conversations_user_updated_idx
  on public.conversations (user_id, updated_at desc);
alter table public.conversations enable row level security;
drop policy if exists "Users can read their own conversations" on public.conversations;
create policy "Users can read their own conversations" on public.conversations
  for select to authenticated using (auth.uid() = user_id);
drop policy if exists "Users can insert their own conversations" on public.conversations;
create policy "Users can insert their own conversations" on public.conversations
  for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "Users can update their own conversations" on public.conversations;
create policy "Users can update their own conversations" on public.conversations
  for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "Users can delete their own conversations" on public.conversations;
create policy "Users can delete their own conversations" on public.conversations
  for delete to authenticated using (auth.uid() = user_id);
grant select, insert, update, delete on public.conversations to authenticated;
