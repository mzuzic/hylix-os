"""End-to-end smoke test: starts nothing itself — expects server on :8000."""

import asyncio
import json

from fastmcp import Client


async def main():
    ok = 0

    # 1. Valid token, full flow
    async with Client("http://127.0.0.1:8000/mcp", auth="test-token-acme") as c:
        r = await c.call_tool("whoami", {})
        assert r.data["client_id"] == "acme-plumbing", r.data
        ok += 1

        await c.call_tool("second_brain_write", {
            "category": "profile", "name": "icp",
            "content": "Homeowners 30-65 in Springfield metro needing plumbing repair; avg job $450."})
        await c.call_tool("second_brain_write", {
            "category": "profile", "name": "tone_of_voice",
            "content": "Friendly, plain-spoken, no jargon. Sign off: 'Talk soon, Mike'."})
        await c.call_tool("second_brain_write", {
            "category": "deal", "name": "henderson-remodel",
            "content": "2026-07-10: Sarah Henderson, kitchen remodel, budget ~$12k, worried about timeline."})
        ok += 1

        r = await c.call_tool("second_brain_list", {})
        assert len(r.data) >= 3, r.data
        ok += 1

        r = await c.call_tool("second_brain_write", {
            "category": "deal", "name": "henderson-remodel",
            "content": "2026-07-14: sent quote, awaiting reply.", "append": True})
        r = await c.call_tool("second_brain_read", {"category": "deal", "name": "henderson-remodel"})
        assert "2026-07-10" in r.data["content"] and "2026-07-14" in r.data["content"]
        ok += 1

        r = await c.call_tool("get_precall_brief", {"lead_name": "Sarah Henderson", "company": "henderson"})
        assert "FIT SCORE" in r.data["sop"]
        assert r.data["profile"].get("icp") and len(r.data["matching_docs"]) >= 1
        ok += 1

        r = await c.call_tool("draft_followup", {"deal_name": "henderson"})
        assert r.data["deal_notes"], r.data
        ok += 1

        r = await c.call_tool("score_call", {"transcript": "Rep: hi. Prospect: hello...", "rep_name": "Mike"})
        assert "DISCOVERY" in r.data["sop"] and r.data["icp"]
        ok += 1

        # Quote flow
        r = await c.call_tool("list_sops", {})
        assert {s["name"] for s in r.data} >= {"quote", "precall_brief", "followup", "score_call"}
        r = await c.call_tool("get_sop", {"name": "quote"})
        assert "PRICE IT" in r.data["sop"]
        ok += 1

        r = await c.call_tool("create_quote", {"job_description": "kitchen repaint 40 sqm, plaster repair", "customer": "henderson"})
        assert "NO RATE CARD" in r.data["rate_card"]  # not seeded yet
        await c.call_tool("second_brain_write", {
            "category": "profile", "name": "pricing",
            "content": "Interior painting: $18/sqm. Plaster repair: $60/hr. Min charge $250. Call-out: $0."})
        r = await c.call_tool("create_quote", {"job_description": "kitchen repaint 40 sqm, plaster repair", "customer": "henderson"})
        assert "$18/sqm" in r.data["rate_card"] and r.data["existing_deal_notes"]
        assert r.data["tone_of_voice"]
        ok += 1

    # 2. Tenant isolation: second client sees nothing
    async with Client("http://127.0.0.1:8000/mcp", auth="test-token-blue") as c:
        r = await c.call_tool("second_brain_list", {})
        assert r.data == [], r.data
        ok += 1

    # 3. Bad token rejected
    try:
        async with Client("http://127.0.0.1:8000/mcp", auth="wrong-token") as c:
            await c.call_tool("whoami", {})
        raise SystemExit("FAIL: bad token was accepted")
    except Exception as e:
        assert "401" in str(e) or "Unauthorized" in str(e) or "auth" in str(e).lower(), e
        ok += 1

    print(f"PASS: {ok}/11 checks")


asyncio.run(main())
