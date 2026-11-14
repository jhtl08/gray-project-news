# Plan: UI/UX refresh for Gray Project News

## Context

The frontend works end to end but was built for function, not for reading. It is one hardcoded dark palette in `frontend/src/index.css`, one 270-line `App.css`, three views that repeat the same table, form and feedback markup and no shared primitives.

Two inputs set the bar for this work: `AGENTS.md` and the `skills/` collection added to the repository. The `better-*` skills give exact rules for accessibility, layout, writing, typography, color and polish, plus a measurement method for contrast. This plan applies them to the whole frontend.

Goal: a calm, modern, information-dense interface that is trustworthy at 320px, under a keyboard and with a screen reader, without changing the backend contract or the stack.

Scope: `frontend/` plus a short `README.md` update. `backend/`, `skills/` and `AGENTS.md` are not modified.

### Evidence: what is wrong today

| Area | Problem | Location |
| --- | --- | --- |
| Shell | Tabs are plain buttons with an `active` class. No `aria-selected`, no tablist, no arrow-key movement, so assistive tech never hears the current view | `src/App.jsx:12-36` |
| Shell | Header chrome is full-bleed while content is centered, so the title and tabs share no edge with the data | `src/App.css:7-16`, `src/App.css:44-50` |
| Shell | Page title is the Vite default | `index.html:6` |
| Shell | No skip link, no sticky header, no `scroll-padding` for anchored focus | `src/App.jsx:38` |
| Data | 9 and 11 column tables at `13px` with no sticky header and no numeric alignment | `src/News.jsx:348-365`, `src/Bets.jsx:333-348` |
| Data | Every row renders a filled accent "Match" button, so one page shows 100 primary actions | `src/News.jsx:386-393`, `src/Bets.jsx:375-385` |
| Data | Price renders `0.106` and moves render `-0.0020`. On a prediction market these are a 10.6% probability and a 0.2 point move | `src/Bets.jsx:5-19` |
| Data | `tags` is a JSON string in the database, so the cell prints `["Politics","Iran"]` | `src/Bets.jsx:364`, `backend/db_operations.py:754` |
| Data | `status_quo_deviation` renders `0` or `1` and `emotionality_score` renders a bare number | `src/Bets.jsx:362-363` |
| Data | The direction select labels `desc` as "Ascending" and `asc` as "Descending", so the control names the opposite of what it does | `src/News.jsx:330-331` |
| Data | Every sort change calls `fetchNews` from a `setTimeout` while an effect also refetches, so each change sends two requests and a slow reply can overwrite a newer one | `src/News.jsx:306-334` |
| Data | The tag filter refetches on each keystroke, with no debounce | `src/Bets.jsx:283-292` |
| Data | Pagination prints "Showing 1 to 0 of 0" when the list is empty | `src/News.jsx:401-415`, `src/Bets.jsx:390-404` |
| States | A failed fetch is only `console.error`, so an outage renders "No news entries found." An error looks like an empty database | `src/News.jsx:133`, `src/Bets.jsx:80` |
| States | "Loading..." replaces the whole table, so the page jumps on every fetch and nothing is announced | `src/App.css:264-271` |
| States | No empty state offers a next action | `src/News.jsx:345`, `src/Bets.jsx:327`, `src/Matches.jsx:64` |
| Feedback | Feedback is a plain `div` with no `role="status"` or `role="alert"`, so success and failure are silent to screen readers. Match feedback also renders at the top of the panel, far from the row that was clicked | `src/News.jsx:339-341`, `src/Bets.jsx:330-332` |
| Destructive | Range delete is a `window.confirm` behind the primary accent button, labelled "Delete", placed inside the query panel as if it were a filter. The accent color marks a destructive action, and the dialog names no scope | `src/News.jsx:185`, `src/News.jsx:423-437`, `src/Bets.jsx:166`, `src/Bets.jsx:414-428` |
| Forms | The delete date inputs have visible labels with no `for`/`id`, so they are not programmatically labelled | `src/News.jsx:426-432`, `src/Bets.jsx:417-423` |
| Forms | The collect submit spans the full grid width as an accent bar under a four-column form | `src/App.css:125-146` |
| Matches | Seed list is a raw table of `id`, source, embedding text and a button. The delete endpoint has no UI | `src/Matches.jsx:64-104`, `backend/main.py:518` |
| Matches | "Selected" is the disabled condition on `relatedLoading`, so the label describes the wrong state | `src/Matches.jsx:89-91` |
| Matches | Similarity renders as a bare `0.7xxx` with no ranking cue | `src/Matches.jsx:136-140` |
| Tokens | One hex palette with no ramp and no semantic indirection. `--code-bg`, `--warning` and `--mono` are referenced nowhere | `src/index.css:1-14` |
| Type | Root `letter-spacing: 0.18px` on body copy, `font: 16px/145%` with a percentage line-height, heading sizes in `px`, no scale, no role tokens | `src/index.css:19-20`, `src/index.css:44-61` |
| Type | No `tabular-nums` anywhere, so prices, scores and volumes shift between rows. No `text-wrap`, no measure cap, no `overflow-wrap` | all views |
| Motion | `transition: all 0.2s` on three control classes, no reduced-motion guard, hover rules not gated by pointer capability | `src/App.css:30`, `src/App.css:72`, `src/App.css:133` |
| Assets | `index.html` links `/favicon.svg` and no `public/` directory exists, so the icon 404s | `index.html:5` |

