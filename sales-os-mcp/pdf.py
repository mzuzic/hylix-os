"""Deterministic PDF rendering for quotes.

The server stays thin: Claude produces the structured quote (line items, scope,
terms); this module only *renders* a fixed, branded template to PDF. No LLM
calls, no layout decisions left to chance — every quote looks identical and
on-brand. Money math (line amounts, subtotal, tax, total) is computed here, not
trusted from the model.
"""

import datetime as _dt

from jinja2 import Environment, BaseLoader, select_autoescape
from weasyprint import HTML

_env = Environment(loader=BaseLoader(), autoescape=select_autoescape(["html", "xml"]))

# Per-client branding lives in the Second Brain as profile/branding (JSON).
# Anything missing falls back to these defaults.
DEFAULT_BRANDING = {
    "business_name": "Your Business",
    "brand_color": "#1f2d3d",
    "logo_url": "",       # optional; WeasyPrint fetches it at render time
    "address": "",
    "email": "",
    "phone": "",
    "tax_id": "",
    "currency": "$",
    "footer": "",
}

_TEMPLATE = _env.from_string(r"""<!doctype html>
<html><head><meta charset="utf-8"><style>
  @page {
    size: A4;
    margin: 22mm 18mm 24mm 18mm;
    @bottom-center {
      content: "{{ business_name }}{% if tax_id %}  ·  {{ tax_id }}{% endif %}  ·  page " counter(page) " of " counter(pages);
      font: 8pt "DejaVu Sans", sans-serif; color: #9aa5b1;
    }
  }
  * { box-sizing: border-box; }
  body { font-family: "DejaVu Sans", sans-serif; color: #24303f; font-size: 10.5pt; line-height: 1.5; margin: 0; }
  .band { background: {{ brand_color }}; height: 8px; margin: -22mm -18mm 18px -18mm; }
  header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 26px; }
  .biz-name { font-size: 20pt; font-weight: 700; color: {{ brand_color }}; letter-spacing: .2px; }
  .biz-meta { font-size: 8.5pt; color: #627084; margin-top: 4px; white-space: pre-line; }
  .logo { max-height: 64px; max-width: 200px; }
  .title-row { display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 2px solid {{ brand_color }}; padding-bottom: 8px; margin-bottom: 18px; }
  h1 { font-size: 24pt; margin: 0; color: {{ brand_color }}; letter-spacing: 1px; }
  .meta { text-align: right; font-size: 9pt; color: #52616b; }
  .meta b { color: #24303f; }
  .billto { margin-bottom: 16px; }
  .label { font-size: 7.5pt; text-transform: uppercase; letter-spacing: .8px; color: #90a0b0; margin-bottom: 2px; }
  .customer { font-size: 12pt; font-weight: 600; }
  .scope { background: #f6f8fa; border-left: 3px solid {{ brand_color }}; padding: 10px 14px; border-radius: 3px; margin-bottom: 20px; font-size: 10pt; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 6px; }
  thead th { background: {{ brand_color }}; color: #fff; font-size: 8.5pt; text-transform: uppercase; letter-spacing: .5px; padding: 8px 10px; text-align: left; }
  thead th.num { text-align: right; }
  tbody td { padding: 9px 10px; border-bottom: 1px solid #e6eaf0; vertical-align: top; }
  tbody tr:nth-child(even) td { background: #fafbfc; }
  td.num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
  .totals { width: 46%; margin-left: auto; margin-top: 10px; }
  .totals td { padding: 6px 10px; }
  .totals .num { text-align: right; font-variant-numeric: tabular-nums; }
  .totals .grand td { border-top: 2px solid {{ brand_color }}; font-size: 13pt; font-weight: 700; color: {{ brand_color }}; padding-top: 10px; }
  .notes { margin-top: 26px; font-size: 9pt; color: #52616b; white-space: pre-line; }
  .notes .label { margin-bottom: 4px; }
  .valid { display: inline-block; margin-top: 4px; background: {{ brand_color }}18; color: {{ brand_color }}; font-size: 8.5pt; font-weight: 600; padding: 3px 9px; border-radius: 10px; }
</style></head>
<body>
  <div class="band"></div>
  <header>
    <div>
      <div class="biz-name">{{ business_name }}</div>
      {% if address or email or phone %}<div class="biz-meta">{{ address }}{% if email %}
{{ email }}{% endif %}{% if phone %}   {{ phone }}{% endif %}</div>{% endif %}
    </div>
    {% if logo_url %}<img class="logo" src="{{ logo_url }}">{% endif %}
  </header>

  <div class="title-row">
    <h1>QUOTE</h1>
    <div class="meta">
      <div><b>{{ quote_number }}</b></div>
      <div>Date: {{ date }}</div>
      <div>Valid until: {{ valid_until }}</div>
    </div>
  </div>

  <div class="billto">
    <div class="label">Prepared for</div>
    <div class="customer">{{ customer }}</div>
  </div>

  {% if scope_summary %}<div class="scope">{{ scope_summary }}</div>{% endif %}

  <table>
    <thead><tr>
      <th>Description</th>
      <th class="num">Qty</th>
      <th class="num">Unit price</th>
      <th class="num">Amount</th>
    </tr></thead>
    <tbody>
      {% for it in items %}<tr>
        <td>{{ it.description }}</td>
        <td class="num">{{ it.qty }}{% if it.unit %} {{ it.unit }}{% endif %}</td>
        <td class="num">{{ it.unit_price_fmt }}</td>
        <td class="num">{{ it.amount_fmt }}</td>
      </tr>{% endfor %}
    </tbody>
  </table>

  <table class="totals">
    <tr><td>Subtotal</td><td class="num">{{ subtotal_fmt }}</td></tr>
    {% if tax_pct %}<tr><td>Tax ({{ tax_pct }}%)</td><td class="num">{{ tax_fmt }}</td></tr>{% endif %}
    <tr class="grand"><td>Total</td><td class="num">{{ total_fmt }}</td></tr>
  </table>
  <div style="text-align:right"><span class="valid">Valid until {{ valid_until }}</span></div>

  {% if notes or footer %}<div class="notes">
    <div class="label">Notes &amp; terms</div>{{ notes }}{% if notes and footer %}

{% endif %}{{ footer }}
  </div>{% endif %}
</body></html>""")


