# VisureX design plan

Revised 9 Nov 2026: light-only visual refresh. The dark theme and its toggle are removed.

## Subject and audience

AI quality inspection for small Indian manufacturers in WCTE's network of 50+ MSMEs. The people who open it are a quality lead or line inspector at one of those plants, and a reviewer with one minute. The site's job is to show one real inspection decision first, then the record flow behind it (walk, NCR, corrective action, closure).

The visual vocabulary comes from the paperwork of a quality department: the inspection record with labelled fields, the hang tag tied to a part (accepted, rejected, on hold), the inspection checklist with tick boxes, and the blue ballpoint that fills them in.

## Pass one

### Palette

| Name | Hex | Role |
|---|---|---|
| Graphite ink | `#1A2630` | Text and headings |
| Steel | `#52626D` | Secondary text, captions, provenance |
| Record paper | `#F4F6F6` | Page background, a cool grey with a hint of green |
| Form white | `#FFFFFF` | Fields, the bench, record rows |
| Ballpoint blue | `#1F4E8C` | Primary actions, links, focus, the DINOv2 series |
| Hold amber | `#9C5A00` | PatchCore series, the "retake" tag |

State colours appear only on the inspection tag: accept green `#1E6B3F`, reject red `#B3261E`, each on its own pale tint. Lines are split in two: a hairline `#D8DFE3` for dividers and a field border `#8C9BA5` for inputs only.

### Type

IBM Plex Sans, self-hosted as woff2 (400 for text, 600 for labels and headings). IBM Plex Sans Condensed 600 for the wordmark and the verdict on the tag, where a narrow, stamped letter fits a tag and keeps "Retake photo" on one line. Plex was drawn for IBM's engineering culture, which suits measurement records better than a neutral UI face. Scale: body 1rem/1.55; home title 2.5rem; platform page titles 2rem; section titles 1.375rem; fine print 0.875rem. Numbers use tabular figures. Form values are regular weight, labels are 600.

### Layout

Left-aligned throughout, one 1120px column. Every section's left edge lines up with the bench.

```text
VisureX   Home Inspect Walk NCR Actions Dashboard                 GitHub
-------------------------------------------------------------------------
[ VisureX is under active development. This site is a prototype ... ]
AI quality inspection for MSME manufacturing
Built at WCTE, IIT Madras, to improve quality-inspection workflows ...
+-----------------------------+-----------------------------------------+
|  light table with           |  Reference part [select]               |
|  measuring grid             |  Test image     [select]               |
|     ( washer )              |  .-------------------------------.     |
|                             |  | o  Defect                      |     |
|                             |  |    Score 0.412  Threshold 0.299|     |
|                             |  '-------------------------------'     |
|                             |  [Run inspection]                      |
+-----------------------------+-----------------------------------------+
How it works       1 Capture  2 Check  3 Record  4 Assign  5 Close
Results            DINOv2 k-NN   |----o----|
                   PatchCore  |-------[]-------|     (amber)
                   k=8 means ... With full training data PatchCore ...
What has been checked
footer: affiliation / student research prototype, not a Walmart product
```

Platform pages (Walk, NCR, Actions, Dashboard): context bar (Plant, Role), a 2rem title, then records. Record forms use a two-column field grid on desktop like a printed NCR form; one column on mobile. Facts are written as label and value pairs ("Owner QA lead", "Due 2026-11-07") with small tags for "Overdue" and "Demo data".

### Principles

1. The verdict is a tag. The inspection result is drawn as a hang tag with a punched hole, coloured by decision: green for OK, red for Defect, amber for Retake photo. It is the one bold element on the site and the only place with saturated colour.
2. Everything else is a calm record. Hairline dividers, labels above fields, label and value pairs, no slash-joined strings, no cards with shadows.
3. Evidence sits beside the claim, including its limits: k=8 is explained under the chart and the full-data result where PatchCore leads is stated in the same place.

## Pass two: review against the brief

Checked each choice against what a generic page for "AI inspection tool" would get.

- The old specimen panel was a dark navy block. That is a default "dark hero" move and fought the verdict for attention. Changed to a pale light-table surface with a faint measuring grid, so the only strong colour on the bench is the tag.
- A results "hero stat" (big 0.956 with a label) was the obvious opener. Kept the interval plot instead and gave PatchCore its own warm colour so the comparison reads without relying on marker shape.
- Generic UI would use one blue for every button. Changed to a clear hierarchy: filled ballpoint blue for the main step on each page (Run inspection, Start walk, Submit NCR, Close action), outlined for secondary actions (exports, confirm, save draft).
- A system font stack or Inter would be the default. Chose Plex Sans plus Plex Sans Condensed for the tag only.
- Avoided: cream and clay, near-black with neon, newspaper columns, identical rounded cards with soft shadows, gradient washes, all-caps eyebrows, middle-dot meta strings, arrows in buttons, monospace labels, fade-ins on scroll. The only motion is a short stamp-in when a new verdict appears, which answers the user's click and is turned off under reduced motion.
- Numbering stays only on the five-step workflow, which is a real sequence.
- Dark mode removed on request: one light theme, `color-scheme: light`.
- Self-critique after screenshots: removed the small tag icon beside the wordmark (the favicon already carries it), set secondary buttons to regular weight so only the primary step reads as filled and bold, and capped single-choice selects at 580px so the Dashboard and NCR pickers do not stretch across the page.