Measured color, computed from the declared tokens rather than estimated:

| Pair | Ratio | Requirement | Result |
| --- | --- | --- | --- |
| `--text` `#e5e7eb` on `--bg` `#0f1117` | 15.24:1 | 4.5:1 (1.4.3) | Pass |
| `--accent` `#c084fc` on `--accent-bg` over surface | 5.35:1 | 4.5:1 | Pass |
| `--error` `#ef4444` on its own 0.15 fill | 4.07:1 | 4.5:1 | Fails |
| `--border` `#2e303a` as an input boundary on `--bg` | 1.44:1 | 3:1 (1.4.11) | Fails |
| Input fill `--bg` on the `--bg-secondary` panel | 1.06:1 | 3:1 (1.4.11) | Fails |

### What is already sound

- The collect form in `src/News.jsx:233-290` binds every label to its input with `for`/`id`.
- `main` exists as a landmark and heading order is coherent inside views.
- The browser focus ring is never suppressed, which is the correct default to preserve.
- The duplicated FastAPI error parsing across all three views already handles both string and object `detail` shapes. It should become one helper, not new logic.
- `backend/main.py` returns everything the UI needs. Tags, hostnames and probability units are all derivable in the client.

## Approach

Settled with the user:

1. Refine the existing dark appearance only. No theme switch.
2. Polished tables at 760px and wider, stacked cards below it. One breakpoint, owned in one place.
3. Zero new dependencies. Hand-rolled SVG icons, system font stack, plain CSS.
4. Frontend only, plus client-side workflow fixes: correct sort labels, single fetch effect with stale-response cancellation, debounced filters, real error and empty states, confirm dialog naming scope, seed deletion, client-side filter of loaded rows. The Ascending and Descending options keep their current top-to-bottom order. Their values change so each label produces the order it names.

Design direction: a quiet near-black canvas, one violet accent reserved for the single primary action per view, borders for structure and elevation only on dialogs, tabular figures for every number, motion only on press, hover and dialog entry, always gated.

Principles this refresh is held to, taken from the `better-*` skills:

- Content first. The story or the market question leads every row, and identifiers and metadata trail it.
- One primary action per view. Row actions are quiet icon buttons, not a hundred filled ones.
- Space groups content first. A line separates only where space cannot carry the grouping.
- Numbers are read in columns, so they align, use tabular figures and keep one precision.
- Meaning never rides on color alone. Every status carries a word or an icon beside its hue.
- Every state points forward. Empty and error states say what this is and what to do next, and loading never blanks the page.
- Motion confirms an action. It never explains one, and it never runs under reduced motion.
- The keyboard and screen-reader path is part of the design, not a pass at the end.

