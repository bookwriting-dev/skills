# Instagram (Reels, Carousels, Stories, and Grid)

## Technical Specifications

### Formats, Dimensions & Aspect Ratios

| Asset Type | Aspect Ratio | Optimal Resolution | Maximum Length / Size |
|---|---|---|---|
| **Reels** | 9:16 vertical | 1080 × 1920 px (or 1440 × 2560 px high-res) | Up to 90s (in-app recording); up to 15 min (uploaded video file). File max: 4 GB. |
| **Carousels** | 4:5 portrait *(recommended)* or 1:1 square | 1080 × 1350 px (4:5) / 1080 × 1080 px (1:1) | **Up to 20 slides** (photos, videos up to 60s each, or mixed). |
| **Stories** | 9:16 vertical | 1080 × 1920 px | Up to 60s per video clip. File max: 4 GB. |
| **Feed Images** | 4:5 portrait *(recommended)* or 1:1 square | 1080 × 1350 px (4:5) / 1080 × 1080 px (1:1) | JPG, PNG up to 30 MB. |

*Crucial Carousel Rule:* **Slide 1 locks the aspect ratio for all subsequent slides**. If slide 1 is 4:5, Instagram automatically forces/crops every slide in the carousel to 4:5. Always render all slides at the exact same dimension.

### Safe Zones & Layout Margins

#### Reels Safe Zones (1080 × 1920 Canvas)
Meta overlays header navigation, caption text, creator details, audio tags, and right-hand engagement buttons:
- **Top No-Go Zone:** Keep text, titles, and faces at least **220–270 px** below the top edge.
- **Bottom No-Go Zone:** Keep subtitles, book covers, and CTAs at least **420–450 px** above the bottom edge (protects against the expanding caption, audio track marquee, and comment bar).
- **Right Margin:** Leave **100–130 px** clear on the right edge (action bar: like, comment, share, save).
- **Left Margin:** Leave **60 px** of padding on the left edge.
- **Central Action Window:** Design key visuals and subtitles strictly within the central **$1010 \times 1280$ px** box.
- **Profile Grid "Square-Proofing":** When a Reel appears on your profile grid, it renders as a **3:4 crop (1080 × 1440 px)** or **1:1 center crop (1080 × 1080 px)**. The top and bottom 240+ pixels are cut off on profile pages. Ensure your cover frame or title sits within the center 1080 × 1080 box.

#### Carousel Safe Zones (1080 × 1350 Canvas)
- **Edge Padding:** Keep all critical text, pull quotes, and logos **60–80 px** inside all outer borders.
- **Top UI Area:** Top 60–80 px is partially obscured by the creator avatar and handle bar.
- **Bottom UI Area:** Bottom 80–120 px is covered by the carousel pagination dots, like/bookmark icons, and caption preview.
- **Slide 1 Grid Crop:** 4:5 carousels appear cropped to a center square (1:1) or 3:4 on your profile grid. Keep the hook headline centered on Slide 1 so it isn't clipped in your grid layout.

#### Stories Safe Zones (1080 × 1920 Canvas)
- Leave **250 px clear at the top** (handle, story progress bar) and **250 px clear at the bottom** (message box, sticker reactions, link sticker tap zones).

### Captions, Truncation & Hashtags
- **Caption Character Limit:** Up to **2,200 characters**.
- **Mobile Feed Truncation:** Truncates to "more" after roughly **125 characters** (1–2 lines). The opening hook must deliver immediate value or intrigue before the fold.
- **Hashtags:** Up to 30 allowed, but Instagram's official creator guidance recommends **3–5 targeted hashtags**. Place them at the end of the caption or after a clean line break.
- **Links:** Captions cannot contain clickable URLs. Use Story **Link Stickers**, direct message keyword automations, or a clean link-in-bio hub.

---

## Content Formats for Authors

| Format | Strategic Role | Author Execution |
|---|---|---|
| **Reels** | Algorithm discovery & non-follower reach | Repurpose TikTok trope hooks, reading reactions, dramatic quote readings (export cleanly without TikTok watermarks). |
| **Carousels** | High saves, shares, and algorithmic trust | "5 tropes in this book," character dossiers, multi-slide sample chapters, non-fiction 3-step frameworks. |
| **Stories** | High-intent fan nurture & launch conversion | Daily informal updates, poll stickers ("Which cover variant?"), countdown stickers for launch day, direct link stickers to pre-orders. |
| **Aesthetic Grid Posts** | Visual storefront & genre comp alignment | Clean cover reveals, typography quote cards matching the book's interior style, paperback unboxings. |

---

## Bookstagram Community & Compliance
- **Direct Engagement:** Comment on and repost Bookstagram reviewers and book clubs in your subgenre. Provide ARC (Advance Reader Copy) files to reviewers with matching reader tastes.
- **Asset Rights:** Ensure all artwork, cover mockups, typography fonts, and background imagery are licensed for commercial distribution.
- **No Purchased Engagement:** Engagement pods, follow-unfollow loops, and bought followers suppress organic Reel reach and distort algorithm targeting.
- **Content Policy:** Adult-rated or high-heat romance/thriller fiction must keep post imagery and caption wording safe for general mobile feeds to avoid shadowbanning.
