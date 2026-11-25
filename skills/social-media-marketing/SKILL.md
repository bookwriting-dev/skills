---
name: social-media-marketing
description: "Plan and write Facebook, Instagram, and TikTok book marketing: organic-first launch campaigns, content calendars, captions, video scripts, hashtags, and optional paid ads. Use for 'social media plan', 'launch campaign', 'BookTok', 'TikTok script', 'Instagram Reels', 'promote my book'. Use book-packaging for blurbs or cover briefs."
metadata:
  author: Storycraft Skills
  version: "1.0.2"
  category: cross-cutting
  output-format: markdown
---

# Social Media Marketing

Turns a book's genre, audience, tropes, and themes into a social campaign for Facebook, Instagram, and TikTok. Works for fiction and non-fiction. The default is **organic only**; paid ads are an opt-in layer.

## Step 1: Load Context

Search the project for these, and read whatever exists:

- `**/Wiki/Style/genre.md` — genre, subgenre, tropes, tone. (Fiction)
- `**/Wiki/Style/audience.md` — target reader, content boundaries.
- `**/Wiki/Story/synopsis.md` or `**/Wiki/Story/Book-N/synopsis.md` — premise, hook, stakes.
- `**/Wiki/Concept/` or the non-fiction concept and audience files — thesis, reader promise, transformation. (Non-fiction)
- `**/Wiki/Story/Book-N/packaging.md` — blurb, logline, comp titles, keywords. Reuse these; do not reinvent the pitch.
- `**/Wiki/Marketing/` — any earlier strategy or calendar, so a new run extends it instead of replacing it.

If there is no genre or audience file, tell the user: "No genre or audience profile found. Run `fiction-genre` and `fiction-audience` (or `nonfiction-concept` and `nonfiction-audience`) first, or give me the genre, target reader, and comp titles directly." Do not stop if the user supplies them.

If there is no packaging file, suggest `book-packaging` for the blurb and comps, then continue with what you have.

## Step 2: Gather Campaign Inputs

Ask only for what the files do not already answer, using the host's normal question mechanism:

1. **Mode:** Launch campaign, Ongoing content, or Both.
2. **Release date** (for launch mode) and format: ebook, paperback, audiobook, wide, or Kindle Unlimited.
3. **Platforms:** Facebook, Instagram, TikTok. Default is all three.
4. **Capacity:** posts per week the author can sustain, and whether the author is willing to be on camera.
5. **Existing presence:** current platforms, follower counts, and email list size.
6. **Paid ads:** Off (default), or On, with a monthly budget and the platform to start on.

## Step 3: Build the Strategy

Write `Wiki/Marketing/strategy.md`, or `Wiki/Marketing/Book-N/strategy.md` for a series. Cover:

- **Positioning:** one-line hook, 3 comp titles, and the reader promise, taken from the packaging file when it exists.
- **Reader profile:** who they are and what they scroll for. Use `fiction-audience` or `nonfiction-audience` output.
- **Content pillars (3–5):** recurring content types mapped to the book. Fiction examples: trope hooks, character moments, aesthetic and mood boards, behind-the-scenes, reader reactions. Non-fiction examples: the core idea in one tip, myth-busting, a story from the book, a question the book answers.
- **Platform roles:**
  - **TikTok:** discovery. Trope and hook-led short video, BookTok and niche communities.
  - **Instagram:** brand and community. Reels for reach, carousels and Stories for depth.
  - **Facebook:** conversion and community. Reader groups, events, link posts, and ads (if enabled).
- **Funnel:** social → email list or retailer link. Name the single call to action per phase.
- **Metrics:** what to track per platform and what counts as a signal. See [references/measurement.md](references/measurement.md).

Read the platform reference for each selected platform before writing any platform-specific content:

- [references/tiktok.md](references/tiktok.md)
- [references/instagram.md](references/instagram.md)
- [references/facebook.md](references/facebook.md)

