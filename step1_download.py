"""
STEP 1: Download Motor Vehicles Act PDF
Source: India Code (official govt repository)
"""

import requests
import os

# Official India Code URL for Motor Vehicles Act 1988
MV_ACT_URL = "https://indiacode.nic.in/bitstream/123456789/1798/1/A1988-59.pdf"
OUTPUT_PATH = "data/mv_act_1988.pdf"

os.makedirs("data", exist_ok=True)

def download_pdf(url: str, output_path: str):
    print(f"Downloading MV Act from India Code...")
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; research-bot)"
    }
    response = requests.get(url, headers=headers, timeout=60)
    
    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        size_kb = len(response.content) / 1024
        print(f"Downloaded: {output_path} ({size_kb:.1f} KB)")
    else:
        print(f"Failed: HTTP {response.status_code}")
        print("Manual fallback: Download from https://indiacode.nic.in/handle/123456789/1798")
        print("Save as: data/mv_act_1988.pdf")

if __name__ == "__main__":
    download_pdf(MV_ACT_URL, OUTPUT_PATH)