The severity gate is `better-interface`'s: no `HIGH` remains, and the escalation triggers are checked explicitly. Those include an unnamed control, a missing focus indicator, a pointer-only path, motion ignoring the preference, loss at 320px or 200%, a failing contrast pair, color-only meaning, an unrecoverable error and a destructive action with no distinct treatment.

Work order inside each view follows the skill order: accessibility, layout, writing, typography, color, polish. A polish detail never outranks a broken interaction.

### Design system

Primitives name values and are never used by components. Semantic tokens name roles and are the only tier components reference. All values below are measured against the surfaces they actually sit on.

| Role token | Value | Contrast |
| --- | --- | --- |
| `--color-bg-base` | `#0a0b0f` | page |
| `--color-bg-surface` | `#101218` | panels, table |
| `--color-bg-raised` | `#161923` | dialogs, tab track |
| `--color-bg-input` | `#171b24` | field fill, row hover |
| `--color-border-subtle` | `#1f232d` | dividers, table rules (1.19:1, decorative) |
| `--color-border-control` | `#626b83` | 3.24:1 on input fill, 3.52:1 on surface, 3.70:1 on base, 3.30:1 on raised |
| `--color-text` | `#e7eaf0` | 16.32:1 on base, 15.53:1 on surface, 14.55:1 on raised |
| `--color-text-muted` | `#a2aab8` | 8.41:1 on base, 8.00:1 on surface, 7.50:1 on raised |
| `--color-accent` | `#c084fc` | 7.44:1 on base, 7.08:1 on surface, 6.64:1 on raised |
| `--color-accent-fill` | `#c084fc` | 7.44:1 against base |
| `--color-on-accent` | `#14061f` | 7.39:1 on the accent fill |
| `--color-accent-soft` | `#292238` | accent text on it 5.76:1 |
| `--color-danger` | `#ff8f8f` | 8.54:1 on surface, 8.00:1 on raised |
| `--color-danger-fill` | `#dc2626` | white on it 4.83:1 |
| `--color-danger-soft` | `#312429` | danger text on it 6.77:1 |
| `--color-success` | `#5fd99a` | 10.59:1 on surface |
| `--color-success-soft` | `#1b2e2a` | success text on it 8.08:1 |
| `--color-warning` | `#f5b942` | 10.61:1 on surface |
| `--color-warning-soft` | `#30291e` | warning text on it 8.14:1 |
| `--color-focus` | `#b79cff` | 8.21:1 on surface, 8.63:1 on base |

Rules that come with the ramp:

- `--color-warning` earns its place because unscored rows render a "Pending" badge. Drop the token if the badge is dropped. Delete `--code-bg` and `--mono`.
- Soft fills are solid tokens, not alpha over a variable surface, so text on them has one measured value.
- `--color-border-control` reaches 3:1 against the field fill inside it as well as the panel outside it, which is why it is `#626b83` and not a softer grey.
- `--color-danger-fill` is used only for the confirm button in a destructive dialog. The accent never marks a destructive action.

Type scale, all sizes in `rem` with unitless line-height:

| Token | Size | Line-height | Weight | Use |
| --- | --- | --- | --- | --- |
| `--text-xs` | `0.75rem` (12) | `1.35` | 500 | badge labels only |
| `--text-sm` | `0.8125rem` (13) | `1.45` | 400 | metadata, helper text, table captions |
| `--text-base` | `0.875rem` (14) | `1.5` | 400 | controls, table cells, navigation |
| `--text-lg` | `1rem` (16) | `1.6` | 400 | card body, dialog copy, descriptions |
| `--text-xl` | `1.125rem` (18) | `1.35` | 600 | section headings (`h2`) |
| `--text-2xl` | `1.375rem` (22) | `1.25` | 600 | page title (`h1`) |