## Step 4: Build the Calendar

Write `Wiki/Marketing/calendar.md` (or `Book-N/calendar.md`). Use the phase structure in [references/launch-phases.md](references/launch-phases.md):

- **Launch mode:** pre-launch (4 weeks out), launch week, post-launch (first 4 weeks).
- **Ongoing mode:** a rolling 4-week plan on the content pillars, with a repeating weekly rhythm sized to the author's capacity. Do not schedule more than the author said they can sustain.

The calendar is a table: date, platform, pillar, format, hook, call to action, status.

## Step 5: Generate Content

For each calendar slot the user wants written, produce the asset in `Wiki/Marketing/content/` (or `Book-N/content/`), grouped by week:

- **TikTok / Reels scripts:** hook (first 1–3 seconds), beats, on-screen text, audio or format note, caption, hashtags.
- **Carousels:** slide-by-slide copy, one idea per slide, a final-slide call to action.
- **Facebook posts:** post copy, group-safe variant, and event or giveaway copy where relevant.
- **Captions:** match the book's voice. Fiction captions should sound like the genre; non-fiction captions should lead with the reader's problem.
- **Hashtags and keywords:** a small mixed set per post (niche, genre, broad). See the platform reference for sizing.

**Hard rules:**
- **No spoilers** beyond what the blurb already reveals. For a series, never give away earlier-book twists in later-book content, and check `Wiki/` canon or `series-continuity` if unsure.
- **Respect audience content boundaries.** Content for a YA book must stay inside the `audience.md` limits, and every hook must be platform-safe.
- **Quote the book carefully.** Pull lines only from approved, final prose, not drafts that may still change.
- **Non-fiction claims must be defensible.** Do not state a statistic or claim in a post that `nonfiction-factcheck` or the research vault does not support.
- **Disclose when required.** Giveaways, paid partnerships, and ARC or advance-copy posts need the platform's disclosure language and a legal-eligibility note. Never invent reviews, testimonials, or follower numbers.
- **Adhere to platform specs & safe zones.** Follow the verified dimensions, safe zones, character limits, and truncation thresholds detailed in the platform reference files (`tiktok.md`, `instagram.md`, `facebook.md`, `paid-ads.md`) so text and hooks are never cropped or blocked by UI overlays.

## Step 6: Optional Paid Ads Layer

Skip this step entirely unless the user chose paid ads. If they did, read [references/paid-ads.md](references/paid-ads.md) and write `Wiki/Marketing/ads-plan.md` covering:

- Objective and the single metric that decides success
- Budget split and test structure (audiences × creatives, small and cheap first)
- 3–5 ad creatives with primary text, headline, and call to action, each tied to a content pillar or an organic post that already performed
- Audience definitions (interests, lookalikes, retargeting) matched to the reader profile
- Rules for scaling, pausing, and stopping, based on the measurement reference
- Compliance checks: special ad category flags, content policy, and ad-copy claims

Paid ads amplify organic content that already works. Do not recommend ad spend before there is at least one creative worth amplifying.

## Step 7: Present and Confirm

Show the strategy and calendar to the user and ask: "What should I change?" Apply revisions in place. When approved, offer the next step: write content for the next two weeks, build the ads plan (if not done), or run a retrospective on what the numbers show.

## Retrospective Mode

When the user shares results (views, saves, clicks, sales), read [references/measurement.md](references/measurement.md), compare against the strategy, and write `Wiki/Marketing/retro-YYYY-MM-DD.md`: what worked, what didn't, what to repeat, what to cut, and the next calendar adjustments.

## Output

```
Wiki/Marketing/
├── strategy.md
├── calendar.md
├── ads-plan.md          (only if paid ads enabled)
├── content/
│   └── week-NN.md
└── retro-YYYY-MM-DD.md
```

For a series, use `Wiki/Marketing/Book-N/` per book, with a shared `Wiki/Marketing/series-strategy.md` if the user wants one.
