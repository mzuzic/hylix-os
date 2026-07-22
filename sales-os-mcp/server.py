"""Sales OS — thin MCP server (MVP).

Architecture: clients connect their CRM/email/etc. directly via Claude
connectors. This server only hosts the Second Brain (per-client sales
intelligence) and SOP-driven tools. It performs NO LLM calls — tools return
context + SOP instructions and the Claude client does the generation.

Auth: bearer token per client. Set SALES_OS_TOKENS as JSON:
    {"<secret-token>": "<client_id>", ...}
"""

import datetime as _dt
import json
import os
import re
import secrets

from fastmcp import FastMCP
from fastmcp.server.auth.auth import MultiAuth
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from fastmcp.server.dependencies import get_access_token
from pydantic import BaseModel, Field, model_validator
from starlette.responses import FileResponse, Response

import oauth as oauth_mod
import pdf as pdfgen
import sops
import storage

# Where persistent data lives (same volume as the SQLite DB).
_DATA_DIR = os.path.dirname(os.environ.get("SALES_OS_DB", "/data/sales_os.db")) or "/data"

# --- Auth ------------------------------------------------------------------

_raw = os.environ.get("SALES_OS_TOKENS")
if not _raw:
    raise SystemExit(
        "SALES_OS_TOKENS env var required, e.g. "
        '\'{"long-random-secret": "acme-plumbing"}\''
    )
TOKEN_MAP: dict[str, str] = json.loads(_raw)

# Public base URL where OAuth endpoints (/authorize, /token, /.well-known/*) are
# served — must match the connector URL's origin.
PUBLIC_URL = os.environ.get("SALES_OS_PUBLIC_URL", "https://salesos.hylix.ai")

# OAuth persistence (signing secret, DCR clients) needs the DB before we build auth.
storage.init_db()

# Two ways in, composed with MultiAuth:
#  - OAuth 2.1 (interactive clients like claude.ai) — see oauth.py
#  - raw per-tenant bearer tokens (Claude Desktop, API, smoke test)
_static = StaticTokenVerifier(
    tokens={
        token: {"client_id": client_id, "scopes": ["sales-os"]}
        for token, client_id in TOKEN_MAP.items()
    }
)
_oauth = oauth_mod.SalesOsOAuthProvider(base_url=PUBLIC_URL, tokens=TOKEN_MAP)
auth = MultiAuth(server=_oauth, verifiers=[_static])

# Sent to the client on connect (MCP `instructions`). This carries the behaviour
# that used to live in the client-side stub skills, so clients only need to
# connect the connector — no per-client skill upload.
INSTRUCTIONS = (
    "This connector is the client's Sales OS — their per-client sales intelligence "
    "(the Second Brain) plus standard operating procedures (SOPs). Behave as follows "
    "without being asked:\n"
    "- When the user describes or dictates a job, or asks to quote / price / estimate "
    "work, call `create_quote` with their words verbatim and follow the returned "
    "`sop` field EXACTLY. Never improvise a quote or pricing from memory. Once the "
    "user approves the drafted quote, call `render_quote_pdf` and give the user the "
    "returned `download_url` — a link to the polished, branded PDF they can open or "
    "send straight to the customer.\n"
    "- Before a sales call, use `get_precall_brief`. After a call, use "
    "`draft_followup` and/or `score_call`.\n"
    "- Whenever the user shares a document (invoice, receipt, bank statement, "
    "supplier quote, contract), extract its data immediately: call "
    "`get_sop('doc_intake')` and follow it, filing the extracted data into the "
    "Second Brain. Never store the raw file there. More procedures: `list_sops`.\n"
    "- When the user asks to audit a website or a business's Google presence, call "
    "`get_sop` with name 'site_audit' and follow it exactly, finishing with "
    "`render_audit_pdf`. More workflows are listed by `list_sops` — check there "
    "before improvising any multi-step business task.\n"
    "- Always pull pricing, tone of voice, ICP, offers, and deal history via the "
    "`second_brain_*` tools rather than inventing them, and follow each tool's "
    "returned `sop` exactly.\n"
    "- Everything you produce is a draft for the user to review. Never send anything."
)

