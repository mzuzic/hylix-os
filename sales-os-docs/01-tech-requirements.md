# AI Sales OS — Tech Requirements (Generic Offer)

Scope: standard reference stack for local-business clients. Assumed client stack:
HubSpot-type CRM, Google Workspace, meeting transcription.

## 1. Connectors (per client, their own OAuth)

| Integration | Path | Notes |
|---|---|---|
| CRM | HubSpot (or Pipedrive) directory connector | Needs CRM user with read/write scopes. Anything exotic = paid extra |
| Google Workspace | First-party Gmail/Calendar/Drive connectors | Workspace admin must allow third-party OAuth — common onboarding blocker |
| Transcription | Standardize on Fathom (easiest API/MCP) | Fireflies workable; Zoom/Meet native transcripts messier — treat as prerequisite, not integration work |

Client data flows directly between their tools and Claude — never through our
infrastructure.

## 2. Second Brain

Per-client store of sales intelligence, hosted on our thin MCP server (see
02-architecture.md). Fixed schema so skills/tools find things reliably:

- `profile/icp`, `profile/offers`, `profile/tone_of_voice`
- `deal/<company>` — running deal notes
- `transcript/<company>-<date>`

Retention/size policy needed so it doesn't bloat.

## 3. Automations

- Cowork scheduled tasks for morning routine / CRM sync (zero infra).
- Known limitation (Jul 2026): cloud scheduled tasks unreliable with MCP
  connectors — anchor automations to one desktop machine, or run them
  server-side on our MCP backend via cron.

## 4. Skills (delivered as a Cowork plugin)

`pre-call-brief`, `post-call-followup`, `crm-sync`, `call-scoring`.
Each has a defined input/output contract against the Second Brain schema.
Plugin = the productized, installable unit.

## 5. Dashboard

- Cowork artifact: live HTML view, pulls fresh connector data on open, no hosting.
- Works on mobile via browser/app. Design mobile-first: today's calls, top 3
  priorities, one-tap pre-call brief.

## Cross-cutting

- **Licensing:** each client needs their own Claude subscription (Team plan for
  multi-rep; Max currently required for mobile Cowork beta). Drives pricing.
- **Human-in-the-loop:** outbound email and CRM writes draft-only at first.
- **Onboarding prerequisites:** CRM admin access, Workspace admin approval,
  transcription tool live, client provides ICP/offer/tone docs. ~1–2 weeks/client.