def render_quote(
    *,
    customer: str,
    line_items: list[dict],
    scope_summary: str = "",
    notes: str = "",
    tax_rate: float = 0.0,
    valid_days: int = 14,
    branding: dict | None = None,
    currency: str | None = None,
    quote_number: str | None = None,
) -> bytes:
    """Render a branded quote PDF and return the bytes. Computes all money."""
    b = {**DEFAULT_BRANDING, **(branding or {})}
    cur = currency or b["currency"] or "$"

    def money(x: float) -> str:
        return f"-{cur}{abs(x):,.2f}" if x < 0 else f"{cur}{x:,.2f}"

    items = []
    subtotal = 0.0
    for li in line_items or []:
        qty = float(li.get("quantity", 1) or 0)
        price = float(li.get("unit_price", 0) or 0)
        amount = qty * price
        subtotal += amount
        # trim trailing .0 on whole quantities for a cleaner look
        qty_str = f"{qty:g}"
        items.append({
            "description": li.get("description", ""),
            "qty": qty_str,
            "unit": li.get("unit", "") or "",
            "unit_price_fmt": money(price),
            "amount_fmt": money(amount),
        })

    # Accept either a fraction (0.2) or a percentage (20) for tax_rate.
    rate = float(tax_rate or 0)
    if rate > 1:
        rate = rate / 100
    tax = subtotal * rate
    total = subtotal + tax
    today = _dt.date.today()
    valid_until = today + _dt.timedelta(days=int(valid_days or 14))
    number = quote_number or f"Q-{today:%Y%m%d}"

    html = _TEMPLATE.render(
        business_name=b["business_name"], brand_color=b["brand_color"],
        logo_url=b["logo_url"], address=b["address"], email=b["email"],
        phone=b["phone"], tax_id=b["tax_id"], footer=b["footer"],
        customer=customer or "—", scope_summary=scope_summary, notes=notes,
        quote_number=number, date=today.strftime("%d %b %Y"),
        valid_until=valid_until.strftime("%d %b %Y"),
        items=items, subtotal_fmt=money(subtotal),
        tax_pct=(f"{rate * 100:g}" if rate else ""), tax_fmt=money(tax),
        total_fmt=money(total),
    )
    return HTML(string=html).write_pdf()


