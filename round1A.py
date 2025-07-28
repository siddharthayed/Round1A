import fitz  # PyMuPDF
import spacy
import os
import json
import re
from typing import List, Dict, Tuple
from difflib import SequenceMatcher
from collections import defaultdict

nlp = spacy.load("en_core_web_sm")


def normalize_text(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text).lower().strip()


def fuzzy_match(a: str, b: str, threshold: float = 0.75) -> bool:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio() > threshold


def is_heading_like(line: str) -> bool:
    return len(line) < 150 and (
        line.isupper() or line.istitle() or re.match(r"^\d+[\.\)]?\s+\w+", line)
    )


def extract_raw_text_per_page(pdf_path: str) -> List[str]:
    doc = fitz.open(pdf_path)
    return [page.get_text("text") for page in doc]


def find_heading_candidates(text: str) -> List[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    candidates = [line for line in lines if is_heading_like(line)]

    doc = nlp("\n".join(lines))
    for ent in doc.ents:
        if ent.label_ in {"ORG", "EVENT", "LAW", "WORK_OF_ART"} and ent.text not in candidates:
            candidates.append(ent.text.strip())

    return list(set(candidates))


def is_inside_box(span_bbox: Tuple[float], block_bbox: Tuple[float], tolerance: float = 2.0) -> bool:
    x0, y0, x1, y1 = span_bbox
    bx0, by0, bx1, by1 = block_bbox
    return (bx0 - tolerance <= x0 <= bx1 + tolerance and
            by0 - tolerance <= y0 <= by1 + tolerance and
            bx0 - tolerance <= x1 <= bx1 + tolerance and
            by0 - tolerance <= y1 <= by1 + tolerance)


def match_headings_in_pdf(pdf_path: str, headings: List[str]) -> List[Dict]:
    doc = fitz.open(pdf_path)
    filename = os.path.basename(pdf_path)
    matched_spans = []

    for page_num, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue
            block_bbox = block.get("bbox", None)

            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue

                    for heading in headings:
                        if fuzzy_match(text, heading):
                            weight = 700 if "bold" in span["font"].lower() else 400
                            size = round(span["size"], 2)
                            in_box = block_bbox and is_inside_box(span["bbox"], block_bbox)

                            matched_spans.append({
                                "document": filename,
                                "page": page_num,
                                "text": text,
                                "font_size": size,
                                "font_weight": weight,
                                "font_color": span["color"],
                                "font_family": span["font"],
                                "coordinates": span["bbox"],
                                "in_box": in_box
                            })
                            break
    return matched_spans
def remove_repeated_text(spans: List[Dict], total_pages: int, threshold: float = 0.8, position_tolerance: float = 10.0) -> List[Dict]:
    from collections import defaultdict
    import statistics

    text_positions = defaultdict(list)
    text_pages = defaultdict(set)

    for span in spans:
        norm_text = normalize_text(span["text"])
        x0, y0, x1, y1 = span["coordinates"]
        center_x = (x0 + x1) / 2
        center_y = (y0 + y1) / 2
        text_positions[norm_text].append((center_x, center_y))
        text_pages[norm_text].add(span["page"])

    blacklist = set()

    for text, positions in text_positions.items():
        page_count = len(text_pages[text])
        if page_count > 2 and page_count / total_pages >= threshold:
            # Check if positions are clustered
            xs = [pos[0] for pos in positions]
            ys = [pos[1] for pos in positions]
            x_std = statistics.pstdev(xs)
            y_std = statistics.pstdev(ys)

            if x_std < position_tolerance and y_std < position_tolerance:
                blacklist.add(text)

    print("🧹 Removed repeated text in same position across pages:")
    for text in blacklist:
        print("   •", text)

    filtered_spans = [
        span for span in spans
        if normalize_text(span["text"]) not in blacklist
    ]

    return filtered_spans
def merge_adjacent_headings(spans: List[Dict], vertical_gap: float = 10.0, size_tolerance: float = 0.5) -> List[Dict]:
    from collections import defaultdict

    merged_spans = []
    spans_by_page = defaultdict(list)

    for span in spans:
        spans_by_page[span["page"]].append(span)

    for page, page_spans in spans_by_page.items():
        sorted_spans = sorted(page_spans, key=lambda x: x["coordinates"][1])  # sort by y0
        skip = set()
        i = 0

        while i < len(sorted_spans):
            if i in skip:
                i += 1
                continue

            current = sorted_spans[i]
            merged_text = current["text"]
            current_y1 = current["coordinates"][3]
            base_size = current["font_size"]
            j = i + 1

            while j < len(sorted_spans):
                next_span = sorted_spans[j]
                next_y0 = next_span["coordinates"][1]

                size_diff = abs(next_span["font_size"] - base_size)

                # Conditions to merge
                if (next_y0 - current_y1 <= vertical_gap and size_diff <= size_tolerance):
                    merged_text += " " + next_span["text"]
                    current_y1 = next_span["coordinates"][3]
                    skip.add(j)
                    j += 1
                else:
                    break

            # Final merged span
            merged_span = dict(current)
            merged_span["text"] = merged_text.strip()
            merged_spans.append(merged_span)
            i += 1

    return merged_spans


def rank_and_tag_headings(spans: List[Dict], top_n: int = 30, min_score: float = 20.0) -> List[Dict]:
    for span in spans:
        boost = 2.0 if span["in_box"] else 0
        span["importance_score"] = span["font_size"] + (span["font_weight"] / 100.0) + boost

    sorted_spans = sorted(spans, key=lambda x: -x["importance_score"])
    filtered_spans = [s for s in sorted_spans if s["importance_score"] >= min_score]

    if top_n:
        filtered_spans = filtered_spans[:top_n]

    seen = set()
    unique_filtered = []
    for span in filtered_spans:
        key = (normalize_text(span["text"]), span["page"])
        if key not in seen:
            seen.add(key)
            unique_filtered.append(span)

    unique_scores = []
    for span in unique_filtered:
        score = span["importance_score"]
        if score not in unique_scores:
            unique_scores.append(score)
        span["tag"] = f"H{unique_scores.index(score) + 1}"

    return unique_filtered
def generate_outline_structure(tagged_headings: List[Dict]) -> Dict:
    if not tagged_headings:
        return {}

    # Pehla heading le lo as main title
    title = tagged_headings[0]["text"]

    outline = []
    for h in tagged_headings[1:]:
        outline.append({
            "level": h["tag"].upper(),
            "text": h["text"].strip(),
            "page": h["page"]
        })

    return {
        "title": title.strip(),
        "outline": outline
    }

def extract_tagged_headings_from_pdf(pdf_path: str, output_json: str):
    all_text = extract_raw_text_per_page(pdf_path)
    total_pages = len(all_text)

    all_candidates = set()
    for text in all_text:
        candidates = find_heading_candidates(text)
        all_candidates.update(candidates)

    matched_spans = match_headings_in_pdf(pdf_path, list(all_candidates))

    with open("debug_all_matches.json", "w", encoding="utf-8") as f:
        json.dump(matched_spans, f, indent=2)

    matched_spans = remove_repeated_text(matched_spans, total_pages)
    merged_spans = merge_adjacent_headings(matched_spans)
    tagged = rank_and_tag_headings(merged_spans, top_n=30, min_score=20.0)

    # Sort tagged headings by page number
    tagged = sorted(tagged, key=lambda x: (x["page"], x["coordinates"][1]))


    # Reduce fields to only page, text, tag, content
# Generate structured outline
    minimal_output = generate_outline_structure(tagged)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(minimal_output, f, indent=2, ensure_ascii=False)


    print("\n📘 Most Important Titles:")
    for item in minimal_output["outline"]:
        print(f"{item['level']} | Page {item['page']} | {item['text']}")



    print(f"\n✅ Saved {len(minimal_output)} tagged headings to: {output_json}")


if __name__ == "__main__":
    input_pdf = "E0CCG5S312.pdf"      # just the PDF
    output_json = "tagged_headings.json"            # final output
    extract_tagged_headings_from_pdf(input_pdf, output_json)
