---
name: storycraft-workspace
description: Set up or resume Storycraft in the current local manuscript workspace. Use when the author selects Storycraft or asks it to identify the active book, show production status, run chapter preflight, or audit setups and payoffs.
---

# Storycraft workspace

- Use the current or explicitly selected project root and its `AGENTS.md`. Read the book's own canon, voice, and review guidance. Ask for the project or book only if the workspace and the request leave the selection ambiguous.
- For status, use `storycraft_dashboard`. For chapter preflight, use `storycraft_chapter_preflight` with the chapter selector. For setups and payoffs, use `storycraft_promises`. Pass the absolute project root and selected book on each call. Report the book and Storycraft version with the result.
- Load the matching bundled skill for a full editorial workflow. Use bundled paths for shared scripts and references. In a migrated project, references to `.agents/skills` in older project instructions identify the corresponding files in this plugin. If both installations are present, use the project's declared installation choice. If a project still pins or customizes its library, use its local workflow unless the author explicitly chooses the shared plugin for the task.
- Keep status, preflight, and promise audits read-only. Save reports or change records only when the author requests that operation. If MCP is unavailable, use the plugin's `run-python` launcher to run the equivalent bundled script with the same project root. Report the fallback.
