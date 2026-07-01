# Dashboard Guide

This is the landing page for your generated documentation.

Run the pipeline (`make capture && make draft && make api`) and one page per
screen will appear in the navigation, alongside an auto-generated API Reference.

Edit `docs/index.md` to introduce your product. The per-screen pages
(`docs/NNN-*.md`) and the screenshots (`docs/img/`) are generated and gitignored,
so they never get committed — regenerate them anytime from the live app.

!!! note
    Screen pages are drafted by an LLM from real screenshots and DOM labels, then
    reviewed before publishing. The API Reference is generated directly from the
    app's OpenAPI spec.