- Two weights only, `400` and `600`.
- Letter-spacing stays `0` because no text reaches the `24px` threshold. No uppercase micro-labels.
- Inputs run `--text-base` at 640px and up, `1rem` below it, so iOS Safari does not zoom on focus.
- `text-wrap: balance` on `h1`, `h2` and empty-state titles, `text-wrap: pretty` on descriptions, `overflow-wrap: break-word` on titles and URLs.
- Description paragraphs cap at `65ch`. `font-variant-numeric: tabular-nums` on prices, deltas, volumes, scores and similarity values.

Other tokens:

- Spacing `--space-1` to `--space-8`: `4, 8, 12, 16, 24, 32, 48, 64`. Group gaps stay at least twice the inner gap.
- Radius: `--radius-sm: 6px` for badges, `--radius-md: 10px` for buttons and fields, `--radius-lg: 14px` for panels, cards and dialogs. Where a surface nests inside another with an even inset, the outer radius equals the inner radius plus the inset.
- Motion: `--ease-out: cubic-bezier(0.2, 0, 0, 1)`, `--dur-fast: 150ms`, `--dur-base: 200ms`, `--dur-slow: 300ms`. Every movement, scale or blur sits inside `@media (prefers-reduced-motion: no-preference)`.
- Layout: `--shell-max: 1280px`, `--header-h: 56px` at every width, gutters `clamp(16px, 4vw, 32px)`, `html { scroll-padding-block-start: var(--header-h) }`.

### Shell

- Skip link as the first focusable element, pointing at `#main`, visible on focus.
- Sticky header at `--header-h`, full-width chrome with an inner container on the same `--shell-max` and gutter as the content, so every edge aligns.
- Brand is a mark plus "Gray Project News" at `--text-base` semibold. It is not a heading. Each view owns the only `h1`, so heading levels descend cleanly.
- Tabs are a real tablist: `role="tablist"`, one `role="tab"` per view with `aria-selected` and `aria-controls`, panels with `role="tabpanel"` and `aria-labelledby`, roving `tabIndex` with ArrowLeft, ArrowRight, Home and End. Visual style is a segmented control on a raised track. Selection is carried by surface plus weight, never by color alone.
- The active tab sets `document.title` to "News · Gray Project News" and so on.
- A panel mounts on first visit and stays mounted afterwards, hidden with the `hidden` attribute. Sort, filter and scroll position survive a tab switch, and the initial load still fetches only the visible view.
- The header keeps one row at every width, so the sticky offset never changes. Below 480px the brand text drops to its mark with the product name in `sr-only` text, and the three tab labels stay visible.
- `<main id="main">` keeps the page gutter and `padding-block: 32px 64px`.
- Always-mounted polite live region (`role="status"`) at app level for cross-view announcements. `role="alert"` only for urgent errors that are not tied to a field.

### Per-view structure

Every view shares one page header: `h1`, one-sentence description capped at `65ch`, a primary action where the view has one and a secondary "Manage data" action in News and Bets. One filled accent element per view.

News, `h1` "News", description "Worldwide coverage, ranked by how much each story could move a market."