mcp = FastMCP("Sales OS", auth=auth, instructions=INSTRUCTIONS)


def _client() -> str:
    """client_id of the authenticated tenant.

    OAuth tokens carry the tenant in `subject`; raw static tokens carry it in
    `client_id`. Prefer subject, fall back to client_id.
    """
    tok = get_access_token()
    return getattr(tok, "subject", None) or tok.client_id


def _profile_context(client_id: str) -> dict[str, str]:
    """All profile docs (ICP, offers, tone_of_voice, ...) as a dict."""
    out = {}
    for meta in storage.list_docs(client_id, "profile"):
        doc = storage.read_doc(client_id, "profile", meta["name"])
        if doc:
            out[meta["name"]] = doc["content"]
    return out


def _branding(client_id: str) -> dict:
    """Client branding for PDFs, from the profile/branding doc (JSON). {} if absent."""
    doc = storage.read_doc(client_id, "profile", "branding")
    if not doc:
        return {}
    try:
        data = json.loads(doc["content"])
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


# --- Second Brain tools ------------------------------------------------------


@mcp.tool
def whoami() -> dict:
    """Confirm connectivity and show which client workspace this token maps to."""
    return {"client_id": _client(), "server": "Sales OS MVP"}


@mcp.tool
def second_brain_list(category: str | None = None) -> list[dict]:
    """List documents in the Second Brain. Categories: profile (ICP, offers,
    tone_of_voice), deal (per-deal notes), transcript (call transcripts), other."""
    return storage.list_docs(_client(), category)


@mcp.tool
def second_brain_read(category: str, name: str) -> dict:
    """Read one Second Brain document by category and name."""
    doc = storage.read_doc(_client(), category, name)
    if not doc:
        return {"error": f"No doc '{name}' in category '{category}'. Use second_brain_list."}
    return doc


@mcp.tool
def second_brain_write(category: str, name: str, content: str, append: bool = False) -> dict:
    """Create or update a Second Brain document. Common categories: profile,
    deal, transcript, finance, marketing, events, other — any short lowercase
    slug is accepted. Use append=True to add to an existing doc (e.g. deal notes).
    Conventions: profile/icp, profile/offers, profile/tone_of_voice,
    deal/<company-name>, transcript/<company-name>-<date>,
    finance/monthly-<year>-<month>."""
    return storage.write_doc(_client(), category, name, content, append)


@mcp.tool
def second_brain_search(query: str, category: str = "") -> list[dict]:
    """Case-insensitive search across the Second Brain by document name or
    content. Returns up to 10 matches (newest first) with a snippet around the
    match — use second_brain_read to fetch a full document. Optionally restrict
    to one category (profile, deal, transcript, finance, ...)."""
    results = storage.search_docs(_client(), query, category=category or None)
    out = []
    for r in results:
        content = r.get("content") or ""
        idx = content.lower().find(query.lower())
        if idx >= 0:
            start = max(0, idx - 120)
            end = min(len(content), idx + len(query) + 120)
            snippet = ("…" if start else "") + content[start:end] + ("…" if end < len(content) else "")
        else:  # matched on the name
            snippet = content[:160] + ("…" if len(content) > 160 else "")
        out.append({
            "category": r["category"], "name": r["name"],
            "updated_at": r["updated_at"], "snippet": snippet,
        })
    return out


@mcp.tool
def second_brain_delete(category: str, name: str) -> dict:
    """Delete a Second Brain document."""
    ok = storage.delete_doc(_client(), category, name)
    return {"deleted": ok}


# --- SOP tools ---------------------------------------------------------------


