# Round 1A – Structured Outline Extraction

## 🚀 Challenge Overview

Extract a **structured outline** from any PDF document. This includes:
- Title
- Headings (H1, H2, H3)
- Page numbers

Output format:
json
{
  "title": "Understanding AI",
  "outline": [
    { "level": "H1", "text": "Introduction", "page": 1 },
    { "level": "H2", "text": "What is AI?", "page": 2 },
    { "level": "H3", "text": "History of AI", "page": 3 }
  ]
}
🧠 Approach
We developed a robust pipeline that uses both visual and semantic cues to extract headings from PDFs. The process includes:

Text Extraction: Extract raw text and layout metadata using PyMuPDF (fitz).

Candidate Identification: Use heuristics (title casing, font size, numbering) and NER (spaCy) to propose heading candidates.

Matching: Fuzzy match candidates against extracted spans with font/style metadata.

Filtering: Remove repeated headers/footers using positional clustering.

Merging: Merge adjacent heading spans with same styling.

Scoring & Ranking: Compute importance score using:

Font size

Font weight

Box enclosure (e.g., if it's inside a bounding box)

Tagging: Top-scored spans are tagged as H1/H2/H3 accordingly.

Output: Structured JSON is generated with proper hierarchy.

🧱 Tech Stack
Python 3.11

PyMuPDF

spaCy (en_core_web_sm)

🐳 Docker Instructions
🔨 Build
bash
Copy
Edit
docker build --platform linux/amd64 -t headingextractor:latest .
▶️ Run
bash
Copy
Edit
docker run --rm \
  -v "$(pwd)/input:/app/input" \
  -v "$(pwd)/output:/app/output" \
  --network none \
  headingextractor:latest
The container will:

Read all PDFs from /app/input

Write JSON outlines to /app/output

✅ Constraints Satisfied
Constraint	Status
≤ 10s for 50-page PDF	✅
CPU only	✅
Model size ≤ 200MB	✅
Offline (no network)	✅
Output JSON format	✅

📁 Directory Structure
css
Copy
Edit
.
├── round1A.py
├── main.py
├── requirements.txt
├── Dockerfile
├── input/
└── output/
📌 Notes
Works for a wide range of document layouts.

No hardcoded logic or file-specific assumptions.
