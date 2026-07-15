---
name: create-quote
description: Create a customer quote or estimate from a job description. Use whenever the user describes a job, asks to quote/price/estimate work, or dictates job details after a site visit or customer call.
---

# Create Quote

This skill is a pointer: the actual procedure lives on the Sales OS server and
is always fetched fresh. Do not improvise a quote format from memory.

## Steps

1. Call the Sales OS connector tool `create_quote`, passing the user's job
   description verbatim as `job_description` and the customer name as
   `customer` if known.
2. Follow the returned `sop` field EXACTLY. It defines how to parse the job,
   apply the rate card, format the quote, and what to do about missing
   information.
3. If the response says no rate card exists, help the user create one first:
   ask for their services and rates, then save with
   `second_brain_write(category="profile", name="pricing", content=...)`.
4. After the user approves the draft, save it to the Second Brain per the SOP
   (deal/<customer-name>, append if it exists).

## Notes

- The user may be dictating by voice from a job site — expect rough phrasing,
  confirm numbers you are unsure about.
- Never send anything; quotes are drafts for the user to review.
