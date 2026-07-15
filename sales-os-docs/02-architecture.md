# AI Sales OS — Architecture: Thin MCP Server

## Decision

Rejected: heavy aggregator API proxying all client data (HubSpot, Gmail,
transcripts through our backend). Makes us custodian of every client's
credentials — token management, uptime, breach liability, SOC 2 exposure — and
duplicates what directory connectors do free with the client's own OAuth.

Chosen: **thin server**. Clients connect their data tools directly to Claude;
our server hosts only what's missing:

1. **Second Brain, hosted** — per-client sales intelligence store. Being a
   remote MCP connector, it reaches mobile and solves local-folder sync in one move.
2. **SOPs as tools** — `get_precall_brief`, `draft_followup`, `score_call`
   encode our sales SOPs. Update once, every client instantly gets it. This is
   the product moat and the argument for a monthly fee.
3. **Server-side scheduled jobs** (post-MVP) — cron on our backend writes
   morning-routine output into the Second Brain, sidestepping the Cowork
   scheduled-task/connector reliability bug.

Paired with a **Cowork plugin** for desktop users bundling the skills (skills
don't travel via MCP; plugins are their delivery vehicle).

> Client's connectors for their data. Our MCP server for intelligence + SOPs.
> Plugin for desktop skills. Centralize our IP without centralizing their credentials.

## Thin-server principle

The server makes **no LLM calls**. Tools return context + SOP instructions;
the Claude client does the generation. Keeps the server cheap, fast, and
model-agnostic.

## Connector distribution (mobile)

Connectors live on the client's Claude account, not the device. Configure once
on claude.ai web → syncs to mobile/desktop/Cowork automatically. Team plan:
org Owner enables in Organization settings → each rep self-serves OAuth.
Constraint: Claude connects from Anthropic's cloud, so our server must be
publicly reachable (HTTPS, no VPN-only hosts).

## MVP (built, 9/9 smoke checks pass)

- Python + FastMCP 3.x, HTTP transport at `/mcp`
- Bearer token per client (`SALES_OS_TOKENS` env: token → client_id);
  multi-tenant SQLite, tenant isolation verified
- Tools: `whoami`, `second_brain_{list,read,write,delete}`,
  `get_precall_brief`, `draft_followup`, `score_call`
- Docker deploy (Fly.io/Railway/VPS + persistent volume)

## Post-MVP roadmap

OAuth (replace bearer tokens) → Postgres (past ~dozens of tenants) → rate
limiting + audit log → DB-backed token management → server-side cron jobs.

## Platform positioning

Cowork-first for local businesses (near-zero infra; client owns data +
subscription; we sell setup + plugin + monthly retainer). SDK/server route
reserved as premium tier for guaranteed unattended automation.
