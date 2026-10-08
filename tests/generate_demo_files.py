import os

assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "demo_assets"))
os.makedirs(assets_dir, exist_ok=True)

# 1. Valid PDF dummy (starts with proper %PDF header)
valid_pdf_path = os.path.join(assets_dir, "valid_sample.pdf")
with open(valid_pdf_path, "wb") as f:
    f.write(b"%PDF-1.4 mock content for demo")

# 2. Corrupt PDF dummy (has .pdf extension, but starts with junk bytes)
corrupt_pdf_path = os.path.join(assets_dir, "corrupt_sample.pdf")
with open(corrupt_pdf_path, "wb") as f:
    f.write(b"CORRUPT_BYTES_NOT_A_PDF")

# 3. Empty file (0 bytes)
empty_file_path = os.path.join(assets_dir, "empty_sample.pdf")
with open(empty_file_path, "wb") as f:
    pass

print(f"Created demo assets successfully in: {assets_dir}")
print("1. valid_sample.pdf")
print("2. corrupt_sample.pdf")
print("3. empty_sample.pdf")