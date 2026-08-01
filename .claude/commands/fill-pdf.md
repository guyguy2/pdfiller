Fill the PDF at the given path using the PDFiller library.

If anything below is ambiguous or underspecified for the PDF at hand, stop and ask me rather than guessing.

Follow the workflow described in CLAUDE.md:
0. Resolve the PDF path:
   - If $ARGUMENTS contains a path to a specific file, use it.
   - Otherwise (empty, or references "inbox"), look in the project's `inbox/` directory for PDFs (ignore `inbox/filled/`).
     - Exactly one PDF found: use it.
     - Multiple PDFs found: list them and ask me which one to fill.
     - None found: tell me and stop.
1. Open and inspect the PDF (fillable vs non-fillable)
2. Load user defaults from ~/.pdfiller/defaults.json
3. Match fields to defaults, identify what's missing:
   - Fillable PDFs: use `match_field_to_defaults` against each field name.
   - Non-fillable PDFs: there is no automatic matcher. For each blank in `get_page_layout()`'s blocks, infer the label preceding it (e.g. "Name:", "Email:", "Cell #:") and match it against the flattened defaults the same way you would a field name. Ask me if a label is too ambiguous to match confidently.
4. Show me the plan - what will be auto-filled and what you need from me
5. Flag anything that isn't a plain text fill and ask me how to handle it before filling:
   - Signature fields/areas - ask if I want to place a signature image (do NOT auto-sign)
   - Checkbox glyphs (e.g. "□ Owner □ Renter") or "circle applicable" style choices on non-fillable PDFs - ask which option applies and confirm how it'll be marked (e.g. an "X" over the box) before inserting anything
   - For each field with no default match (missing), prompt me individually for that field and offer to skip it or provide a value - don't leave it silently blank or guess a value
6. Fill the form with my answers and save as <name>_filled.pdf
7. Ask if any new values should be remembered for next time

PDF path: $ARGUMENTS