@mcp.tool
def list_sops() -> list[dict]:
    """List available SOPs (standard operating procedures) with descriptions
    and the context each one needs."""
    return [
        {"name": k, "description": v["description"], "context_needed": v["context_needed"]}
        for k, v in sops.REGISTRY.items()
    ]


@mcp.tool
def get_sop(name: str) -> dict:
    """Fetch the latest version of an SOP by name (see list_sops). Follow the
    returned SOP exactly, pulling any needed context via second_brain tools."""
    entry = sops.REGISTRY.get(name)
    if not entry:
        return {"error": f"No SOP '{name}'.", "available": sorted(sops.REGISTRY)}
    return {"name": name, **entry}


@mcp.tool
def create_quote(job_description: str, customer: str = "") -> dict:
    """Create a customer quote from a (possibly dictated) job description.
    Returns the quote SOP plus rate card, offers, and tone; follow the SOP to
    produce the quote draft, then save it with second_brain_write."""
    cid = _client()
    profile = _profile_context(cid)
    return {
        "sop": sops.QUOTE_SOP,
        "job_description": job_description,
        "customer": customer,
        "rate_card": profile.get("pricing", "NO RATE CARD — ask the user to add profile/pricing first."),
        "offers": profile.get("offers", ""),
        "tone_of_voice": profile.get("tone_of_voice", ""),
        "existing_deal_notes": storage.search_docs(cid, customer, category="deal") if customer else [],
    }


def _to_number(value) -> float:
    """Parse a possibly-messy numeric value: 4500, '4500', '$4,500.00', '40 sqm',
    '6 months', '-$540', '($540)' -> float. Returns 0.0 if no number is present.
    Preserves a negative sign even when a currency symbol sits between it and the
    digits (e.g. '-$540' -> -540), and treats accounting parentheses as negative."""
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return 0.0
    s = str(value)
    m = re.search(r"\d[\d,]*\.?\d*", s)
    if not m:
        return 0.0
    magnitude = float(m.group(0).replace(",", ""))
    prefix = s[: m.start()]
    negative = "-" in prefix or "(" in prefix
    return -magnitude if negative else magnitude


class QuoteLineItem(BaseModel):
    """One priced line on a quote. The server computes the line amount."""
    description: str = Field(default="", description="What the line covers, e.g. 'Interior painting'")
    quantity: float = Field(default=1, description="Amount of the unit, e.g. 40")
    unit: str = Field(default="", description="Unit label, e.g. 'sqm', 'hr', 'each'")
    unit_price: float = Field(default=0, description="Price per unit in the client's currency")

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data):
        """Be forgiving about how the model phrases numbers/field names, so a
        quote never fails on '$3,200.00', '6 months', or a 'rate'/'price' alias."""
        if not isinstance(data, dict):
            return data
        d = dict(data)
        for alias in ("rate", "price", "unit_cost", "amount_per_unit"):
            if d.get("unit_price") in (None, "") and alias in d:
                d["unit_price"] = d[alias]
        for alias in ("qty", "count"):
            if d.get("quantity") in (None, "") and alias in d:
                d["quantity"] = d[alias]
        for alias in ("desc", "item", "name", "title"):
            if not d.get("description") and alias in d:
                d["description"] = d[alias]
        # If quantity carries its unit as text ('40 sqm'), lift the unit out.
        q = d.get("quantity")
        if isinstance(q, str) and not d.get("unit"):
            um = re.search(r"[a-zA-Z%]+", q)
            if um:
                d["unit"] = um.group(0)
        if isinstance(d.get("quantity"), str):
            d["quantity"] = _to_number(d["quantity"])
        if isinstance(d.get("unit_price"), str):
            d["unit_price"] = _to_number(d["unit_price"])
        return d


