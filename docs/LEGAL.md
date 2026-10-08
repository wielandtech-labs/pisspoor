# Legal documents: inventory and review notes

Prepared for review by a licensed Michigan attorney. Everything here was
drafted by an AI assistant at the owner's request and has **not** been reviewed
by a lawyer. Nothing in this file is legal advice.

## Inventory

| Document | Where | How it's accepted | Record kept |
|---|---|---|---|
| Venue Placement Agreement **v2** (`2026-10-v2`) | `venues/templates/venues/agreement_v2.html`, shown at `/venues/join` and `/venues/agreement` | Click-through at signup: typed name + role, "I'm authorized", "I agree" | `AgreementAcceptance`: full rendered text, SHA-256, version, signer, email, time, visitor hash |
| Venue Placement Agreement v1 (`2026-10-v1`) | `venues/templates/venues/agreement_v1.html` | Superseded; kept because venues may have signed it | Same |
| Advertiser Terms v1 (`2026-10-v1`) | `ads/templates/ads/advertiser_terms_v1.html`, shown at `/advertising-terms` | Click-through at ad submission (wired in the self-serve ads PR) | Version + SHA-256 + time on the `Campaign` |
| Advertising Policy | `ads/templates/ads/policy.html`, `/advertising-policy` | Incorporated by the Advertiser Terms and Venue Agreement | n/a |
| Terms of Use | `marketing/templates/marketing/terms.html`, `/terms` | Notice next to the rate / report buttons ("By submitting, you agree…") | n/a (no accounts) |
| Privacy Policy | `marketing/templates/marketing/privacy.html`, `/privacy` | Linked | n/a |

Each accepted document's text hash is pinned in a test
(`venues/tests/test_onboarding.py`, `core/tests/test_legal.py`): editing the
text without a new version fails CI. The contracting party and notice address
render from `OPERATOR_LEGAL_NAME` and `LEGAL_EMAIL` settings.

## Blockers before relying on any of these

1. **Form the entity and set `OPERATOR_LEGAL_NAME`.** Until it is set, every
   document names "Piss Poor Idea", which is not a legal person: the owner
   would be contracting personally, as a sole proprietor, with unlimited
   liability. Set it to e.g. `PPI Media LLC, d/b/a Piss Poor Idea` (and the
   assumed-name filing) before the first venue signs or advertiser pays.
   Venues that signed v1 should re-accept once the entity exists.
2. **Set `LEGAL_EMAIL`** to a monitored address. Notices under both contracts go there.
3. **Attorney review** of the open questions below.

## Review (preliminary, AI "lawyer cosplay")

### Fixed in this draft
| # | Document | Issue | Change |
|---|---|---|---|
| R1 | Venue v2 §1 | Prepaid campaigns span months; "collected for ads shown during a month" was ambiguous | Revenue allocated to months pro rata by the days each paid ad ran |
| R2 | Venue v2 §5.1 | Political ads run only at opted-in venues, yet revenue is pooled; undisclosed cross-subsidy | Disclosed: one pool, including political revenue |
| R3 | Venue v2 §9.1 | "Keeping restrooms safe and clean" created an unnecessary duty running to us | Removed |
| R4 | Venue v2 §4 | Tied-house risk if the Ad Policy ever allows alcohol: advertiser money reaching licensed bars | Covenant: no alcohol ads at liquor-licensed venues unless the law allows, regardless of policy |
| R5 | Venue v2 §15 | Liability cap would have limited our fraud clawback to $100 | Clawback/offset under §6 excluded from the cap |
| R6 | Venue v2 §16.3 | Board-link confidentiality and guest-data limits didn't survive termination; "changes" clause oddly did | Survival list corrected (adds 9.3, 10; drops 17) |
| R7 | Venue v2 §19 | Silent on a bar being sold | Agreement ends on change of operator unless the new operator accepts |
| R8 | Advertiser §1.3 | Contract formation unclear: what makes an approved ad binding | Formed on payment; invoices governed by the Terms |
| R9 | Advertiser §7 | Advertiser indemnifies venues, but venues aren't parties, so they couldn't enforce it | Venues named intended third-party beneficiaries |
| R10 | Advertiser §5 | No position on chargebacks for delivered campaigns | Pause + recovery of amount and dispute fees |
| R11 | Terms of Use | Footer-only notice is weak "browsewrap" | Notice moved next to both submit buttons ("By submitting, you agree…") |

### Open questions for counsel
1. **Uncapped indemnities.** Both indemnities in the Venue Agreement sit outside the liability cap. For a micro-business, an uncapped promise to defend a venue against claims "arising from the ads and web pages we show" is a large exposure. Cap it (e.g. at insurance limits)? Confirm the advertiser indemnity backs it up in practice.
2. **Characterizing the revenue share.** Is it compensation for space (1099-MISC rents) or services (1099-NEC)? Does it matter for sales/use tax or for any venue lease restrictions on "subletting" wall space?
3. **Political ads.** Confirm whether Michigan (MCL 169.247, and the 2023 AI-disclosure amendments) puts any duty on us as publisher beyond displaying the sponsor's disclaimer; whether federal-race ads trigger FEC disclaimer duties for us; whether the public archive raises any issue. Consider a rule for ads close to an election.
4. **Unilateral amendment** (Venue §17, Advertiser §10): 30 days' notice plus continued participation; enforceable as drafted in Michigan?
5. **E-signature records.** UETA (MCL 450.831 et seq.) and ESIGN: is the stored text + hash + typed name + visitor hash sufficient attribution, or should we also email a copy to the signer at signing (recommended either way)?
6. **Consumer-facing caps** (Terms of Use §10: $50 cap, consumer indemnity): enforceable, or worth dropping for goodwill?
7. **Venue verification** process: what evidence of authority to bind the venue is reasonable (call to the listed business number, liquor-license lookup)?
8. **Kent County venue** clause and absence of arbitration/jury waiver: confirm that's the right call for this scale.
9. **Trademark**: clearance search for "Piss Poor Idea" before printing at volume; register?
10. **Insurance**: general liability with personal and advertising injury, plus media/cyber; confirm the policies actually cover the indemnities given.

### Operational notes (not contract text)
- Handout stickers: marketing must never suggest placing stickers on property without permission. Terms of Use §4 now prohibits it expressly.
- Keep rejected-ad records with reasons (sexual-services ban and the FOSTA-SESTA carve-out from Section 230).
- Collect W-9s before first payouts; confirm current 1099 thresholds with a CPA.
