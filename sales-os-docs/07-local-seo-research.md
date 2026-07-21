# Local SEO Research → Marketing Module SOPs

Deep-research run 2026-07-20 (19 sources, 94 claims extracted, 25 adversarially
verified: 23 confirmed / 2 refuted). Each section below becomes one SOP in
`sops.py`. Evidence quality noted inline; see Caveats before promising numbers
to clients.

---

## 1. SOP candidate: `gbp_audit` — Google Business Profile audit & fix

**Trigger:** client onboarding + quarterly re-run.
**Inputs:** public GBP listing (web fetch), competitors' listings, `profile/offers`, `profile/service-area`.
**Output:** prioritized fix checklist to `marketing/gbp-audit-<date>`.

Checklist in verified impact order ([Whitespark 2026 survey](https://whitespark.ca/local-search-ranking-factors/), 47 experts):

1. **Primary category correct?** #1 ranking factor (100% consensus). Wrong
   category is also the #2 cause of ranking drops (98.6%). Audit against top-3
   ranking competitors' categories. Up to 10 categories total (1 primary + 9
   secondary); add all relevant secondaries.
2. **Physical address in the target city, visible.** #4 factor (93.8%).
   Service-area businesses hiding their address rank measurably worse
   ([Sterling Sky 2025, n=8,186](https://www.sterlingsky.ca/what-gets-you-ranking-for-near-me-2025/),
   replicated before/after). If the client has a real in-city address, show it.
3. **Hours cover peak search times.** "Open at time of search" = 83.3%.
   Check hours are complete, holiday hours set.
4. **Services list filled with every pre-defined + custom service.** Verified
   ranking lift for niche service keywords
   ([Sterling Sky retest](https://www.sterlingsky.ca/services-in-google-business-profile-impact-ranking/), medium confidence).
5. Business title: keywords help (98.2%) but see Guardrails — never stuff.
6. Photos, Q&A, attributes: complete for conversion; weaker ranking evidence.

---

## 2. SOP candidate: `review_engine` — request + respond + monitor

**Trigger:** review_request fires on job-won (hook from `crm_sync`); review_response fires on new review (Gmail notification / heartbeat).
**Inputs:** `deal/<customer>`, `profile/tone_of_voice`, `marketing/gbp-profile` (static review link), `marketing/reviews-log`.
**Output:** personalized ask drafts; tiered replies; log lines to `marketing/reviews-log`.

Verified rules to encode:

- **Sprint to 10 reviews, then optimize velocity, not totals.** Ranking bump
  at 9→10 reviews, none 10→11, plateau 16→31
  ([Sterling Sky controlled tests](https://www.sterlingsky.ca/number-of-reviews-impact-ranking/)).
- **Recency beats count**: one documented case dropped after 18 days without a
  new review. (NOTE: generalized "3-week threshold" was REFUTED in
  verification — cite only the 18-day anecdote.) Target: ≥1-2 new reviews
  every month, forever.
- **Respond to every review**: 80% of consumers favor businesses that respond
  to all reviews; 50% are put off by templated replies
  ([BrightLocal 2026, n=1,002](https://www.brightlocal.com/research/local-consumer-review-survey/)).
  Replies must be personalized (reference the job) and mention service+city
  naturally.
- **Tiered autonomy**: 4-5★ → auto-postable; ≤3★ → draft + owner approval,
  de-escalate, own what's true, take offline, never argue/admit liability.
- Conversion thresholds to report to clients: 68% require 4★+, 74% want a
  review from the last 3 months, only 9% accept ≤5 reviews.

---

## 3. SOP candidate: `local_content` — service+city pages & GBP posts

**Trigger:** monthly content calendar run.
**Inputs:** `profile/offers`, `profile/pricing` (+ `project_pnl` margins to prioritize services), transcripts/reviews for customer language, `marketing/keywords`.
**Output:** page drafts + weekly GBP post drafts to `marketing/content-calendar`.

Verified rules:

- **One dedicated page per service** — #1 local-organic factor (100%).
  Never combine services on one page.
- **City/neighborhood keywords in content** — #2 factor (90.5%). Build
  service × city matrix from the client's actual service area.
- **Use customer language from transcripts/reviews**, not industry jargon
  (our unique data edge; also feeds review-keyword relevance).
- **Prioritize high-margin services** (from `finance` module P&L) — marketing
  informed by finance.
- Quality inbound links are #3 (89.0%) — see section 4 for how to earn them.

---

## 4. SOP candidate: `ai_visibility` — get found by AI Overviews & ChatGPT

**Trigger:** quarterly.
**Inputs:** web search for existing mentions/list presence; `profile/offers`.
**Output:** target list of "best-of" lists, local press, associations to `marketing/ai-visibility-plan`.

Why it exists (all point-in-time, spring 2025 data — re-verify quarterly):

- AI Overviews on ~40% of local queries; ~17% of commercial ones
  ([Local Falcon, 60k queries](https://www.localfalcon.com/blog/whitepaper-studies-the-impact-of-google-ai-overviews-on-local-business-search-visibility)).
- AI local packs surface only ~⅓ as many unique businesses as 3-packs —
  winner-take-more ([Sterling Sky](https://www.sterlingsky.ca/the-state-of-local-seo-in-2026/)).
- 45% of consumers now consult ChatGPT/AI for local recommendations
  (Google fell 83%→71%) ([BrightLocal 2026](https://www.brightlocal.com/research/local-consumer-review-survey/)).

Verified levers ([Whitespark 2026 AI-search dimension](https://whitespark.ca/local-search-ranking-factors/)):
1. **Presence on expert-curated "best of <city>" lists** — #1 (100%)
2. Prominence on key industry-relevant domains (93.3%)
3. Quality **unstructured citations** — local news articles, industry
   association pages (89.4%)

NAP directory consistency = table stakes only; earned mentions are the lever.
Tactics: pitch local journalists, join associations, get on curated lists,
sponsor local events (earns both links for §3 and mentions for AI).

---

## 5. SOP candidate: `seo_reporting` — prove improvement monthly

**Trigger:** monthly, after metrics snapshots land.
**Inputs:** `marketing/seo-metrics-<month>` snapshots (GSC export, GBP
performance export, geogrid tracker report), `marketing/reviews-log`,
`deal/*` + `finance/ledger-*` for attribution.
**Output:** branded PDF report (reuse pdf.py pattern) + `marketing/report-<month>`.

Verified KPI rules:

- **Never use raw GBP call counts as the health KPI** — calls decline even
  when rankings hold (Google hiding call buttons; 179-profile dataset,
  [Sterling Sky](https://www.sterlingsky.ca/the-state-of-local-seo-in-2026/)).
  Track: geogrid position, GSC impressions/clicks, website clicks, attributed
  leads.
- Always report vs baseline month AND 3-month trend; attribute changes to
  work shipped (posts, reviews gained, fixes) so improvement justifies the
  invoice.
- End every report with business outcomes: calls → quotes (`deal/*`) → won
  jobs → revenue (`finance/*`). Our differentiator.
- Context for client expectations: paid units are eating the SERP (local pack
  ads ~1%→~22% of tracked mobile queries in 2025; LSAs 11%→31%) — set the
  hybrid organic+LSA conversation early with trades.

---

## 6. Guardrails — embed in EVERY marketing SOP

Verified penalty mechanics ([Google's own docs](https://support.google.com/business/answer/14114287?hl=en) + [Whitespark negative factors](https://whitespark.ca/local-search-ranking-factors/)):

- ❌ **Fake/virtual/PO-box addresses** — #1 suspension risk (100% consensus)
- ❌ **Review gating** (pre-filtering unhappy customers) — policy violation
- ❌ **Fake/purchased/incentivized reviews** — Google can freeze new reviews,
  unpublish ALL existing reviews for a period, and pin a PUBLIC "fake reviews
  removed" warning on the profile (observed in the wild since ~May 2025)
- ❌ **Keyword-stuffing the business name** — was warning-first in 2020
  (60% warnings, [Sterling Sky 50-case study](https://www.sterlingsky.ca/50-cases-of-keyword-spam/));
  enforcement tightened since — treat as unsafe. (Exact 20%/20% suspension
  split claim was REFUTED — don't cite it.)
- ❌ Duplicate same-category listings at one address ("The Filter")
- ❌ Never mark a business "permanently closed" as a tactic — top ranking-drop factor

---

## Caveats (say these to clients honestly)

- Evidence base is concentrated: Whitespark (expert opinion, not causation),
  Sterling Sky (small-n case studies, no control groups), BrightLocal
  (self-reported preferences), + Google docs (penalties only). Google
  confirms almost none of these as ranking signals.
- AI-surface numbers are spring-2025 snapshots in a fast-moving area.
- Proximity remains a hard constraint on map-pack results — set expectations
  per client location; geogrid reports make this visible honestly.

## Open questions (from the research)

1. What drives inclusion in AI local packs beyond list presence/mentions — no controlled study yet.
2. Does recency-over-count replicate at scale, and what monthly velocity is "enough" per vertical?
3. Current enforcement rate for keyword-stuffed names under AI-based spam detection?
4. Measured ROI crossover: organic local SEO vs LSAs for small service businesses?

## Implementation order

1. `review_engine` (ships with Zapier bridge; highest ROI, engine already designed)
2. `gbp_audit` (pure checklist, no integrations)
3. `local_content` (needs `profile/service-area` convention)
4. `seo_reporting` (needs geogrid subscription ~$40/mo + GSC exports; PDF template)
5. `ai_visibility` (quarterly, lowest urgency)