# --- Audit report -------------------------------------------------------------

_IMPACT_COLORS = {"high": "#b3261e", "med": "#9a6b00", "low": "#5f6b76"}

_AUDIT_TEMPLATE = _env.from_string(r"""<!doctype html>
<html><head><meta charset="utf-8"><style>
  @page {
    size: A4;
    margin: 22mm 18mm 24mm 18mm;
    @bottom-center {
      content: "{{ agency_name }}{% if tax_id %}  ·  {{ tax_id }}{% endif %}  ·  page " counter(page) " of " counter(pages);
      font: 8pt "DejaVu Sans", sans-serif; color: #9aa5b1;
    }
  }
  * { box-sizing: border-box; }
  body { font-family: "DejaVu Sans", sans-serif; color: #24303f; font-size: 10pt; line-height: 1.5; margin: 0; }
  .band { background: {{ brand_color }}; height: 8px; margin: -22mm -18mm 18px -18mm; }
  header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 22px; }
  .agency { font-size: 18pt; font-weight: 700; color: {{ brand_color }}; }
  .agency-meta { font-size: 8.5pt; color: #627084; margin-top: 3px; }
  .logo { max-height: 56px; max-width: 180px; }
  .title-row { border-bottom: 2px solid {{ brand_color }}; padding-bottom: 8px; margin-bottom: 16px; }
  h1 { font-size: 20pt; margin: 0; color: {{ brand_color }}; letter-spacing: .5px; }
  .meta { font-size: 9pt; color: #52616b; margin-top: 3px; }
  .meta b { color: #24303f; }
  .summary { background: #f6f8fa; border-left: 3px solid {{ brand_color }}; padding: 10px 14px; border-radius: 3px; margin-bottom: 16px; }
  .counts { display: flex; gap: 10px; margin: 14px 0 20px 0; }
  .count { flex: 1; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px 12px; text-align: center; }
  .count .n { font-size: 18pt; font-weight: 700; }
  .count .lbl { font-size: 7.5pt; text-transform: uppercase; letter-spacing: .8px; color: #90a0b0; }
  h2 { font-size: 11pt; text-transform: uppercase; letter-spacing: 1px; color: {{ brand_color }}; margin: 22px 0 10px 0; }
  .finding { border: 1px solid #e2e8f0; border-radius: 8px; padding: 11px 14px; margin-bottom: 10px; page-break-inside: avoid; }
  .finding.top { border-left: 4px solid {{ brand_color }}; }
  .f-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
  .f-title { font-weight: 700; font-size: 10.5pt; }
  .chips { white-space: nowrap; }
  .chip { display: inline-block; font-size: 7.5pt; font-weight: 700; text-transform: uppercase; letter-spacing: .6px;
          padding: 2px 8px; border-radius: 9px; margin-left: 4px; color: #fff; }
  .chip.effort { background: none; color: #52616b; border: 1px solid #cbd5e1; }
  .f-fix { margin-top: 5px; font-size: 9.5pt; }
  .f-fix b { color: {{ brand_color }}; }
  .f-detail { margin-top: 3px; font-size: 9pt; color: #52616b; }
  .nc { font-size: 9pt; color: #52616b; margin: 0 0 4px 0; }
  .disclaimer { margin-top: 24px; font-size: 8pt; color: #90a0b0; border-top: 1px solid #e2e8f0; padding-top: 8px; }
</style></head>
<body>
  <div class="band"></div>
  <header>
    <div>
      <div class="agency">{{ agency_name }}</div>
      {% if agency_contact %}<div class="agency-meta">{{ agency_contact }}</div>{% endif %}
    </div>
    {% if logo_url %}<img class="logo" src="{{ logo_url }}">{% endif %}
  </header>

  <div class="title-row">
    <h1>LOCAL SEO AUDIT</h1>
    <div class="meta"><b>{{ business_name }}</b>{% if website %} · {{ website }}{% endif %} · {{ date }}</div>
  </div>

  {% if summary %}<div class="summary">{{ summary }}</div>{% endif %}

  <div class="counts">
    <div class="count"><div class="n" style="color:#b3261e">{{ n_high }}</div><div class="lbl">High impact</div></div>
    <div class="count"><div class="n" style="color:#9a6b00">{{ n_med }}</div><div class="lbl">Medium impact</div></div>
    <div class="count"><div class="n" style="color:#5f6b76">{{ n_low }}</div><div class="lbl">Low impact</div></div>
    <div class="count"><div class="n">{{ n_quick }}</div><div class="lbl">Quick wins</div></div>
  </div>

  <h2>Top priorities</h2>
  {% for f in top %}
  <div class="finding top">
    <div class="f-head">
      <div class="f-title">{{ loop.index }}. {{ f.title }}</div>
      <div class="chips"><span class="chip" style="background:{{ f.color }}">{{ f.impact }}</span><span class="chip effort">{{ f.effort }}</span></div>
    </div>
    <div class="f-fix"><b>Fix:</b> {{ f.fix }}</div>
    {% if f.detail %}<div class="f-detail">{{ f.detail }}</div>{% endif %}
  </div>
  {% endfor %}

  {% if rest %}
  <h2>Further findings</h2>
  {% for f in rest %}
  <div class="finding">
    <div class="f-head">
      <div class="f-title">{{ f.title }}</div>
      <div class="chips"><span class="chip" style="background:{{ f.color }}">{{ f.impact }}</span><span class="chip effort">{{ f.effort }}</span></div>
    </div>
    <div class="f-fix"><b>Fix:</b> {{ f.fix }}</div>
    {% if f.detail %}<div class="f-detail">{{ f.detail }}</div>{% endif %}
  </div>
  {% endfor %}
  {% endif %}

  {% if not_checked %}
  <h2>Not checked in this pass</h2>
  {% for item in not_checked %}<p class="nc">— {{ item }}</p>{% endfor %}
  {% endif %}

  <div class="disclaimer">All recommendations comply with Google Business Profile policies — no review gating,
  incentivized reviews, or address manipulation. Findings based on publicly visible pages at audit time.
  Marketing guidance, not a guarantee of rankings.{% if footer %} {{ footer }}{% endif %}</div>
</body></html>""")


