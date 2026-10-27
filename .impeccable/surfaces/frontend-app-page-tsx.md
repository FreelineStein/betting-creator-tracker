---
version: 1
slug: "frontend-app-page-tsx"
primary_target: "frontend/app/page.tsx"
related_targets: ["frontend/app/creators/[id]/page.tsx","frontend/app/submit/page.tsx","frontend/app/layout.tsx"]
---

# Surface brief: homepage (/) and the shared world

Scope: the whole public site (/, /creators/[id], /submit). Visitor mode: Persuade on /, Operate on /creators/[id] and /submit. Audience: a sports bettor arriving from X on a phone, deciding in seconds whether a creator's record is worth tailing. Action on /: find the creator (live filter) and open their record; secondary action: submit a pick. Proof: real settled and pending picks from the live API. Constraints: no invented claims, losses as plain as wins, W/L never by color alone, legal lines kept.

Chosen direction: Category standard, played straight (chosen 2026-10-27 over The Receipt Roll and Sports Data Desk after viewing live-data HTML mocks of all three). Logo pinned by the user: frontend/public/logo.png. The Agate Page (newsprint standings) was rejected and is an anti-reference.

## Direction contract

THESIS: The betting-media app shell done at full quality: each creator is one rounded card whose record reads in a glance. Refuses the dense newspaper table where every column blends together.

OWN-WORLD: Near-black ground, three panel steps, hairline borders, no shadows. The logo's lime for wins, the primary action and a Win % that clears 52.4%; the logo's orange for losses and negative ROI. Barlow Condensed uppercase for headlines, section heads and figures; Barlow for body. Lettered W/L/P chips at 7px radius, controls 10px, cards 14px.

STORY: The visitor sees the headline, types the creator's name, reads Record, Win %, ROI and last-5 chips on one card, expands it for the latest picks, and opens the full record. Box scores and On deck show the record moving.

FIRST VIEWPORT: Sticky header with the logo left and the lime "Submit a pick" button right. Headline "Every pick. Every loss. On the record." with the last clause in lime, one lede line, the find field, then Division I cards (avatar with rank badge, name and handle, Record / Win % / ROI, five form chips, expand button) beside a 320px Box scores column. Mobile stacks each card as identity, three stats, form row.

FORM: Category standard (canon card), outside the ordered list; seed key 8745f32a (assigned candidate was The Receipt Roll). Signature interaction: live find-a-creator filter plus inline card expand. Motion: 150ms color and border transitions only; nothing animates on load.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.