- The two subtabs collapse into one page. Browsing is the page, and collection moves into a dialog, so "Collect New Data" no longer appears twice on screen.
- Primary action "Collect news" opens a native `<dialog>` with Query, Max records, Timespan and Sort, each with helper text for the GDELT syntax and defaults. Success shows counts and a "View news" action that closes the dialog and refreshes the list.
- Toolbar: a Sort by select limited to the values the API accepts (`seendate`, `disruptiveness_score`, `created_at`, `id`), a Direction select with "Ascending" above "Descending" and values corrected so each label produces the order it names, and a "Filter loaded rows" input. The input filters the already-fetched page by title, query or source and is labelled so it cannot be mistaken for a database search. It reports "12 of 100 loaded rows".
- Table at 760px and wider, sticky header under the app chrome: Score (meter plus number), Story (title link, hostname and country/language below it), Seen (`<time>` with a short absolute date), Actions.
- Cards below 760px: score and source on the top line, full title link, then country, language and query as muted metadata, then a labelled action.
- Row action is a ghost icon button with an accessible name that includes the row, such as `Find bets related to "…"`. While pending, the row shows "Matching…" in a live region. On success it shows "Seed created" with a "View in Matches" action. On failure it shows the reason and a retry beside the same row.
- Unscored rows show a "Pending" badge in the warning color with the word beside it, never a bare dash.
- Empty state: "No news stored yet" plus "Collect news". Filtered empty: "No loaded rows match "…"" plus "Clear filter".
- Error state: "Can't load news" with the cause and "Try again". Network failures name the API address.
- Pagination: "Showing 1–100 of 1,203" with an en dash, a page-size select of 50, 100 and 250 and Previous/Next. Clamp the range text and hide Previous on the first page.

Bets, `h1` "Bets", description "Polymarket markets, scored for how much they unsettle the status quo."

- Primary action "Collect bets" runs immediately, because it takes no parameters. Pending state, then a result summary in the status region.
- Filter bar: Active only and New only as toggle chips with `aria-pressed`, a Tag input and a "Minimum move" input in percentage points, both debounced 250ms. A "Clear filters" button appears only when a filter is set, next to a live count.
- Units, which is the biggest comprehension fix here: price and outcome prices are probabilities, so they render with `Intl.NumberFormat` percent style at one decimal. A move of `-0.002` renders as `-0.2%` with a down arrow. Volume and liquidity render compact as `$28.7M`. `status_quo_deviation` renders as a badge, "Unsettling" or "Status quo", with an icon. `emotionality_score` renders as a meter plus its number.
- Tags parse from the stored JSON string into chips. A malformed value degrades to no chips, never a raw string.
- Table at 760px and wider: Market (question link, tags, status badges), Price, 1D, 1W, 1M, Volume, Unrest, Ends, Actions. Cards below 760px keep the same fields stacked, with liquidity as extra metadata.
- Every delta carries a sign, an arrow and a color. Zero renders neutral with no arrow.
- Empty and error states mirror News. A filtered empty state names the filters and offers "Clear filters".

Matches, `h1` "Matches", description "News and markets that describe the same thing, linked by embedding similarity at 0.7 or higher."

- Layout is a two-pane grid at 1024px and wider, `320px minmax(0, 1fr)`, stacked below it.
- Seeds are a list of buttons, not a table. Each shows a source badge, the seed text and its creation date. Selection uses `aria-current="true"` plus a leading accent rule and a raised surface.
- A remove button sits beside each seed as a sibling control, not nested inside the selection button, and calls `DELETE /api/matches/{id}`. Re-matching the source row restores a seed, so removal deletes immediately and announces "Seed removed" rather than blocking on a confirm.
- Detail pane: `h2` "Related to <seed>" with `tabIndex={-1}`, a description naming the threshold, then up to five related cards. Each card carries a rank, a News or Bet badge, a title link and similarity as a meter plus a percentage in `tabular-nums`.
- Below 1024px, selecting a seed moves focus to the detail heading so the new content is not silent.
- Empty states: "No match seeds yet" with "Browse news" that switches to the News tab, plus "Nothing above the 0.7 threshold for this seed" with an explanation.

Data and state rules, applied in all views:

- One fetch effect per view, keyed on the query parameters, with an `AbortController`. Aborted requests are ignored, so a slow reply can never overwrite a newer one. The `setTimeout` calls and the duplicate effect both go.
- While refetching, keep the previous rows, dim the list and set `aria-busy="true"`. Announce the load once in the status region. No layout jump.
- Three distinct states per list: empty, error with retry and loaded. A fetch failure is never rendered as "no results".
- Debounced filter inputs enter the parameters only after 250ms.
- All request and error handling lives in one `api.js`. All display formatting lives in one `format.js`.

