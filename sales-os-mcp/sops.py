"""SOP templates returned by the server. The server stays thin: it assembles
context + instructions, and the Claude client does the actual generation.
Edit these once — every connected client gets the update instantly."""

PRECALL_BRIEF_SOP = """\
You are preparing a pre-call brief for a sales rep. Using ONLY the context
provided below, produce a one-page brief with these sections:

1. LEAD SNAPSHOT — who they are, company, role, anything known from deal notes.
2. FIT SCORE (1-10) — score the lead against the Ideal Customer Profile and
   justify in 2 sentences. If ICP data is missing, say so instead of guessing.
3. HISTORY — bullet the last interactions from deal notes/transcripts, newest first.
4. TALKING POINTS — 3-5 points connecting our offers to their likely needs.
5. RISKS & OBJECTIONS — likely objections and one suggested response each.
6. GOAL FOR THIS CALL — one concrete outcome to drive toward.

Match the tone-of-voice guidelines if provided. Keep the whole brief under 400 words.
Flag any missing information explicitly rather than inventing details."""

FOLLOWUP_SOP = """\
You are drafting a post-call follow-up for a sales rep to review and send.
Using ONLY the context provided below (transcript, deal notes, offers, tone):

1. FOLLOW-UP EMAIL — under 180 words. Reference 2-3 specific things actually
   said in the call. Address the main objection raised. One clear call to action.
2. PROPOSAL OUTLINE — only if the call indicated buying intent: scope,
   the specific offer(s) discussed, pricing placeholder, next steps.
3. CRM UPDATE SUGGESTION — one-line status, next action, and follow-up date.

Match the tone-of-voice guidelines exactly. Never invent commitments,
prices, or dates not present in the context. Mark placeholders as [PLACEHOLDER].
This is a DRAFT for human review — do not present it as sent."""

QUOTE_SOP = """\
You are creating a customer quote from a job description a sales rep dictated
(possibly rough voice-to-text: expand shorthand, fix obvious transcription
errors, but never invent job details). Using ONLY the provided context:

1. PARSE THE JOB — extract: customer, job type, quantities/dimensions,
   materials, timeline, special conditions. List anything CRITICAL that is
   missing and ASK for it before producing a final quote (labor quantity,
   dimensions, or customer name are critical; nice-to-haves are not).
2. PRICE IT — apply the rate card (profile/pricing) exactly. Every line item:
   description, quantity, unit rate, line total. Never invent rates: if an
   item has no rate in the rate card, include it as [RATE NEEDED]. Apply
   minimum-charge and call-out rules if the rate card defines them.
3. FORMAT THE QUOTE — professional plain-text/markdown quote: business name,
   date, customer, scope summary (2-3 sentences), line items table, subtotal,
   tax as [TAX] unless the rate card defines it, total, validity period
   (default 14 days unless rate card says otherwise), payment terms from
   profile/offers or rate card.
4. MATCH TONE — apply profile/tone_of_voice to the scope summary and any
   cover note.
5. SAVE & NEXT STEPS — write the quote to the Second Brain as
   deal/<customer-name> (append if the deal exists), then suggest: send-ready
   email draft? CRM update?
6. BRANDED PDF — once the user approves the numbers, call `render_quote_pdf`
   with the STRUCTURED line items (description, quantity, unit, unit_price),
   the customer, a short scope_summary, any notes/terms, and tax_rate if the
   rate card defines one. The server computes the amounts and totals and
   returns a `download_url` for a polished branded PDF (branding comes from
   profile/branding). Do NOT pre-total the lines yourself. Represent any
   discount as its own line item with a NEGATIVE unit_price (e.g. -540). Give
   the user the download_url — they can open it or send it to the customer.

This is a DRAFT for human review. Never present it as sent or final."""

