# Assistant Rendering Dependencies

Pinned browser distributions are served locally so the chat does not depend on a CDN.

- Marked 9.1.6: https://cdn.jsdelivr.net/npm/marked@9.1.6/marked.min.js
  License: Marked-LICENSE.md (MIT).
- DOMPurify 3.4.15: https://cdn.jsdelivr.net/npm/dompurify@3.4.15/dist/purify.min.js
  License: DOMPurify-LICENSE (Apache-2.0 or MPL-2.0).
- Bootstrap Icons 1.13.1 font: https://cdn.jsdelivr.net/npm/bootstrap-icons@1.13.1/font/fonts/bootstrap-icons.woff2
  License: Bootstrap-Icons-LICENSE (MIT).

All model Markdown must pass through DOMPurify with the template's restricted tag
and attribute list. Only same-origin dashboard and ERP links remain clickable.
When updating either library, rerun chat rendering and XSS regression checks.
