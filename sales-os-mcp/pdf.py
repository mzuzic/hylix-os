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
        return f"{cur}{x:,.2f}"

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
