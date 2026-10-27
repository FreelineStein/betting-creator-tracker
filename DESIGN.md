---
name: PickReceipts
description: A dark betting-media app shell in the receipt logo's palette. Creator cards, lettered W/L chips, lime for wins, orange for losses.
colors:
  win: "#A8F55C"
  win-bright: "#BDFA7E"
  win-dim: "rgba(168, 245, 92, 0.14)"
  loss: "#FF6A3D"
  loss-dim: "rgba(255, 106, 61, 0.15)"
  ground: "#0C0F0D"
  panel: "#151A17"
  panel-2: "#1C221E"
  panel-3: "#232A25"
  line: "#262D28"
  line-2: "#3A443D"
  fg: "#EEF1EC"
  fg-2: "#A9B0A6"
  fg-3: "#848C81"
typography:
  display:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "clamp(40px, 5.6vw, 68px)"
    fontWeight: 800
    lineHeight: 0.98
  headline:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.02em"
  stat:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.1
    fontFeature: "tnum"
  stat-lg:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "38px"
    fontWeight: 700
    lineHeight: 1.1
    fontFeature: "tnum"
  title:
    fontFamily: "Barlow, Arial, sans-serif"
    fontSize: "17px"
    fontWeight: 700
    lineHeight: 1.25
  lede:
    fontFamily: "Barlow, Arial, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.5
  body:
    fontFamily: "Barlow, Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Barlow, Arial, sans-serif"
    fontSize: "11.5px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.06em"
rounded:
  chip: "7px"
  control: "10px"
  card: "14px"
  full: "9999px"
spacing:
  row-gap: "10px"
  card-x: "18px"
  card-y: "16px"
  column-gap: "32px"
  section: "40px"
  break: "80px"
components:
  button-primary:
    backgroundColor: "{colors.win}"
    textColor: "#000000"
    rounded: "{rounded.control}"
    padding: "10px 18px"
  button-primary-hover:
    backgroundColor: "{colors.win-bright}"
  button-secondary:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.fg}"
    rounded: "{rounded.control}"
    padding: "10px 18px"
  button-secondary-hover:
    backgroundColor: "{colors.panel-2}"
  chip-win:
    backgroundColor: "{colors.win-dim}"
    textColor: "{colors.win}"
    rounded: "{rounded.chip}"
    size: "26px"
  chip-loss:
    backgroundColor: "{colors.loss-dim}"
    textColor: "{colors.loss}"
    rounded: "{rounded.chip}"
    size: "26px"
  chip-push:
    backgroundColor: "{colors.panel-3}"
    textColor: "{colors.fg-3}"
    rounded: "{rounded.chip}"
    size: "26px"
  card:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.card}"
    padding: "16px 18px"
  card-open:
    backgroundColor: "{colors.panel-2}"
  input:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.fg}"
    rounded: "{rounded.control}"
    height: "52px"
    padding: "0 16px"
---

# Design System: PickReceipts

## Overview

**Creative North Star: "The Receipt on the Scoreboard"**

The familiar betting-media app shell, played straight and at full quality: a near-black ground, rounded creator cards with avatars, lettered W/L chips, condensed caps for every number that matters. The palette is lifted directly from the receipt logo: its lime check is the color of a win and of the primary action, its orange cross the color of a loss. Nothing else in the system is saturated, so the two result colors carry the whole page.

Density is moderate and phone-first. One creator card holds the verdict a visitor from X needs (Record, Win %, ROI, last-5 form) in a single glance, then expands in place for recent picks. Depth comes from three stepped panel tones and hairline borders, never from shadows. The system is dark only.

The previous "Agate Page" newsprint world (paper ground, Oswald, press red, ruled tables) was rejected and is an anti-reference.

**Key Characteristics:**
- Near-black ground, three tonal panel steps, hairline borders, no shadows.
- Lime means win / clears the line / do this; orange means loss / below zero. Nothing else is colored.
- Every result is a letter (W, L, P) on its tinted chip; color never travels alone.
- Barlow Condensed uppercase for headlines, section heads and stats; Barlow for everything read.
- Three radii only: chip (7px), control (10px), card (14px), plus full circles for avatars, dots and pills.

## Colors

Two signal colors from the logo on a green-tinted near-black neutral ramp.

### Primary
- **Receipt Lime** (`win`): wins, the primary button, the break-even-clearing Win %, positive ROI, active link text, the pending dot, focus rings, text selection and the input caret. On a filled button its text is pure black.
- **Lime Flare** (`win-bright`): primary-button hover only.
- **Lime Wash** (`win-dim`): W chip fill, numbered step discs, the "On the record" status pill.