@mcp.tool
def render_quote_pdf(
    customer: str,
    line_items: list[QuoteLineItem],
    scope_summary: str = "",
    notes: str = "",
    tax_rate: float = 0.0,
    valid_days: int = 14,
    currency: str = "",
) -> dict:
    """Render a polished, branded PDF quote and return a shareable download link.
    Call this AFTER the user has approved the drafted quote (see create_quote /
    the quote SOP). Give the user the returned `download_url` — they can open it
    or send it straight to the customer.

    Pass structured line_items (description, quantity, unit, unit_price) — the
    server computes each line amount, the subtotal, tax, and total, so do NOT
    pre-compute or round totals yourself. tax_rate is a fraction (0.2 = 20%);
    omit or 0 for none. Branding (business name, logo, colours, address, tax id,
    currency) is pulled from the client's profile/branding doc. A copy is saved
    to the deal history automatically."""
    cid = _client()
    branding = _branding(cid)
    items = [li.model_dump() for li in line_items]
    number = f"Q-{_dt.date.today():%Y%m%d}-{secrets.token_hex(2).upper()}"

    data = pdfgen.render_quote(
        customer=customer,
        line_items=items,
        scope_summary=scope_summary,
        notes=notes,
        tax_rate=tax_rate,
        valid_days=valid_days,
        branding=branding,
        currency=currency or None,
        quote_number=number,
    )

    # Save under an unguessable token and expose it at a shareable URL. (claude.ai
    # doesn't render an MCP file blob as a chat download, so we hand back a link.)
    token = secrets.token_urlsafe(24)
    url = f"{PUBLIC_URL.rstrip('/')}/q/{token}.pdf"
    try:
        qdir = os.path.join(_DATA_DIR, "quotes")
        os.makedirs(qdir, exist_ok=True)
        with open(os.path.join(qdir, f"{token}.pdf"), "wb") as fh:
            fh.write(data)
    except OSError:
        return {"error": "Could not save the quote PDF. Please try again."}

    if customer:
        storage.write_doc(
            cid, "deal", customer,
            f"{_dt.date.today():%Y-%m-%d}: quote {number} generated "
            f"({len(items)} line item(s)) — {url}",
            append=True,
        )

    return {
        "quote_number": number,
        "customer": customer,
        "download_url": url,
        "message": (
            f"Quote {number} is ready. Share this link with the customer "
            f"(it opens the branded PDF): {url}"
        ),
    }


class AuditFinding(BaseModel):
    """One audit finding. Impact/effort are normalized server-side — send what you have."""
    title: str = Field(description="Short name of the issue, e.g. 'No dedicated service pages'")
    impact: str = Field(default="med", description="high | med | low")
    effort: str = Field(default="", description="quick | moderate | project")
    fix: str = Field(default="", description="The concrete recommended fix, one or two sentences")
    detail: str = Field(default="", description="Optional supporting detail/evidence")

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data):
        if not isinstance(data, dict):
            return data
        d = dict(data)
        imp = str(d.get("impact", "med")).strip().lower()
        d["impact"] = {"medium": "med", "mid": "med", "critical": "high", "severe": "high",
                       "minor": "low"}.get(imp, imp)
        if d["impact"] not in ("high", "med", "low"):
            d["impact"] = "med"
        d["effort"] = str(d.get("effort", "")).strip().lower()
        return d


