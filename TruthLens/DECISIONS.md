# TruthLens Decision Points

## DP1 – Feed Order

Decision:
Risk + Recency

Explanation:
The feed lists High Risk claims first, then Risk Flag, then Low Risk, and shows the newest claim first inside each group. A newsroom or citizen group has limited time, so the claims most likely to spread harm should be the first thing they see. Recency still matters because a fresh viral claim is more urgent than an old one. Ordering is done in the backend query, so every client sees the same order.

## DP2 – Visibility

Decision:
Unverified claims are publicly visible.

Explanation:
TruthLens is a triage tool, not a gatekeeper, so hiding claims until they are reviewed would hide exactly the backlog people need to see. Every unverified claim carries a clear, dashed "UNVERIFIED" badge and is never styled like a verdict. Risk flags are automatic triage only, and the interface says plainly that High Risk does not mean False. Only a human reviewer can move a claim to Verified True, False or Misleading.

## DP3 – Editing

Decision:
Claims cannot be edited after submission.

Explanation:
The claim text, platform, category and source link are fixed once submitted, so the record always matches what was actually circulating. The risk flags are calculated once at submission and stay attached to that exact text, which keeps the triage result honest and auditable. Editing would let someone quietly change a claim after it was flagged or reviewed. Only the reviewer's status and note can change; a corrected version should be submitted as a new claim.