def render_audit(
    *,
    business_name: str,
    website: str = "",
    summary: str = "",
    findings: list[dict] | None = None,
    not_checked: list[str] | None = None,
    branding: dict | None = None,
    audit_date: str | None = None,
) -> bytes:
    """Render a branded local-SEO audit PDF. findings: [{title, impact, effort, fix, detail}]."""
    b = {**DEFAULT_BRANDING, **(branding or {})}
    contact = "  ·  ".join(x for x in (b["email"], b["phone"], b["address"]) if x)

    prepared = []
    for f in findings or []:
        impact = str(f.get("impact", "med")).lower()
        impact = impact if impact in _IMPACT_COLORS else "med"
        prepared.append({
            "title": f.get("title", ""),
            "impact": impact,
            "color": _IMPACT_COLORS[impact],
            "effort": str(f.get("effort", "")) or "n/a",
            "fix": f.get("fix", ""),
            "detail": f.get("detail", ""),
        })
    # highs first, then med, then low — stable within groups
    order = {"high": 0, "med": 1, "low": 2}
    prepared.sort(key=lambda f: order[f["impact"]])

    html = _AUDIT_TEMPLATE.render(
        agency_name=b["business_name"], brand_color=b["brand_color"],
        logo_url=b["logo_url"], agency_contact=contact, tax_id=b["tax_id"],
        footer=b["footer"], business_name=business_name or "—", website=website,
        date=audit_date or _dt.date.today().strftime("%d %b %Y"),
        summary=summary,
        n_high=sum(1 for f in prepared if f["impact"] == "high"),
        n_med=sum(1 for f in prepared if f["impact"] == "med"),
        n_low=sum(1 for f in prepared if f["impact"] == "low"),
        n_quick=sum(1 for f in prepared if "quick" in f["effort"].lower()),
        top=prepared[:3], rest=prepared[3:], not_checked=not_checked or [],
    )
    return HTML(string=html).write_pdf()