### Secondary
- **Cross Orange** (`loss`): losses, negative ROI, losing streaks, field errors and form alerts.
- **Orange Wash** (`loss-dim`): L chip fill and alert backgrounds (alerts add a 40% orange border).

### Neutral
- **Ground** (`ground`): page background, sticky header (at 90% with a blur), and the submit field's inset fill.
- **Panel** (`panel`): every card and container at rest.
- **Raised Panel** (`panel-2`): card hover and open state, avatar disc, secondary-button hover.
- **Top Panel** (`panel-3`): push chip, rank badge, the "Held for review" pill.
- **Hairline** (`line`): card borders, list dividers, empty form-slot dashes, the header and footer rules.
- **Strong Hairline** (`line-2`): hovered/open card border, secondary-button border, control borders, parlay leg rail, scrollbar thumb.
- **Chalk** (`fg`): headlines, names, figures, primary text.
- **Dim Chalk** (`fg-2`): ledes, panel body copy, secondary text.
- **Faint Chalk** (`fg-3`): handles, meta lines, stat labels, captions, placeholders, footer.

### Named Rules
**The Two Signals Rule.** Lime and orange are the only saturated colors, and they mean result. A new surface may not introduce a third accent or use lime/orange decoratively.

**The Break-Even Rule.** Win % turns lime only at or above 52.4% (the −110 break-even). Below it the figure stays Chalk, not orange: a sub-break-even rate is not a loss. ROI goes lime above zero, orange below.

## Typography

**Display Font:** Barlow Condensed (with Arial Narrow, sans-serif), weights 600-800
**Body Font:** Barlow (with Arial, sans-serif), weights 400-700

**Character:** A scoreboard pairing from one family: the condensed cut stands up in caps for headlines and numbers, the regular cut does all the reading.

### Hierarchy
- **Display** (800, clamp(40px, 5.6vw, 68px), 0.98, uppercase, balanced): the one page headline. Creator page and submit page use the same treatment at clamp(34px, 5vw, 56px) and clamp(36px, 5vw, 60px). A trailing clause may turn lime ("On the record.").
- **Headline** (700, 22px, 1.0, uppercase, 0.02em): section heads (Division I, Box scores, On deck), with an optional Barlow 14px count in Faint Chalk and a 13px caption on the right. Smaller condensed caps heads (17-19px) title step cards and sport rows.
- **Stat** (700, 24px card / 30-38px creator header, 1.1, tabular figures): Record, Win %, ROI, Streak, Picks.
- **Title** (Barlow 700, 17px): creator names on cards. Pick titles are Barlow 600 at 15-15.5px.
- **Lede** (Barlow 400, 17px, 1.5, max 58ch, Dim Chalk): the single line under a headline.
- **Body** (Barlow 400, 16px, 1.5): base text; panel copy runs 14-15px, meta lines 12.5-13.5px in Faint Chalk joined by " · ".
- **Label** (Barlow 600, 11.5-13px, 0.06em, uppercase, Faint Chalk): stat labels, field labels, pills.

### Named Rules
**The Tabular Figures Rule.** Every stat, odds value and record figure sets in tabular numerals so columns of numbers align card to card.

**The Condensed Is For Shouting Rule.** Barlow Condensed is uppercase and bold (600+) wherever it appears; it never sets running text.

## Layout

A single centered column capped at 1152px (`max-w-6xl`) with 16px gutters, 24px from 640px. The header is sticky, 64px tall (72px from 640px), holding only the logo and the primary "Submit a pick" button.

At 1024px and up, list pages split into a main column and a fixed side rail: 320px on home and creator pages (32px gap), 360px on submit (48px gap). The rail carries On deck / Box scores / By sport; below 1024px it stacks after the main column with 48px above it.

Rhythm: 10px between creator cards, 40px between sections, 80px before the closing "How the record is kept" block and the footer. Cards pad 16px vertically and 16-18px horizontally; list rows inside panels pad 12-14px with hairline dividers.

The creator card reflows by width: on phones, avatar + name + expand button sit on the first row and Record / Win % / ROI form a three-up grid with the form chips below; from 768px everything sits on one row in fixed stat columns (84 / 76 / 70px).

## Elevation & Depth

Flat. There are no shadows anywhere. Depth is tonal: Ground, then Panel, then Raised Panel on hover or open, then Top Panel for the smallest chips and badges. Borders step with the tone (Hairline at rest, Strong Hairline on hover/open). The only translucency is the sticky header: Ground at 90% with a medium backdrop blur.

### Named Rules
**The No-Shadow Rule.** A surface rises by getting one panel step lighter and one border step stronger, never by casting a shadow.

## Shapes

