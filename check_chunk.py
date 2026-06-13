import json
import fitz
import re

# Load chunks
with open("data/chunks.json", encoding="utf-8") as f:
    chunks = json.load(f)

print(f"Total chunks: {len(chunks)}\n")

# Check section 130
s130 = next((c for c in chunks if c['section_number'] == '130'), None)
if s130:
    print("=== SECTION 130 ===")
    print(s130['text'])
else:
    print("Section 130 NOT FOUND")

print("\n---\n")

# Average text length
avg_len = sum(len(c['text']) for c in chunks) / len(chunks)
print(f"Average chunk length: {avg_len:.0f} chars")

# Short chunks
short = [c for c in chunks if len(c['text']) < 300]
print(f"Short chunks (under 300 chars): {len(short)}")
for c in short[:5]:
    print(f"  Section {c['section_number']}: {c['text'][:100]}")

print("\n---\n")

# Coverage check
section_nums = [int(c['section_number']) for c in chunks if c['section_number'].isdigit()]
section_nums.sort()
print(f"First section: {min(section_nums)}")
print(f"Last section: {max(section_nums)}")
print(f"Total numeric sections: {len(section_nums)}")

expected = set(range(min(section_nums), max(section_nums)+1))
found = set(section_nums)
missing = sorted(expected - found)
print(f"\nMissing sections ({len(missing)} total): {missing}")

print("\n---\n")

# Load raw text
doc = fitz.open("data/mv_act_1988.pdf")
full_text = ""
for page_num, page in enumerate(doc):
    if page_num < 14:
        continue
    full_text += page.get_text()

# Debug cleaning
import re
cleaned = re.sub(r'\n\d{1,2}\[(\d)', r'\n\1', full_text)
idx = cleaned.find("129.")
print("In cleaned text around 129:")
print(repr(cleaned[idx-20:idx+20]))

# Check if regex sees 129
matches = list(re.finditer(r'\n\s{0,4}(\d{1,3}[A-Z]?)\.\s{1,4}([A-Z][^\n]{5,})', full_text, re.MULTILINE))
nums = [m.group(1) for m in matches]
print("Sections found by regex:", sorted(set(nums), key=lambda x: int(x) if x.isdigit() else 0)[:50])
print("\nIs 129 in there?", '129' in nums)

# Raw text around 129
idx = full_text.find("129.")
print("\n=== RAW TEXT AROUND 129 ===")
print(repr(full_text[idx-50:idx+200]))

idx = full_text.find("129.")
print(repr(full_text[idx-10:idx+5]))