## Files to modify

| File | Change |
| --- | --- |
| `frontend/index.html` | Real title, meta description, `theme-color`, working favicon |
| `frontend/public/favicon.svg` | New, small mark in the accent color |
| `frontend/src/main.jsx` | Import the new style entry points |
| `frontend/src/index.css` | Removed, replaced by `src/styles/tokens.css` and `src/styles/base.css` |
| `frontend/src/App.css` | Removed, replaced by `src/styles/components.css` and `src/styles/views.css` |
| `frontend/src/App.jsx` | Shell, tablist, title sync, live region, cross-view navigation |
| `frontend/src/News.jsx` | Rewritten view |
| `frontend/src/Bets.jsx` | Rewritten view |
| `frontend/src/Matches.jsx` | Rewritten view |
| `frontend/src/styles/tokens.css` | New: primitives, semantic tokens, type scale, spacing, motion |
| `frontend/src/styles/base.css` | New: root, reset, focus-visible, skip link, selection, reduced motion, sr-only |
| `frontend/src/styles/components.css` | New: buttons, fields, badges, meter, cards, table, tabs, dialogs, states |
| `frontend/src/styles/views.css` | New: shell and per-view layout |
| `frontend/src/components/Icon.jsx` | New: inline SVG set, `currentColor`, 1.5px stroke, 16 or 20px |
| `frontend/src/components/Button.jsx` | New: `primary`, `secondary`, `ghost`, `danger`, `icon` variants |
| `frontend/src/components/Tabs.jsx` | New: tablist with roving tabindex and key map |
| `frontend/src/components/Field.jsx` | New: label, hint and error wiring with `aria-describedby` and `aria-invalid` |
| `frontend/src/components/Dialog.jsx` | New: native `<dialog>` with `showModal`, Escape, focus restore |
| `frontend/src/components/Feedback.jsx` | New: inline banner plus the stable live region |
| `frontend/src/components/EmptyState.jsx` | New: orientation plus one next action |
| `frontend/src/components/ErrorState.jsx` | New: what failed, why, retry |
| `frontend/src/components/Skeleton.jsx` | New: static row and card placeholders |
| `frontend/src/components/Pagination.jsx` | New: range text, page size, Previous/Next |
| `frontend/src/lib/api.js` | New: `apiFetch`, FastAPI detail extraction, network message |
| `frontend/src/lib/format.js` | New: percent, delta, compact currency, dates, tags, hostname, score |
| `frontend/src/lib/hooks.js` | New: `useMediaQuery`, `useDebouncedValue` |
| `README.md` | Update section 2 and section 9 to describe the new frontend structure |

Not modified: `backend/`, `skills/`, `AGENTS.md`, `docker-compose.yaml`.

## Reuse

- `useMediaQuery('(min-width: 760px)')` is the only place the table/card breakpoint exists. CSS for cards carries no breakpoint, so the two cannot drift.
- The existing endpoints and parameters stay exactly as they are: `GET /api/news` (`backend/main.py:98`), `GET /api/bets` (`backend/main.py:180`), `POST /api/news/collect`, `POST /api/bets/collect`, `DELETE /api/news` (`backend/main.py:142`), `DELETE /api/bets` (`backend/main.py:310`), `POST /api/matches` (`backend/main.py:383`), `GET /api/matches` (`backend/main.py:476`), `DELETE /api/matches/{id}` (`backend/main.py:518`), `GET /api/matches/{id}/related` (`backend/main.py:536`).
- Sort and direction option lists must match the backend enums exactly. News accepts `seendate`, `created_at`, `id` and `disruptiveness_score`. Bets accepts `collected_at`, `volume`, the three changes, `emotionality_score`, `status_quo_deviation`, `end_date` and `question`. Collect sort accepts `datedesc`, `dateasc` and `hybridrel`.
- `limit` is capped at 1000 by the API, so the page-size options stay at 50, 100 and 250.
- Response fields the UI can use as they are: `url` (hostname), `tags` (JSON string to parse), `source_type` and `source_id` on seeds, `disruptiveness_score`, `emotionality_score`, `status_quo_deviation`, `outcome_prices`.
- The error-shape parsing in `src/News.jsx:57-90`, `src/News.jsx:108-136`, `src/Bets.jsx:61-79` and `src/Bets.jsx:110-130` moves into `api.js` unchanged in behavior.
- The contrast measurements already run for this plan become the verification step. No eyeballing.