@mcp.tool
def render_audit_pdf(
    business_name: str,
    website: str = "",
    summary: str = "",
    findings: list[AuditFinding] | None = None,
    not_checked: list[str] | None = None,
) -> dict:
    """Render the site_audit results as a branded PDF report and return a
    shareable download link — the client-facing deliverable/leave-behind.
    Call AFTER completing the site_audit SOP. Pass the findings structured
    (title, impact high/med/low, effort quick/moderate/project, fix, detail);
    the server sorts by impact and takes the first three as Top Priorities.
    Agency branding comes from profile/branding. The link is also appended to
    marketing/site-audit-<domain> automatically."""
    cid = _client()
    branding = _branding(cid)
    items = [f.model_dump() for f in (findings or [])]

    data = pdfgen.render_audit(
        business_name=business_name,
        website=website,
        summary=summary,
        findings=items,
        not_checked=not_checked or [],
        branding=branding,
    )

    token = secrets.token_urlsafe(24)
    url = f"{PUBLIC_URL.rstrip('/')}/q/{token}.pdf"
    try:
        qdir = os.path.join(_DATA_DIR, "quotes")
        os.makedirs(qdir, exist_ok=True)
        with open(os.path.join(qdir, f"{token}.pdf"), "wb") as fh:
            fh.write(data)
    except OSError:
        return {"error": "Could not save the audit PDF. Please try again."}

    domain = (website.replace("https://", "").replace("http://", "").strip("/")
              or business_name.strip().replace(" ", "-").lower())
    storage.write_doc(
        cid, "marketing", f"site-audit-{domain}",
        f"{_dt.date.today():%Y-%m-%d}: branded audit PDF generated — {url}",
        append=True,
    )

    return {
        "business": business_name,
        "download_url": url,
        "message": f"Audit report for {business_name} is ready — share this link: {url}",
    }


@mcp.tool
def get_precall_brief(lead_name: str, company: str = "") -> dict:
    """Assemble everything needed for a pre-call brief on a lead/company.
    Returns SOP instructions plus ICP, offers, tone, and matching deal notes
    and transcripts. Follow the SOP to produce the brief."""
    cid = _client()
    matches = storage.search_docs(cid, company or lead_name)
    return {
        "sop": sops.PRECALL_BRIEF_SOP,
        "lead": {"name": lead_name, "company": company},
        "profile": _profile_context(cid),
        "matching_docs": matches,
        "note": "If matching_docs is empty, this is a first-touch lead; say so in the HISTORY section.",
    }


@mcp.tool
def draft_followup(deal_name: str, transcript: str = "") -> dict:
    """Assemble context for a post-call follow-up (email + proposal outline +
    CRM update). Pass the transcript if you have it; otherwise the latest
    stored transcript matching deal_name is used. Follow the returned SOP."""
    cid = _client()
    if not transcript:
        found = storage.search_docs(cid, deal_name, category="transcript")
        transcript = found[0]["content"] if found else ""
    return {
        "sop": sops.FOLLOWUP_SOP,
        "deal": deal_name,
        "transcript": transcript or "NO TRANSCRIPT FOUND — ask the user to provide one.",
        "profile": _profile_context(cid),
        "deal_notes": storage.search_docs(cid, deal_name, category="deal"),
    }


@mcp.tool
def score_call(transcript: str, rep_name: str = "") -> dict:
    """Score a sales call transcript against the coaching rubric.
    Follow the returned SOP to produce scores and coaching feedback."""
    return {
        "sop": sops.SCORECALL_SOP,
        "rep": rep_name,
        "transcript": transcript,
        "icp": _profile_context(_client()).get("icp", ""),
    }


# --- Prompts -----------------------------------------------------------------
# Surface each SOP as a connector prompt (appears in the client's "+" menu on
# connect). These replace the uploaded stub skills: same "call the tool, follow
# the SOP, never improvise" pointer behaviour, delivered by the connector itself.


@mcp.prompt(title="Create a quote")
def quote(job_description: str = "", customer: str = "") -> str:
    """Create a customer quote or estimate from a described or dictated job.
    Use whenever the user describes a job, or asks to quote / price / estimate work."""
    job = job_description or "the job the user just described (ask if it is unclear)"
    who = f" for customer '{customer}'" if customer else ""
    return (
        f"Create a quote{who}. Call the `create_quote` tool with the user's job "
        f"description verbatim ({job}) and the customer name if known, then follow the "
        f"returned `sop` field EXACTLY — never improvise pricing or quote format from "
        f"memory. If the response says no rate card exists, help the user add one via "
        f"second_brain_write(category='profile', name='pricing', ...) first. The user "
        f"may be dictating by voice — expect rough phrasing and confirm any numbers you "
        f"are unsure about. After the user approves, call `render_quote_pdf` (passing "
        f"the structured line items) and give the user the returned `download_url` for "
        f"the branded PDF. Never send anything; it's a draft for the user to send."
    )


