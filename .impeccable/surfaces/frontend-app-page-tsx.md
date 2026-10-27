---
version: 1
slug: "frontend-app-page-tsx"
primary_target: "frontend/app/page.tsx"
related_targets: ["frontend/app/creators/[id]/page.tsx","frontend/app/submit/page.tsx","frontend/app/layout.tsx"]
---

# Surface brief: homepage (/) and the shared world

Scope: the whole public site (/, /creators/[id], /submit). Visitor mode: Persuade on /, Operate on /creators/[id] and /submit. Audience: a sports bettor arriving from X on a phone, deciding in seconds whether a creator's record is worth tailing. Action on /: find the creator (live filter over the standings) and open their record; secondary action: submit a pick. Proof: real settled picks and real pending picks from the live API. Constraints: no invented claims, losses as plain as wins, W/L never by color alone, legal lines kept.

Chosen direction: The Agate Page. Memorable moment: the creators are teams in a standings table you already know how to read, and yesterday's settled picks sit beside it as box scores.

## Direction contract

THESIS: The record is a standings table, not a card grid. The page refuses the category's hero-plus-cards arrangement: no banner, no stat tiles, no glassy pills. Dense agate rules carry authority.

OWN-WORLD: Newsprint grey-white ground, black ink, one press red used only for the section tab, the dateline and the pending marker. Oswald heavy condensed caps for headlines and masthead; Archivo Narrow with tabular figures for every table, label and body line. Hairline and 2px ink rules are the only grid; filled vs hollow squares carry W/L; no gradients, no shadows, no rounded cards.

STORY: The visitor sees a sports section's standings page, recognizes the format, finds the creator by typing, reads W, L, PCT, ROI, streak and last five, and opens the game log. They believe it because losses are listed exactly like wins and every settled pick is a box score with a date.

FIRST VIEWPORT: Masthead band at top: PICKRECEIPTS wordmark, dateline rule with today's date (ET), red RECEIPTS section tab, "Submit a pick" as a boxed classified-ad link at right. Under it the banner headline "Every pick. Every loss. On the record." across the full width in condensed caps, one standfirst line, and the FIND A CREATOR field. Then the standings: DIVISION I (popular) table at 8 of 12 columns with #, creator, W, L, PCT (break-even 52.4% marked), ROI, STRK, L5 squares, LAST pick; right column (4 of 12): BOX SCORES, settled yesterday, and ON DECK, tonight's pending picks under the red marker. Mobile stacks the table to name, W, L, PCT, STRK and puts box scores below.

FORM: Standings agate page, candidate 1 on my ordered list, chosen as IMPECCABLE'S PICK over the roll's assigned candidate 5 (out-of-town scoreboard). Seed key 75c91b10 (concept-seed, scope direction, mode persuade, 2026-10-26). Roll record: the decision page was served twice (keys 1c76c596 and 35d9ab8f under .impeccable/questions/) and timed out unanswered both times; the choice was then taken through the harness's structured question tool in conversation, where the user picked The Agate Page over the assigned candidate; the five decision comps named in the hand files were never generated because this harness has no image generation. Signature interaction: the FIND A CREATOR filter narrows both divisions and the box scores live, and a standings row expands inline to its last three picks on click. Motion grammar: no fades or slides; instant state changes with a 120ms rule-draw underline on hover and focus; nothing animates on load.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

## Unresolved

- Whether the green receipt logo PNG (`frontend/public/brand-mark.png`) returns to the masthead: it is designed for dark grounds and clashes with newsprint; the wordmark is set in type instead and the PNG stays as favicon.
