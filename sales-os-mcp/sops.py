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
}
