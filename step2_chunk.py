"""
STEP 2: Parse MV Act PDF and chunk by section
- Extracts text from PDF
- Splits into section-level chunks (e.g., Section 130, Section 177)
- Saves as JSON for embedding in next step

Chunking strategy: by legal section
Why: Each section = one legal concept = one retrievable unit
"""

import fitz  # pymupdf
import re
import json
import os

INPUT_PDF = "data/mv_act_1988.pdf"
OUTPUT_JSON = "data/chunks.json"


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from all pages except TOC."""
    doc = fitz.open(pdf_path)
    full_text = ""
    for page_num, page in enumerate(doc):
        if page_num < 14:  # skip table of contents
            continue
        full_text += page.get_text()
    page_count = len(doc)
    doc.close()
    print(f"Extracted text from {page_count} pages")
    return full_text


def chunk_by_section(full_text: str) -> list:
    import re
    chunks_dict = {}  # id -> chunk, keeps longest version
    current_chapter = "General"
    chapter_pattern = re.compile(r'CHAPTER\s+[IVXLC]+\s*\n([^\n]+)', re.IGNORECASE)

    cleaned_text = re.sub(r'\n\d{1,2}\[(\d)', r'\n\1', full_text)
    cleaned_text = re.sub(r'\n(\d{1,3}[A-Z]?)\. \d{1,2}\[', r'\n\1. ', cleaned_text)

    section_pattern = re.compile(
        r'\n\s{0,4}(\d{1,3}[A-Z]?)\.\s{1,4}([A-Z][^\n]{5,})',
        re.MULTILINE
    )

    matches = list(section_pattern.finditer(cleaned_text))

    for i, match in enumerate(matches):
        section_num = match.group(1)
        start = match.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(cleaned_text)
        section_text = cleaned_text[start:end].strip()

        chapter_match = chapter_pattern.search(cleaned_text[max(0, start-500):start])
        if chapter_match:
            current_chapter = chapter_match.group(1).strip()

        if (len(section_text) > 120
                and "Subs. by" not in section_text[:100]
                and "Omitted by" not in section_text[:100]):

            chunk_id = f"section_{section_num}"

            # Prefer chunk whose text starts with the actual section number
            starts_correctly = section_text.startswith(f"{section_num}.")
            existing = chunks_dict.get(chunk_id)

            if not existing:
                chunks_dict[chunk_id] = {
                    "id": chunk_id,
                    "section_number": section_num,
                    "chapter": current_chapter,
                    "text": section_text[:2000],
                    "source": "Motor Vehicles Act 1988"
                }
            elif starts_correctly and not existing['text'].startswith(f"{section_num}."):
                # Current match is better, replace
                chunks_dict[chunk_id] = {
                    "id": chunk_id,
                    "section_number": section_num,
                    "chapter": current_chapter,
                    "text": section_text[:2000],
                    "source": "Motor Vehicles Act 1988"
                }
            elif starts_correctly and len(section_text) > len(existing['text']):
                # Both start correctly, keep longer
                chunks_dict[chunk_id] = {
                    "id": chunk_id,
                    "section_number": section_num,
                    "chapter": current_chapter,
                    "text": section_text[:2000],
                    "source": "Motor Vehicles Act 1988"
                }

    chunks = list(chunks_dict.values())
    print(f"Created {len(chunks)} section chunks")
    return chunks


def save_chunks(chunks: list, output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    print(f"Saved chunks to: {output_path}")

    if chunks:
        print("\nSample chunk:")
        print(f"  ID: {chunks[0]['id']}")
        print(f"  Chapter: {chunks[0]['chapter']}")
        print(f"  Text preview: {chunks[0]['text'][:200]}...")


if __name__ == "__main__":
    if not os.path.exists(INPUT_PDF):
        print(f"PDF not found at {INPUT_PDF}")
        print("Run step1_download.py first")
        exit(1)

    full_text = extract_text_from_pdf(INPUT_PDF)
    chunks = chunk_by_section(full_text)
    save_chunks(chunks, OUTPUT_JSON)
    print(f"\nDone. {len(chunks)} chunks ready for embedding.")