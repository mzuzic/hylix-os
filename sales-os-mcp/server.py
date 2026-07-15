"""Sales OS — thin MCP server (MVP).

Architecture: clients connect their CRM/email/etc. directly via Claude
connectors. This server only hosts the Second Brain (per-client sales
intelligence) and SOP-driven tools. It performs NO LLM calls — tools return
context + SOP instructions and the Claude client does the generation.

Auth: bearer token per client. Set SALES_OS_TOKENS as JSON:
    {"<secret-token>": "<client_id>", ...}
"""

import json
import os

from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from fastmcp.server.dependencies import get_access_token

import sops
import storage

# --- Auth ------------------------------------------------------------------

_raw = os.environ.get("SALES_OS_TOKENS")
if not _raw:
    raise SystemExit(
        "SALES_OS_TOKENS env var required, e.g. "
        '\'{"long-random-secret": "acme-plumbing"}\''
    )
TOKEN_MAP: dict[str, str] = json.loads(_raw)

auth = StaticTokenVerifier(
    tokens={
        token: {"client_id": client_id, "scopes": ["sales-os"]}
        for token, client_id in TOKEN_MAP.items()
    }
)

mcp = FastMCP("Sales OS", auth=auth)


def _client() -> str:
    """client_id of the authenticated tenant."""
    return get_access_token().client_id


def _profile_context(client_id: str) -> dict[str, str]:
    """All profile docs (ICP, offers, tone_of_voice, ...) as a dict."""
    out = {}
    for meta in storage.list_docs(client_id, "profile"):
        doc = storage.read_doc(client_id, "profile", meta["name"])
        if doc:
            out[meta["name"]] = doc["content"]
    return out


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
    """Create or update a Second Brain document. Categories: profile, deal,
    transcript, other. Use append=True to add to an existing doc (e.g. deal notes).
    Conventions: profile/icp, profile/offers, profile/tone_of_voice,
    deal/<company-name>, transcript/<company-name>-<date>."""
    return storage.write_doc(_client(), category, name, content, append)


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


if __name__ == "__main__":
    storage.init_db()
    mcp.run(
        transport="http",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )
