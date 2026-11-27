# Storycraft for Claude Code

Open Claude Code in your manuscript repository and run `/storycraft:book-status`. Use `/storycraft:storycraft-workspace` to select a book or resume a project. Storycraft reads the book's own instructions, chapters, Wiki and saved editorial reports. Use `/mcp` to check the `plugin:storycraft:storycraft-state` connection.

The bundled scripts use Python 3.10 or newer on macOS, Linux or WSL. The launcher searches your PATH and the standard macOS Homebrew locations. Set `STORYCRAFT_PYTHON` in Claude's environment to select a specific interpreter. The package includes PyYAML for reading promise ledgers. DOCX and EPUB exports also use Pandoc, and PDF exports require a configured PDF engine.

Claude Code and the ChatGPT desktop plugin can use the same saved chapter reviews. Both check the manuscript inputs and the content of the editorial rules that produced the review.
