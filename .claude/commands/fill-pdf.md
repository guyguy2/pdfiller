Fill the PDF at the given path using the PDFiller library.

Follow the workflow described in CLAUDE.md:
1. Open and inspect the PDF (fillable vs non-fillable)
2. Load user defaults from ~/.pdfiller/defaults.json
3. Match fields to defaults, identify what's missing
4. Show me the plan - what will be auto-filled and what you need from me
5. If a signature field is detected, ask if I want to place a signature image (do NOT auto-sign)
6. Fill the form with my answers and save as <name>_filled.pdf
7. Ask if any new values should be remembered for next time

PDF path: $ARGUMENTS