Three corner radii, each bound to a scale of object: chips and the expand button 7px, buttons and inputs 10px, cards and panels 14px. Fully round forms are reserved for avatars (with a 2px Hairline ring), the rank badge, pending and status dots, numbered step discs, and pills (Pending, submission status). Borders are always 1px hairlines except the avatar ring and the rank badge's 2px panel-colored cutout. Empty form slots are dashed-outline chips of the same size as a result chip. Parlay legs hang off a 1px Strong Hairline rail on the left.

## Components

### Buttons
Solid and quick; bold Barlow at 15px.
- **Shape:** gently rounded (10px).
- **Primary:** Receipt Lime fill, black text, 10px 18px padding. Used once per view for the main action (Submit a pick, Submit another).
- **Hover / Focus:** fill brightens to Lime Flare over 150ms; focus shows the global 2px lime outline at 2px offset. Disabled drops to 40% opacity.
- **Secondary:** Panel fill, Strong Hairline border, Chalk text; hover lifts to Raised Panel with a Faint Chalk border.
- The header button compacts to 8px 14px at 14px on phones.

### Result Chips
The system's signature mark.
- **Style:** a square chip (26px default, 24px in lists, 16px on parlay legs, 28px in the creator header), 7px corners, condensed bold letter at 54% of the chip size. W on Lime Wash in lime, L on Orange Wash in orange, P on Top Panel in Faint Chalk. Each carries a screen-reader word (Won, Lost, Push).
- **Pending:** a full pill with a Strong Hairline border, a 6px lime dot and "PENDING" label caps. Void is plain label caps.
- **Form strip:** the last five results oldest to newest left to right, 4px apart, padded on the left with dashed empty slots; exposed to assistive tech as one labeled image.

### Cards / Containers
- **Corner Style:** 14px.
- **Background:** Panel at rest; Raised Panel on hover and when open.
- **Shadow Strategy:** none (see Elevation & Depth).
- **Border:** 1px Hairline; Strong Hairline on hover and open.
- **Internal Padding:** 16px 18px (16px horizontal on phones). Message panels use 16px 20px.

### Inputs / Fields
- **Style:** 52px tall, 10px corners, 16px medium text, Faint Chalk placeholder. The find-a-creator field is Panel-filled with a Hairline border and an inline 18px search icon; the submit URL field is Ground-filled with a Strong Hairline border.
- **Focus:** the border turns lime (150ms); the global outline is suppressed on the field itself.
- **Error / Disabled:** error border and 13px semibold message in orange; disabled at 50% opacity. Form-level errors sit in an Orange Wash box with a 40% orange border.

### Navigation
The sticky header is the only navigation: logo left (38px tall, 44px from 640px), primary button right. In-page links are text with a 1.5px underline that fades in on hover and focus (offset 3px, 150ms ease-out); action links are lime and bold, "back" links are Dim Chalk turning Chalk.

### Creator Card
The page's unit. An expandable list item: 48px avatar with an overlapping rank badge, name (links to the full record) over handles, Record / Win % / ROI stats, last-5 form, and a 30px chevron button (7px corners, Strong Hairline) that rotates 180° when open. Clicking anywhere on the card toggles it; only one card is open at a time. The open state adds a Hairline divider and a list of recent picks with result chips, then a lime "Full record" link. Above the divisions, the find-a-creator field filters cards live by name or handle, with a polite live-region count.

### Pick Line
The repeated row in Box scores, On deck, game logs and submission results: a leading result chip (or an 8px lime dot when pending), a 12.5-13px Faint Chalk meta line, a 15-15.5px semibold title, and the event in Faint Chalk, rows split by Hairline dividers inside a Panel.

## Do's and Don'ts

### Do:
- **Do** letter every result: W, L or P on its chip, with the screen-reader word attached.
- **Do** keep lime and orange for results and the single primary action; everything else is the neutral ramp.
- **Do** step depth with panel tone and border strength (Panel to Raised Panel, Hairline to Strong Hairline) on hover and open states.
- **Do** set every stat in Barlow Condensed bold with tabular figures.
- **Do** keep transitions to 150ms color/transform changes, and honor `prefers-reduced-motion` (all transitions off).
- **Do** use only the three radii (7px, 10px, 14px) plus full circles.

### Don't:
- **Don't** add shadows, glows or gradients to any surface.
- **Don't** color a below-break-even Win % orange; it stays Chalk.
- **Don't** introduce a light theme; the system is dark only.
- **Don't** introduce a third accent color or use lime/orange as decoration.
- **Don't** return to the rejected "Agate Page" newsprint look (paper ground, Oswald, press red, ruled agate tables).
