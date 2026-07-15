# Sales OS — Thin MCP Server (MVP)

A multi-tenant remote MCP server hosting the **Second Brain** (per-client sales
intelligence) and **SOP-driven tools** for the AI Sales Operating System.

**Design principle: thin.** Client data (CRM, email, calendar) never touches this
server — clients connect those directly via Claude's directory connectors. This
server makes **no LLM calls**: tools return context + SOP instructions, and the
Claude client does the generation. Your SOPs live in `sops.py` — edit once, every
client gets the update instantly.

## Tools

| Tool | Purpose |
|---|---|
| `whoami` | Connectivity check; shows tenant |
| `second_brain_list / read / write / delete` | CRUD on per-client docs (ICP, offers, tone, deal notes, transcripts) |
| `get_precall_brief(lead_name, company)` | SOP + profile + matching deal history for a pre-call brief |
| `draft_followup(deal_name, transcript?)` | SOP + tone + offers + notes for follow-up email / proposal / CRM update |
| `score_call(transcript, rep_name?)` | Coaching rubric SOP + ICP context |
| `create_quote(job_description, customer?)` | Quote SOP + rate card + tone for a dictated job |
| `list_sops / get_sop(name)` | Fetch latest SOPs — used by client-side stub skills |

## MVP flow: dictate a job → get a quote

1. Rep dictates into the Claude mobile app: "kitchen repaint for the Hendersons,
   about 40 square meters, some plaster repair."
2. The `create-quote` stub skill (see `client-skills/create-quote.zip`, uploaded
   once per client via Settings → Skills) triggers and calls `create_quote`.
3. Server returns the quote SOP + the client's rate card (`profile/pricing`),
   offers, and tone. Claude drafts the quote for review and saves it to the deal.

SOPs live in `sops.py` (`REGISTRY`) — edit centrally, every client's next call
gets the update. Stub skills never need re-uploading.

Doc conventions: `profile/icp`, `profile/offers`, `profile/tone_of_voice`,
`deal/<company>`, `transcript/<company>-<date>`.

## Run locally

```bash
pip install -r requirements.txt
export SALES_OS_TOKENS='{"long-random-secret":"acme-plumbing"}'
python server.py   # serves http://0.0.0.0:8000/mcp
python smoke_test.py   # 9 end-to-end checks (uses test tokens, see file)
```

## Auth & tenancy

`SALES_OS_TOKENS` is a JSON map of `token -> client_id`. Every doc is scoped to
the authenticated tenant — one server, many clients, no data crossover
(verified in smoke test). Generate tokens with
`python -c "import secrets; print(secrets.token_urlsafe(32))"`.

Adding a client = add one entry to `SALES_OS_TOKENS`, restart, hand them the token.

## Deploy (Fly.io example)

```bash
fly launch --no-deploy            # uses the Dockerfile
fly volumes create data --size 1  # persistent SQLite
fly secrets set SALES_OS_TOKENS='{"<token>":"<client-id>"}'
fly deploy
```

Any Docker host works (Railway, Render, a VPS). Requirements: public HTTPS URL,
persistent disk for `SALES_OS_DB` (default `/data/sales_os.db` in the container).

## Connect from Claude

Web (syncs to mobile/desktop automatically): **Settings → Connectors → Add custom
connector** → URL `https://<your-app>.fly.dev/mcp`. When prompted for
authentication, supply the client's bearer token.
Note: Claude connects from Anthropic's cloud, so the server must be publicly
reachable — no localhost, no VPN-only hosts.

## MVP limits / next steps

- Bearer tokens are fine for pilots; move to OAuth before scale.
- SQLite is fine to ~dozens of tenants; swap `storage.py` for Postgres after.
- No rate limiting or audit log yet.
- Token rotation requires a restart (env var); move tokens to the DB later.
