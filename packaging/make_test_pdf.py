"""Write the made-up PDF that the smoke test and the app test ask questions about.

Run from engine/: uv run python ../packaging/make_test_pdf.py <output file>
"""
from __future__ import annotations

import sys

from fpdf import FPDF

PAGES = [
    "Backups run nightly at 02:00 and are kept for 14 days. Restore from the Maintenance menu.",
    "The PX-400 label printer connects by USB. Firmware 2.1.7 fixes the buffer overflow.",
    "The licence renews every year. To cancel, contact sales at least 30 days before it expires.",
]

pdf = FPDF()
pdf.set_font("helvetica", size=11)
for text in PAGES:
    pdf.add_page()
    pdf.multi_cell(0, 6, text)
pdf.output(sys.argv[1])
