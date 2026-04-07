# public-profile

Shareable per-user public profile page — the main thing users will link
to from Twitter/LinkedIn/bios.

No auth required to view. Shows curated reputation data only (not full
prediction history by default).

**Stack TBD** — should support OG image generation for rich link previews.

## Key pages / components

- `/u/:username` — profile page: badges, summary stats, linked platforms
- OG image endpoint — generates a badge card image for social sharing
- Embed widget — small iframe-embeddable badge card (stretch goal)