## Steps

Phase 1, tokens and base

- [x] Write `styles/tokens.css` with the primitives and the semantic table above.
- [x] Write `styles/base.css`: root type, reset, `:focus-visible` ring at 2px offset, `::selection` on accent with `--color-on-accent`, skip link, `sr-only`, reduced-motion wrapper, `scroll-padding-block-start`.
- [x] Delete `index.css` and `App.css`, wire `main.jsx` to the new sheets.
- [x] Run the contrast check over every declared pair and confirm each measured value in the table above.

Phase 2, primitives

- [x] `Icon.jsx` with the glyph set: collect, trash, external, target, arrow-up, arrow-down, check, alert, close, chevron-left, chevron-right, search, info, news, chart.
- [x] `Button.jsx` with native `<button>`, `disabled` for unavailable states, `aria-label` required on icon-only use, press scale `0.96` over `150ms` gated by reduced motion, hover styles inside `@media (hover: hover)`.
- [x] `Tabs.jsx` with the tablist pattern and key map.
- [x] `Field.jsx`, `Dialog.jsx`, `Feedback.jsx`, `EmptyState.jsx`, `ErrorState.jsx`, `Skeleton.jsx`, `Pagination.jsx`.
- [x] `lib/api.js`, `lib/format.js`, `lib/hooks.js`.

Phase 3, shell

- [x] Rebuild `App.jsx`: skip link, sticky header, brand, tablist, panels, `document.title` sync, app-level live region, `onNavigate` for cross-view jumps.
- [x] Fix `index.html` title, description, `theme-color` and favicon. Add `public/favicon.svg`.

Phase 4, News

- [x] Page header, collect dialog, toolbar with corrected Direction values ("Ascending" first, `value="asc"`; "Descending" second, `value="desc"`; default `desc` now displays "Descending").
- [x] Single abortable fetch effect on `orderBy`, `orderDir`, `offset`, `limit`. Remove both `setTimeout` calls.
- [x] Table and card rendering from one record shape, score meter, pending badge, row action state machine.
- [x] Filter-loaded-rows input with debounce and an explicit "loaded rows" label.
- [x] Pagination with range clamping and page size.
- [x] Manage-data dialog: bound labels, helper text naming `seendate`, a second confirm step naming the range and stating that it cannot be undone, danger button, deleted count in the status region.
- [x] Loading, empty, filtered empty and error states.

Phase 5, Bets