SCORECALL_SOP = """\
You are scoring a sales call from its transcript. Apply this rubric,
scoring each dimension 1-10 with a one-sentence justification quoting the
transcript where possible:

1. DISCOVERY — did the rep uncover needs, budget, timeline, decision process?
2. LISTENING RATIO — did the prospect talk more than the rep?
3. VALUE FRAMING — were offers tied to the prospect's stated problems?
4. OBJECTION HANDLING — were objections acknowledged and addressed, not dodged?
5. NEXT STEP — did the call end with a concrete, time-bound next step?

Then give: OVERALL SCORE (average), TOP STRENGTH, #1 COACHING PRIORITY with a
specific alternative phrasing the rep could have used. Be direct but constructive.
If the transcript is too short or garbled to score a dimension, mark it N/A."""

SOW_SUMMARY_SOP = """\
You are turning a meeting or site-visit transcript into shareable documentation.
Using ONLY the transcript and provided context, produce:

1. POST-CALL NOTES — attendees, date, purpose; then key moments as bullets,
   each with its approximate timestamp from the transcript.
2. SCOPE OF WORK — what was agreed: deliverables, materials, timeline,
   price points mentioned. List EXCLUSIONS explicitly (things discussed but
   not agreed). Mark anything ambiguous as [TO CONFIRM] — never guess scope.
3. OPEN QUESTIONS — anything the client asked that wasn't answered.
4. TWO OUTPUTS — (a) client-facing version in the business tone (confirm
   scope, next steps), (b) internal handoff for technicians: plain, specific,
   no sales language.
5. SAVE — append to deal/<customer> and suggest sending (a) for approval.

Drafts only; never present the SOW as a signed agreement."""

INBOX_TRIAGE_SOP = """\
You are running an inbox triage pass over unread customer emails (via the
client's Gmail connector). For each unread customer email:

1. CLASSIFY — inquiry / scheduling / complaint / billing / spam-ignore.
2. DRAFT a reply in the business tone using Second Brain context (deal
   history, offers, pricing). NEVER send — save as Gmail draft or present
   for approval. Never invent availability, prices, or commitments.
3. ESCALATE — complaints and anything angry, legal, or safety-related get
   flagged URGENT to the owner with a one-line summary, on top of the draft.
4. LOG — append a one-line interaction note to the matching deal/<customer>;
   create the deal doc if it's a new lead, and say so in the summary.
5. SUMMARY — end with: N emails triaged, drafts ready, urgent items.

Only touch unread emails from real customers/leads. Skip newsletters,
receipts, and internal mail."""

CRM_SYNC_SOP = """\
You are running daily pipeline hygiene against the client's CRM (via their
connector) and the Second Brain deal files.

1. COLD DEALS — flag active deals with no interaction in 14+ days (use
   profile/crm_rules if it overrides). Suggest one next action each.
2. STATUS DRIFT — where the latest interactions (emails, transcripts, notes)
   imply a different stage than the CRM shows, propose the update with a
   one-line justification.
3. CLOSED JOBS — deals clearly won or lost: propose closing them out, and
   for wins, trigger-suggest the review-request and invoice follow-ups.
4. APPLY — present all proposed changes as a checklist for approval BEFORE
   writing to the CRM, unless profile/crm_rules explicitly allows auto-apply
   for a change type. Sync approved changes to both CRM and deal/ files.

Output: cold list, proposed updates, closed list — short enough to read on
a phone."""

OPEN_LOOPS_SOP = """\
You are finding everything that risks slipping through the cracks. Scan the
Second Brain (deal files, transcripts, recent events) for:

1. UNANSWERED customer questions (asked in email/call, no reply since).
2. PROMISED follow-ups ("I'll get back to you on X") not yet done.
3. UNRESOLVED complaints or service issues without a closing note.
4. STALLED deals — quote sent, no response, no follow-up scheduled.

Output a ranked report (most at-risk first): customer, what's open, how long,
suggested next action with a draft opener line. End with counts by category.
If evidence is thin, list it under 'possibly stale — verify' rather than
asserting. This report is for the owner; keep it scannable."""

