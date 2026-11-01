# __SERIES_TITLE__ — Book __BOOK_NUM__ board

Production board for Book __BOOK_NUM__. The `kanban-board` skill regenerates
this file from the outline, scene plans, chapter drafts, and gate reports —
the board is a view, never the source of truth. Say "show the board" to
refresh it. Columns:

## Backlog

- (chapters in the outline with no scene plan yet)

## Ready

- (scene plan done, draft not started)

## Drafting

- (draft exists, no gate/review report yet)

## Review

- (gate or review report filed, verdict not yet PASS)

## Done

- (gate verdict PASS)

Evidence: Done requires current configured checks and resolved blocking work. Legacy or stale PASS remains Review.
