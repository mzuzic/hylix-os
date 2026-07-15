# AI Sales OS — Mobile Story

Frame: **desktop = engine room** (automations, heavy workflows),
**mobile = cockpit** (briefs, dashboard, quick actions, voice). For local
businesses — reps in trucks, owners on job sites — mobile is a headline
feature, not a footnote.

## What works from a phone (as of July 2026)

- **Cowork on mobile/web** — launched Jul 7, 2026 (beta, Max plan first, other
  plans rolling out). Open from the Claude iOS/Android app sidebar. Cloud
  sessions keep running with the laptop closed; start a task at the desk,
  check status and pick up output on the phone.
- **Connectors** — remote MCP connectors (HubSpot, Google Workspace, our Sales
  OS server) work on all Claude clients including mobile. "What's the latest
  on the Henderson deal?" works from the road.
- **Dashboard** — cloud-hosted artifact/HTML is just a URL; any phone browser.
- **Voice dictation** — field reps log updates hands-free: "log that the client
  wants the premium package, draft the follow-up."

## What doesn't reach mobile

Anything local: desktop extensions, local MCP servers, local files. Hence the
hosted Second Brain (remote connector) instead of a desktop folder.

## Caveats to scope around

- Mobile Cowork is beta, Max-tier first — verify plan availability per client.
- Cloud scheduled tasks + MCP connectors unreliable (known bug,
  [issue #43397](https://github.com/anthropics/claude-code/issues/43397)) —
  run automations on one anchor desktop or server-side.
- No per-phone setup exists or is needed: connectors configured on web sync to
  mobile automatically (~30-min onboarding step per client).

Sources: [Cowork web/mobile announcement](https://claude.com/blog/cowork-web-mobile),
[Cowork scheduled tasks](https://support.claude.com/en/articles/13854387-schedule-recurring-tasks-in-claude-cowork),
[Remote MCP connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)