- [x] Page header with a direct collect action and pending state.
- [x] Filter bar with toggle chips, debounced tag and minimum move in percentage points (converted to the API's 0 to 1 scale before the request), clear-all, live count.
- [x] Probability, delta, compact currency, tag chips, status quo badge and unrest meter formatters.
- [x] Table and card rendering, row action, pagination, manage-data dialog mirroring News with `collected_at` named.
- [x] Loading, empty, filtered empty and error states.

Phase 6, Matches

- [x] Two-pane layout, seed list with source badge, `aria-current`, remove action calling the delete endpoint, live announcement.
- [x] Detail pane with focusable heading, related cards with rank and similarity meter, threshold explanation.
- [x] Cross-view "Browse news" action from the empty state.
- [x] Loading, empty and error states.

Phase 7, resilience and reach

- [x] Verify each list keeps previous rows during refetch and sets `aria-busy`.
- [x] Walk every state: 0 rows, 500 rows, backend down, slow API, malformed tags, null scores, missing URL.
- [x] 320px, 480px, 760px, 1024px, 1440px and 200% zoom. No horizontal scroll at 320 and no clipped action.
- [x] Logical properties throughout the new CSS. Physical `left` and `right` only where geometry is physical.
- [x] Forced-colors check on buttons, fields and the confirm dialog.
- [x] Keyboard walk: skip link, tablist arrows, toolbar, filters, row actions, dialog Escape and focus return, detail focus move.

Phase 8, polish

- [x] Press scale, hover fills, dialog entry and the pending spinner, each named in `transition-property` and gated by reduced motion.
- [x] Sticky table header offset by `--header-h`, row hover gated by pointer capability, `-webkit-tap-highlight-color: transparent` on buttons that draw their own pressed state.
- [x] Optional: after a successful match, the status message links to Matches with the new seed selected.

Phase 9, wrap-up

- [x] `npm run lint` and `npm run build`.
- [x] Update `README.md` sections 2 and 9.

## Verification

Build and lint:

- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `cd frontend && npm run dev`, with `docker compose up -d` and `uvicorn main:app --reload` for data-bearing states.

Contrast, computed from `styles/tokens.css` rather than estimated. Every pair must meet its threshold:

- Text on base, surface, raised and input: `--color-text` at least 4.5:1, `--color-text-muted` at least 4.5:1.
- Accent text on base, surface and raised, plus `--color-on-accent` on `--color-accent-fill`, at least 4.5:1.
- Status text on surface and on its own soft fill: danger, success and warning, at least 4.5:1.
- `--color-border-control` against the field fill, base, surface and raised, at least 3:1.
- Text and muted text on the input fill, at least 4.5:1.
- `--color-focus` against base and surface, at least 3:1.
- White on `--color-danger-fill`, at least 4.5:1.

Interaction and content checks:

- The Direction select shows "Descending" on first load and produces descending order. Choosing "Ascending" produces ascending order, with one request per change.
- A price of `0.106` renders "10.6%". A 1D change of `-0.002` renders "-0.2%" with a down arrow. Volume renders compact, tags render as chips, a null score renders "Pending".
- Stopping the API renders an error state with a retry, never "No news entries found."
- An empty database renders an empty state with a next action.
- A sort change while a request is in flight leaves the newest result on screen.
- Deleting a range names the range in the confirm step and reports the deleted count.
- Removing a seed updates the list and announces it.

Accessibility checks:

- Tab order reaches skip link, tablist, toolbar, filters, table actions and dialogs in DOM order. No positive `tabindex` anywhere.
- Arrow keys move between tabs and only the selected tab is in the tab sequence.
- Every icon-only control announces an action and an object.
- Success, error and loading messages are announced through the always-mounted live region.
- Dialog focus enters on open, Escape closes it and focus returns to the trigger.
- At 200% zoom and 320px width, nothing clips, overlaps or needs horizontal scrolling.
- Grep the finished CSS for `transition: all`, `outline: none`, `tabindex="1"` and `overflow-x` on a page container. None should remain.
- Reduced-motion emulation removes every transform and blur and leaves instant or opacity-only transitions.
- axe DevTools reports no critical or serious issue on each view.

Screen reader smoke test, if available:

- The tablist announces each tab with its selected state.
- A pending row action announces its result.
- A confirm dialog announces its title and both buttons.

## Out of scope

- Any backend change, including a delete-preview count and server-side search. The confirm step states scope without a count. The filter searches only loaded rows and says so.
- A light theme or a theme switch.
- Table column sorting on header click. Sorting stays in the toolbar, which keeps one control for one job.
- Changes under `skills/` or to `AGENTS.md`.
- Persisting tab, sort or filter state in the URL.
- Pagination for the seed list, which the backend returns unpaginated. It also ships 384 floats per seed, which the UI ignores.