@mcp.prompt(title="Pre-call brief")
def precall_brief(lead_name: str = "", company: str = "") -> str:
    """Assemble a pre-call brief for a lead or company before a sales call."""
    return (
        "Prepare a pre-call brief. Call `get_precall_brief` with the lead name and "
        "company, then follow the returned `sop` field EXACTLY, pulling any extra "
        "context via the second_brain tools. If no matching history is found, say so "
        "in the HISTORY section rather than inventing details."
    )


@mcp.prompt(title="Draft a follow-up")
def followup(deal_name: str = "", transcript: str = "") -> str:
    """Draft a post-call follow-up: email, proposal outline, and CRM update."""
    return (
        "Draft a post-call follow-up. Call `draft_followup` with the deal name (and "
        "the call transcript if you have one), then follow the returned `sop` field "
        "EXACTLY. Use the client's stored tone_of_voice and offers; never invent "
        "pricing. Produce a draft for the user to review — never send anything."
    )


@mcp.prompt(title="File a document")
def file_document() -> str:
    """Extract data from a shared document (invoice, receipt, statement,
    supplier quote, contract) and file it into the Second Brain wiki."""
    return (
        "The user is sharing a document to file. Call `get_sop` with name "
        "'doc_intake' and follow the returned `sop` field EXACTLY: classify the "
        "document, dedup against the wiki with second_brain_search, extract the "
        "data (transactions to the finance ledger, contract terms to the deal, "
        "supplier prices to finance/supplier-<name>), and confirm what was filed "
        "where. Never store the raw file in the Second Brain, and never invent "
        "amounts or dates — mark anything unreadable as [UNCLEAR]."
    )


@mcp.prompt(title="Site audit (local SEO)")
def site_audit(website: str = "", business_name: str = "") -> str:
    """Audit a local business's website + Google presence and produce a branded
    PDF report. Use when prospecting or onboarding a local business."""
    target = website or "the website the user provides (ask if missing)"
    return (
        f"Run a local SEO audit on {target}"
        f"{f' (business: {business_name})' if business_name else ''}. "
        "Call `get_sop` with name 'site_audit' and follow the returned SOP EXACTLY: "
        "fetch the site, check the Google Business Profile (existence, reviews, "
        "claim status), citations, competitors, and ads history where reachable. "
        "Mark anything you cannot verify as [NOT CHECKED] — never guess. Save the "
        "findings with second_brain_write, then call `render_audit_pdf` with the "
        "structured findings and give the user the download link. Recommend only "
        "Google-policy-compliant tactics."
    )


@mcp.prompt(title="Score a call")
def score_a_call(transcript: str = "", rep_name: str = "") -> str:
    """Score a sales call transcript against the coaching rubric."""
    return (
        "Score a sales call. Call `score_call` with the transcript (and rep name if "
        "known), then follow the returned `sop` field EXACTLY to produce scores and "
        "coaching feedback grounded in the client's ICP."
    )


@mcp.custom_route("/consent", methods=["GET", "POST"])
async def consent(request):
    """Login/consent page for the OAuth flow — user pastes their access key."""
    return await _oauth.handle_consent(request)


@mcp.custom_route("/q/{filename}", methods=["GET"])
async def serve_quote(request):
    """Serve a rendered quote PDF by its unguessable token (shareable link)."""
    filename = request.path_params["filename"]
    token = filename[:-4] if filename.endswith(".pdf") else filename
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", token):
        return Response("Not found", status_code=404)
    path = os.path.join(_DATA_DIR, "quotes", f"{token}.pdf")
    if not os.path.isfile(path):
        return Response("Not found", status_code=404)
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{token}.pdf"'},
    )


if __name__ == "__main__":
    storage.init_db()
    mcp.run(
        transport="http",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )
