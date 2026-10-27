---
name: PickReceipts
description: Sports-section standings and box scores for betting creators' public records. Newsprint, ink, one press red.
colors:
  press: "#C8102E"
  news: "#E7E4DC"
  news-2: "#F0EEE8"
  news-3: "#DAD6CC"
  ink: "#121212"
  ink-2: "#3A3835"
  ink-3: "#625F59"
  rule: "#B5B1A7"
typography:
  display:
    fontFamily: "Oswald, Arial Narrow, sans-serif"
    fontSize: "clamp(46px, 8.4vw, 108px)"
    fontWeight: 700
    lineHeight: 0.9
    letterSpacing: "-0.015em"
  headline:
    fontFamily: "Oswald, Arial Narrow, sans-serif"
    fontSize: "clamp(40px, 7vw, 80px)"
    fontWeight: 700
    lineHeight: 0.9
    letterSpacing: "-0.015em"
  figure:
    fontFamily: "Oswald, Arial Narrow, sans-serif"
    fontSize: "36px"
    fontWeight: 700
    lineHeight: 1
    fontFeature: "tnum"
  title:
    fontFamily: "Oswald, Arial Narrow, sans-serif"
    fontSize: "15px"
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: "0.06em"
  standfirst:
    fontFamily: "Archivo Narrow, Arial Narrow, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.45
  body:
    fontFamily: "Archivo Narrow, Arial Narrow, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  agate:
    fontFamily: "Archivo Narrow, Arial Narrow, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.3
    fontFeature: "tnum"
  line:
    fontFamily: "Archivo Narrow, Arial Narrow, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.375
  meta:
    fontFamily: "Archivo Narrow, Arial Narrow, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Archivo Narrow, Arial Narrow, sans-serif"
    fontSize: "11px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.08em"
  control:
    fontFamily: "Oswald, Arial Narrow, sans-serif"
    fontSize: "14px"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "0.07em"
rounded:
  none: "0px"
spacing:
  hair: "1px"
  rule: "2px"
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  2xl: "40px"
  3xl: "48px"
  4xl: "80px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.news}"
    typography: "{typography.control}"
    rounded: "{rounded.none}"
    padding: "9px 16px"
  button-primary-hover:
    backgroundColor: "{colors.ink-2}"
    textColor: "{colors.news}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.control}"
    rounded: "{rounded.none}"
    padding: "9px 16px"
  button-secondary-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.news}"
  section-bar:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.news}"
    typography: "{typography.title}"
    rounded: "{rounded.none}"
    padding: "5px 10px 4px"
  input-url:
    backgroundColor: "{colors.news-2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "12px 14px"
  input-find:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "8px 0"
  result-mark-won:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.news}"
    rounded: "{rounded.none}"
    size: "18px"
  result-mark-lost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    size: "18px"
  result-mark-push:
    backgroundColor: "transparent"
    textColor: "{colors.ink-3}"
    rounded: "{rounded.none}"
    size: "18px"
  wordmark-tab:
    backgroundColor: "{colors.press}"
    textColor: "{colors.news}"
    rounded: "{rounded.none}"
    padding: "0.14em 0.22em 0.06em"
---

# Design System: PickReceipts

## Overview

**Creative North Star: "The Agate Page"**

PickReceipts is laid out like the standings page of a newspaper sports section. The creators are teams in a standings table (#, W, L, PCT, ROI, STRK, L5, LAST), yesterday's settled picks sit beside it as box scores, and tonight's pending picks wait under ON DECK. The visitor already knows how to read this format; the design borrows that literacy instead of teaching a new one. Authority comes from density and rules, not from decoration: a heavy 2px ink rule opens every table, hairlines separate rows, a reversed black bar heads every section.

The material is newsprint: a warm grey-white ground with a faint grain tiled under the whole page, black ink on top, and a single press red used so rarely that it reads as the section tab on the front page. Light mode only, by decision; newsprint is read under daylight. There are no cards, no shadows, no tonal gradients, no rounded corners, and no icons beyond the plus/minus on a row toggle. Wins and losses are letters in squares, W filled and L hollow, so the record reads identically in print, in grayscale, and to a colorblind reader. Losses are listed exactly like wins. This replaced the prior "Stadium Card" world (warm paper, amber, cobalt, Manrope, stat tiles) which is the confirmed anti-reference.

Motion is nearly absent. State changes are instant; the only transitions are a 120ms rule that draws in under a link and a 120ms color swap on boxed controls. Nothing animates on load.

**Key Characteristics:**
- Standings table, not card grid: every list is an agate table with a 2px ink head rule and hairline rows.
- Newsprint ground with SVG grain, black ink, one press red reserved for four jobs.
- Oswald condensed caps for headlines, figures and controls; Archivo Narrow with tabular numerals for everything else.
- W/L carried by filled vs hollow squares and the letter itself, never by color.
- Zero radius, zero elevation, zero tonal gradients; rules are the only grid.
- Controls are boxed like classified ads: 2px ink border, condensed uppercase, reverse on hover.

## Colors

A three-step newsprint ground, a three-step ink, one hairline rule tone, and one press red.

### Primary
- **Press Red** (`press`): The one accent, used only where a sports section would use its spot color: the RECEIPTS tab in the masthead wordmark, the dateline under the masthead, the 7px square that marks ON DECK / pending, and form error borders and text (the input's border, the alert's top and bottom rules, inline error copy). The `press-dim` tint (`rgba(200, 16, 46, 0.10)`) is defined in the Tailwind config but is not used anywhere in the build; do not reach for it.

### Neutral
- **Newsprint** (`news`): Page ground for html and body, with the grain tile over it. Also the text color on every reversed surface (section bars, filled W marks, primary buttons, the red tab).
- **Newsprint Light** (`news-2`): The one raised paper tone, used as the fill of the URL input on /submit.
- **Newsprint Shade** (`news-3`): Hover and open state of a clickable standings row, the background of the expanded recent-picks row, and the small right-hand caption inside a section bar.
- **Ink** (`ink`): Body text, every heavy rule (2px table head, masthead and footer rules, control borders), all reversed surfaces, focus outlines, and the ::selection background.
- **Ink Soft** (`ink-2`): Secondary copy: standfirsts, step paragraphs, masthead dateline strip, PCT values below break-even, parlay leg text, primary-button hover fill.
- **Ink Faint** (`ink-3`): Tertiary copy: handles, dates, odds, sport tags, table footnotes, placeholders, push marks, the scrollbar thumb.
- **Rule** (`rule`): Hairline between table rows and between list items; vertical dividers between the three "How the record is kept" columns.

### Named Rules
**The Four Jobs Rule.** Press red has exactly four jobs: the wordmark tab, the dateline, the pending marker, and form errors. It never decorates, never marks a win or a loss, never fills a button, and never appears in a table body except as the 7px on-deck square.

**The Letter Carries It Rule.** Win, loss and push are told by the letter (W, L, P) and the square it sits in (filled, hollow, dashed hollow). No color, including press red, may be the only thing that distinguishes a result.

**The Ink Reverse Rule.** Emphasis is a reversal, not a tint: a surface that needs weight goes ink-on-news to news-on-ink (section bars, W marks, primary buttons, hovered secondary buttons, the wordmark tab in red). There is no accent-tinted background anywhere in the system.

## Typography

**Display Font:** Oswald (with Arial Narrow, sans-serif), weights 500 and 700, loaded through next/font as `--font-oswald`
**Body Font:** Archivo Narrow (with Arial Narrow, sans-serif), weights 400 through 700, loaded as `--font-archivo`
**Label/Mono Font:** none; tabular numerals come from Archivo Narrow's `tnum` feature (`.tabular`, `.agate`)

**Character:** Two condensed faces doing newspaper jobs. Oswald is the headline and figure face: heavy, uppercase, tight, set with negative tracking at banner sizes and positive tracking at label sizes. Archivo Narrow is the agate: a narrow grotesk that packs a W-L-PCT-ROI row into a phone width and keeps every figure column aligned with tabular numerals.

### Hierarchy
- **Display** (700, `clamp(46px, 8.4vw, 108px)`, 0.9, -0.015em, uppercase): The homepage banner headline only ("Every pick. Every loss. On the record."), full width, text-balanced.
- **Headline** (700, `clamp(40px, 7vw, 80px)`, 0.9, -0.015em, uppercase): Page h1 on /creators/[id] (the creator's name) and /submit.
- **Figure** (700, 30px on mobile / 36px from sm, line-height 1, Oswald): The creator record row (GP, W, L, P, PCT, ROI, STRK, PICKS) on the creator page. PCT in this row is Oswald at 36px but takes the Pct component's weight (700 above break-even, 400 below).
- **Sub-headline** (700, 28px mobile / 36px sm, 0.95, -0.01em, uppercase): The result message on the submit success panel.
- **Title** (500, 15px, 1.2, 0.06em, uppercase, Oswald): The reversed section bar text (DIVISION I, BOX SCORES, ON DECK, GAME LOG, BY SPORT, HOW THE RECORD IS KEPT).
- **Control** (500, 14px, line-height 1, 0.07em, uppercase, Oswald): Button and boxed-link text. The masthead "Submit a pick" link is the same style at 13px.
- **Display Label** (500, 13px, 0.1em, uppercase, Oswald): Field labels (FIND A CREATOR, POST URL), "Back to standings", "Full game log" links.
- **Standfirst** (400, 17px, 1.45, Ink Soft, max 62ch): The one-line deck under a headline.
- **Body** (400, 15px, 1.5): Base body, explanatory paragraphs, empty-state messages, the "How the record is kept" steps.
- **Agate** (400, 14px, 1.3, tabular): Default table cell. Creator names in the standings are 15px semibold. Pick titles and the creator meta line are 14px.
- **Line** (400 or 600, 13px): Box-score lines, recent-picks rows, parlay legs on the creator page, small notes.
- **Meta** (400, 12px): Dates, handles, odds, events, footnotes under tables, footer copy, the "N creators on the record" count (uppercase, 0.08em).
- **Label** (700, 11px, 1.2, 0.08em, uppercase): Table column heads (`.agate th`), section-bar captions, the masthead dateline strip, and sport tags (600 or 700, 11px, 0.04 to 0.05em, Ink Faint).
- **Input** (400, 19px on the FIND field, 16px on the URL field): Oversized relative to body so the typed query reads like a headline being set.

### Named Rules
**The Tabular Rule.** Every table and every figure column is set with `font-variant-numeric: tabular-nums` and `font-feature-settings: "tnum"`. A number that will be compared against the number above or below it never uses proportional figures.

**The Condensed Caps Rule.** Oswald is always uppercase. It appears at three jobs only: headlines and big figures (700), section bars and controls (500), and small display labels (500). It is never used for running text or for table bodies.

**The Bold Means Break-Even Rule.** In any PCT column, 700 weight means the value clears the -110 break-even (52.4%); 400 weight in Ink Soft means it does not. The weight is the signal; a footnote under the table spells it out.

## Layout

One centered column, `max-width 72rem` (1152px), with 16px side padding below 640px and 24px from sm up. The masthead sits in the same column: wordmark and boxed "Submit a pick" link on the first line (20px top, 12px bottom), then a hairline ink rule and the 11px uppercase dateline strip, then the 2px ink rule that closes the header. Main content starts 32px below (40px from sm). The footer is pushed down 80px, opens with a 2px ink rule, and ends 48px above the viewport bottom.

Below `lg` (1024px) everything stacks in one column. From lg, the standings pages run a 12-column grid with a 40px column gap: the standings or game log take 8 columns, the aside (box scores and on deck; by sport on the creator page) takes 4. Stacked sections within a column are spaced 40px (home) or 48px (creator page). The aside is 48px below the main column when stacked and flush when side by side. There is no vertical rule between the 8-column and 4-column regions in the shipped build.

Vertical rhythm on a page: headline, 20px, standfirst, 36px, FIND field, 32px, first section bar. Sections after the board are 80px down. Section bars sit directly on their table with no gap; the table opens with its own 2px rule.

Table density is newspaper agate: heads padded 7px 8px 5px, cells 9px 8px, with the outermost cells pulled to 4px so the figures sit on the table's edge. Responsive columns drop by priority: GP and ROI hide below sm; L5 and LAST hide below md; the mobile standings keep #, creator, W, L, PCT, STRK and the toggle. The creator record row hides P, L5 and PICKS below sm.

The /submit page is a single 42rem (672px) column; at desktop widths the right half of the content column is empty newsprint.

Breakpoints are Tailwind's defaults: sm 640px, md 768px, lg 1024px.

## Elevation & Depth

Flat, by design. Nothing in the system is lifted. Depth is conveyed by rule weight (2px ink opens a table, 1px ink closes it, 1px rule tone separates rows) and by reversal (a section bar is a black band on the paper). The page's only texture is the grain tile on the body, an inline SVG fractal-noise filter at 180px repeat and roughly 9% ink alpha, which reads as paper stock rather than a layer.

Two `box-shadow` declarations exist and both are zero-blur ink strokes standing in for focus rings, not elevation: the FIND field thickens its bottom rule on focus (`0 3px 0 0 var(--ink)`) and the URL field grows a 2px ink outline on focus (`0 0 0 2px var(--ink)`). The global `:focus-visible` is a 2px solid ink outline offset 2px. The `.rule-link` underline is implemented with a solid-color `linear-gradient(currentColor, currentColor)` background sized from 0% to 100%; it is an underline mechanism, not a tonal gradient.

### Named Rules
**The No Lift Rule.** No drop shadows, no blurred shadows, no glass, no layered surfaces. If an element needs to come forward, reverse it to ink or give it a 2px ink rule. A `box-shadow` is permitted only as a hard, zero-blur ink stroke standing in for a focus ring.

**The Grain Is Paper Rule.** The newsprint grain belongs to the body background and nowhere else. Components do not carry their own texture, tint, or background image.

## Shapes

Everything is a rectangle with square corners; no border radius appears anywhere in the build (`rounded` is `0px`). Form language is the rule and the box: 2px ink rules open tables and bound controls, 1px ink rules close tables and separate the masthead and record sections, 1px rule-tone hairlines separate rows. Result marks are squares (18px default, 16px in tables, 12 to 13px inside parlay legs) with the result letter centered; the L5 form strip is five 10px squares (14px on the creator record) at 3 to 4px gaps, filled for W, 2px hollow for L, 1.5px dashed hollow at 60% for P, 1px hollow at 25% for an empty slot. The on-deck marker is a 7px filled red square. Parlay legs hang off a 1px ink rule on their left. Profile images are square, cropped to cover, 2px ink border, rendered grayscale with contrast raised 25% so a color avatar reads as a halftone portrait.

## Components

Controls are boxed like classified ads; tables are agate; headings are reversed bars. Every state change is instant except a 120ms color or underline transition.

### Buttons
- **Shape:** Square-cornered box (0px), 2px ink border, inline-flex, centered, 8px gap.
- **Primary:** Ink fill, newsprint text, Oswald 500 14px uppercase 0.07em, padding 9px 16px. The "Put it on the record" submit and "Submit another".
- **Secondary / BoxedLink:** Transparent fill, ink text, same border and type. "Back to standings". The masthead "Submit a pick" is the same box at 13px with 7px 12px padding.
- **Hover:** Primary fill and border shift to Ink Soft; secondary reverses to ink fill with newsprint text. `transition-colors 120ms`.
- **Focus:** Global 2px ink outline, 2px offset.
- **Disabled:** 40% opacity, not-allowed cursor; the submit button shows "Filing…" while pending.
- **Row toggle:** A 22px square with a 1.5px ink border holding a 12px inline-SVG plus (minus when open); reverses to ink on hover.

### Section Bar
- **Style:** Reversed ink band, newsprint text, Oswald 500 15px uppercase 0.06em, padding 5px 10px 4px, flex with baseline alignment and 12px gap.
- **Caption:** Optional right-hand `small` in Archivo Narrow 11px 0.08em in Newsprint Shade ("4 creators", "Latest settled", "Settles about 15 minutes after the game ends").
- **On deck variant:** A 7px press-red square precedes the title (`.on-deck::before`). Also used for the "Held for review" state on the submit success panel.

### Agate Table
- **Frame:** Full width, collapsed borders, 2px ink top rule, 1px ink bottom rule, tabular numerals.
- **Head:** 11px 700 uppercase 0.08em ink, 1px ink rule beneath, no wrap. Box-score tables keep their head screen-reader-only.
- **Cells:** 14px, line-height 1.3, 9px 8px padding, 1px rule-tone hairline beneath; last row has none. `.num` cells right-align and never wrap.
- **Row states:** `.is-link` rows take a pointer cursor and fill Newsprint Shade on hover; `.is-open` rows hold that fill and hide their bottom hairline so the expanded detail row reads as part of the same block. The detail row is Newsprint Shade, opens with a 1px ink rule, and is indented 26px.
- **Footnote:** 12px Ink Faint paragraph beneath the table explaining GP, PCT bold, ROI, STRK, L5.

### Result Mark
- **Won:** Ink-filled square, newsprint "W" in Oswald 700 at 64% of the box size.
- **Lost:** Hollow square, 2px ink border at 16px and up (1.5px below), ink "L".
- **Push:** Hollow square, dashed Ink Faint border, Ink Faint "P".
- **Pending:** No square; the word PENDING in 12px 600 uppercase 0.06em ink with the red on-deck marker before it. In the game log an unsettled past pick reads UNSETTLED in Ink Faint without the marker.
- **Void:** The word VOID in 12px uppercase Ink Faint.
- Each mark carries a `title` and a visually hidden suffix ("W" + "on") so the letter is read as the word.

### Form Strip (L5)
Inline SVG of five squares, oldest left to newest right, drawn in `currentColor`: filled for W, 2px hollow for L, 1.5px dashed hollow at 60% opacity for P, 1px hollow at 25% for an unplayed slot. 10px squares at 3px gap in the standings; 14px at 4px on the creator record. Carries an `aria-label` reading the sequence.

### Pct
A number to one decimal. 700 weight in ink when it clears 52.4%; 400 weight in Ink Soft when it does not; an em dash in Ink Faint when there is no settled record. A `title` names the break-even either way.

### Inputs / Fields
- **Label:** Oswald 500 13px uppercase 0.1em ink, block, above the field.
- **FIND A CREATOR (search):** No box; a 2px ink bottom rule only, transparent fill, 19px text, 8px vertical padding, no horizontal padding, Ink Faint placeholder. Focus thickens the rule to 3px via a hard box-shadow; the outline is suppressed.
- **POST URL:** 2px ink border, Newsprint Light fill, 16px text, 12px 14px padding, Ink Faint placeholder, 120ms color transition. Focus adds a 2px ink outline ring via hard box-shadow. Disabled drops to 50% opacity.
- **Error:** Border turns press red; a 13px 600 press-red message follows the field. Form-level errors are a `role="alert"` band with 2px press-red top and bottom rules and 14px 600 press-red text.
- **Caret:** Press red in every input and textarea.
- **Live count:** 12px uppercase 0.08em Ink Faint beside the FIND field, `aria-live="polite"`.

### Links
- **Rule link:** Inherits color (ink, usually 600 weight); a 2px `currentColor` rule draws in from the left over 120ms ease-out on hover and focus-visible. `.is-on` holds the rule drawn (used on the "Flag for manual review" button so it reads as a link). Disabled under `prefers-reduced-motion`.
- **Display link:** The same rule link set in Oswald 500 13px uppercase 0.08 to 0.1em ("Back to standings", "Full game log · N picks").

### Navigation (Masthead)
- **Wordmark:** PICK in ink, RECEIPTS reversed in the press-red tab (padding 0.14em 0.22em 0.06em, 0.18em gap), Oswald 700 uppercase -0.01em, 32px in the header. Links home.
- **Dateline strip:** 11px uppercase 0.08em; the date in press red at left, "Standings and box scores · All times Eastern" in Ink Soft at right (shortened to "All times Eastern" below sm).
- **Action:** The boxed "Submit a pick" link at right, bottom-aligned with the wordmark.
- **Rules:** 1px ink between wordmark line and dateline; 2px ink closing the header.
- **Mobile:** Same layout; nothing collapses. There is no menu.

### Standfirst
17px Archivo Narrow at 1.45 in Ink Soft, max 62ch, 20px under the headline.

### Three-Up Steps (How the record is kept)
Under a section bar, three paragraphs in a grid: one column below sm, three from sm with 1px rule-tone vertical dividers and 20px side padding, closed by a 1px ink rule. Each starts with a 700 ink lead-in ("Capture.", "Settle.", "Record.") in 15px Ink Soft body.

### Empty and Error Bands
A paragraph bounded by 2px ink rules top and bottom (`border-y-2`) with 16px vertical padding, 15px Ink Soft text and a 600 ink lead line ("Could not reach the record."). Section-level empties are a single 1px ink bottom rule with 13px Ink Faint text.

## Do's and Don'ts

### Do:
- **Do** open every table with a 2px ink rule, separate rows with 1px rule-tone hairlines, and close with a 1px ink rule (`.agate`).
- **Do** set every number column in tabular numerals and right-align it (`.num`).
- **Do** head every section with the reversed ink bar at Oswald 500 15px uppercase 0.06em, with the optional 11px caption at right.
- **Do** carry W, L and P as letters in filled, hollow and dashed-hollow squares; keep the hollow stroke at 2px from 16px so a loss scans as heavily as a win.
- **Do** list losses exactly like wins: same row, same size, same weight, same column.
- **Do** box controls with a 2px ink border and Oswald 500 uppercase at 0.07em; reverse to ink on hover with a 120ms color transition.
- **Do** keep press red to the wordmark tab, the dateline, the 7px on-deck marker, and form errors.
- **Do** show PCT at 700 weight only when it clears 52.4%, and footnote the break-even under the table.
- **Do** render profile images grayscale, contrast 125%, square, with a 2px ink border.
- **Do** keep the page light: `color-scheme: light`, newsprint ground with the body grain, no dark variant.
- **Do** respect `prefers-reduced-motion` by dropping the rule-draw transition; nothing else animates.

### Don't:
- **Don't** add cards, panels, stat tiles, or any bordered-and-filled container. A block is a section bar over a table, bounded by rules.
- **Don't** add drop shadows, blurred shadows, glass, or layered surfaces. The only permitted `box-shadow` is a zero-blur ink stroke standing in for a focus ring.
- **Don't** add tonal gradients. The solid-color `linear-gradient` inside `.rule-link` is an underline mechanism, not a license.
- **Don't** round a corner. Radius is 0px everywhere.
- **Don't** use color to signal win, loss, push or streak direction; never green for W or red for L.
- **Don't** use press red for a button fill, a hover state, a table head, a stat, or any decoration; and don't use `press-dim`, which the build does not use.
- **Don't** add emoji, glyph icon fonts, or icon packages. The only icon is the inline-SVG plus/minus on the row toggle.
- **Don't** set Oswald in mixed case or use it for running text or table bodies; don't set Archivo Narrow headlines above 19px.
- **Don't** use proportional figures in anything that stacks numbers.
- **Don't** add fades, slides, or load animations; state changes are instant, with only the 120ms rule-draw and color transitions.
- **Don't** reintroduce the "Stadium Card" world (warm paper, amber, cobalt, Manrope, rounded cards) or the March brand palette (signal green, alert orange, Barlow Condensed); both are confirmed anti-references.