MONTHLY_FINANCE_SOP = """\
You are producing the monthly finance report from raw documents the client
dropped into their folder (bank statements, supplier invoices, receipts —
process them client-side; NEVER copy raw statements into the Second Brain).

1. EXTRACT — transactions from each document: date, payee, amount, category.
   Flag unreadable/ambiguous items as [UNCLEAR] with the filename.
2. CATEGORIZE — against finance/profile/budget categories (materials, fuel,
   subs, tools, marketing, admin...). If no budget doc exists, propose one
   first from the data.
3. REPORT — spend by category vs budget; three sections: WHERE THE MONEY
   WENT, WHAT WENT WELL (under budget, good margins), WHERE TO SAVE NEXT
   MONTH (specific, e.g. duplicate subscriptions, supplier price creep).
4. STORE — write only the summary report and category totals to
   finance/library/monthly-<year>-<month>. Raw documents stay in the
   client's folder.

Numbers must add up — reconcile totals against the statements and say so.
This is bookkeeping support, not tax or accounting advice; recommend their
accountant reviews it."""

DEMAND_MINING_SOP = """\
You are mining the client's own communications for unmet demand. Scan
support tickets, email history, call transcripts, and past invoices in the
Second Brain (and via connectors where available):

1. RECURRING ASKS — questions or requests that appear 3+ times and aren't
   covered by profile/offers. Count occurrences and quote 1-2 examples each.
2. UPSELL PATTERNS — services customers bought elsewhere or asked about
   after a job ("do you also do X?").
3. FRICTION — complaints that repeat (scheduling, response time, pricing
   clarity) which a service change could fix.
4. OUTPUT — ranked opportunity list: the need, evidence count, example
   quotes, suggested offer (name + rough price using profile/pricing), and
   which existing customers to pitch first.
5. STORE — write to marketing/library/opportunities-<quarter>.

Only claim patterns the evidence supports; note sample sizes. This informs
the owner's judgment — it is not a directive to launch services."""


# Registry served by get_sop / list_sops. Edit here -> all clients updated.
REGISTRY = {
    "precall_brief": {
        "description": "Prepare a pre-call brief for an upcoming sales call",
        "sop": PRECALL_BRIEF_SOP,
        "context_needed": ["profile/*", "deal + transcript docs matching the lead"],
    },
    "followup": {
        "description": "Draft post-call follow-up email, proposal outline, CRM update",
        "sop": FOLLOWUP_SOP,
        "context_needed": ["transcript", "profile/*", "deal notes"],
    },
    "score_call": {
        "description": "Score a sales call transcript against the coaching rubric",
        "sop": SCORECALL_SOP,
        "context_needed": ["transcript", "profile/icp"],
    },
    "quote": {
        "description": "Create a customer quote from a dictated job description",
        "sop": QUOTE_SOP,
        "context_needed": ["profile/pricing (rate card)", "profile/offers", "profile/tone_of_voice"],
    },
    "sow_summary": {
        "description": "Turn a meeting or site-visit transcript into post-call notes and a scope of work",
        "sop": SOW_SUMMARY_SOP,
        "context_needed": ["transcript", "profile/tone_of_voice", "deal notes"],
    },
    "inbox_triage": {
        "description": "Heartbeat routine: classify unread customer email and draft replies for review",
        "sop": INBOX_TRIAGE_SOP,
        "context_needed": ["Gmail via client connector", "profile/*", "deal notes"],
    },
    "crm_sync": {
        "description": "Daily pipeline hygiene: flag cold deals, propose status updates, freeze closed jobs",
        "sop": CRM_SYNC_SOP,
        "context_needed": ["CRM via client connector", "deal/*"],
    },
    "open_loops": {
        "description": "Report every unresolved question, promised follow-up, and stalled deal",
        "sop": OPEN_LOOPS_SOP,
        "context_needed": ["deal/*", "transcript/*", "events"],
    },
    "monthly_finance": {
        "description": "Monthly spend report from bank statements, invoices, and receipts vs budget",
        "sop": MONTHLY_FINANCE_SOP,
        "context_needed": ["PDFs client-side", "finance/profile/budget"],
    },
    "demand_mining": {
        "description": "Mine tickets, emails, and invoices for unmet customer needs and upsell opportunities",
        "sop": DEMAND_MINING_SOP,
        "context_needed": ["events history", "profile/offers"],
    },
}
