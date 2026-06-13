import fitz

doc = fitz.open("data/mv_act_1988.pdf")
for i in range(9, 15):
    print(f"=== PAGE {i+1} ===")
    print(doc[i].get_text()[:1000])
    print()