#!/usr/bin/env python3
"""
Download FASB ASC dataset from Hugging Face and place PDFs in the correct location.

Usage:
    pip install datasets huggingface_hub
    
    # Option 1: Set HF_TOKEN environment variable
    export HF_TOKEN=hf_xxxxxxxxxxxxx
    python scripts/download_fasb_dataset.py
    
    # Option 2: Login via CLI first
    huggingface-cli login
    python scripts/download_fasb_dataset.py
"""

import os
import sys
from pathlib import Path

# Target directory for FASB PDFs
TARGET_DIR = Path("/app/data/eval/fasb_docs") if Path("/app").exists() else Path("data/eval/fasb_docs")


def main():
    print("=" * 60)
    print("FASB Dataset Downloader")
    print("=" * 60)
    
    # Ensure target directory exists
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n✓ Target directory: {TARGET_DIR.absolute()}")
    
    # Import datasets library
    try:
        from datasets import load_dataset
        from huggingface_hub import login
        print("✓ datasets library loaded")
    except ImportError:
        print("✗ datasets library not found. Installing...")
        os.system(f"{sys.executable} -m pip install datasets huggingface_hub")
        from datasets import load_dataset
        from huggingface_hub import login
        print("✓ datasets library installed and loaded")
    
    # Check for HF token authentication
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token:
        print("✓ HF_TOKEN found in environment")
        try:
            login(token=hf_token)
            print("✓ Logged in to Hugging Face")
        except Exception as e:
            print(f"⚠ Login warning: {e}")
    else:
        print("⚠ No HF_TOKEN found. Will try to use cached credentials.")
        print("  If download fails, set HF_TOKEN environment variable or run: huggingface-cli login")
    
    # Load the dataset
    print("\n📥 Loading dataset from Hugging Face: adarshxs/asc-blah")
    print("   (This may take a few minutes depending on dataset size...)")
    
    try:
        ds = load_dataset("adarshxs/asc-blah", token=hf_token)
        print(f"✓ Dataset loaded successfully")
    except Exception as e:
        print(f"✗ Failed to load dataset: {e}")
        print("\n💡 This dataset may be gated. To access it:")
        print("   1. Go to https://huggingface.co/datasets/adarshxs/asc-blah")
        print("   2. Request access (if needed)")
        print("   3. Get your token from https://huggingface.co/settings/tokens")
        print("   4. Run: export HF_TOKEN=hf_your_token_here")
        print("   5. Re-run this script")
        sys.exit(1)
    
    # Inspect dataset structure
    print("\n📊 Dataset structure:")
    print(f"   Splits: {list(ds.keys())}")
    
    for split_name, split_data in ds.items():
        print(f"\n   {split_name}:")
        print(f"      Rows: {len(split_data)}")
        print(f"      Columns: {split_data.column_names}")
        
        # Show first row to understand structure
        if len(split_data) > 0:
            print(f"      Sample row keys: {list(split_data[0].keys()) if isinstance(split_data[0], dict) else 'N/A'}")
    
    # Process and save files
    print("\n📁 Processing files...")
    
    files_saved = 0
    files_skipped = 0
    
    for split_name, split_data in ds.items():
        for idx, row in enumerate(split_data):
            # Try different possible column names for file content
            file_content = None
            file_name = None
            doc_id = None
            
            # Check for common column patterns
            if isinstance(row, dict):
                # Look for PDF content
                for key in ['pdf', 'content', 'file', 'data', 'bytes', 'pdf_bytes']:
                    if key in row and row[key] is not None:
                        file_content = row[key]
                        break
                
                # Look for filename or doc_id
                for key in ['filename', 'file_name', 'name', 'doc_id', 'id', 'document_id']:
                    if key in row and row[key] is not None:
                        file_name = str(row[key])
                        break
                
                # Look for doc_id specifically
                for key in ['doc_id', 'document_id', 'id']:
                    if key in row and row[key] is not None:
                        doc_id = str(row[key])
                        break
            
            # If we have file content, save it
            if file_content is not None:
                # Determine output filename
                if doc_id:
                    output_name = f"{doc_id}.pdf"
                elif file_name:
                    output_name = file_name if file_name.endswith('.pdf') else f"{file_name}.pdf"
                else:
                    output_name = f"doc_{idx}.pdf"
                
                output_path = TARGET_DIR / output_name
                
                # Write file
                try:
                    if isinstance(file_content, bytes):
                        with open(output_path, 'wb') as f:
                            f.write(file_content)
                    elif isinstance(file_content, str):
                        # Might be base64 encoded
                        import base64
                        try:
                            decoded = base64.b64decode(file_content)
                            with open(output_path, 'wb') as f:
                                f.write(decoded)
                        except:
                            with open(output_path, 'w') as f:
                                f.write(file_content)
                    else:
                        # Try to access as file-like object
                        if hasattr(file_content, 'read'):
                            with open(output_path, 'wb') as f:
                                f.write(file_content.read())
                        elif hasattr(file_content, 'path'):
                            # It's a file reference, copy it
                            import shutil
                            shutil.copy(file_content.path, output_path)
                        else:
                            print(f"   ⚠ Unknown content type for row {idx}: {type(file_content)}")
                            files_skipped += 1
                            continue
                    
                    files_saved += 1
                    if files_saved <= 5 or files_saved % 50 == 0:
                        print(f"   ✓ Saved: {output_name}")
                        
                except Exception as e:
                    print(f"   ✗ Error saving {output_name}: {e}")
                    files_skipped += 1
            else:
                # No file content found, print row structure for debugging
                if idx == 0:
                    print(f"\n   ⚠ No file content found in expected columns.")
                    print(f"   Row structure: {row if isinstance(row, dict) else type(row)}")
                    print(f"\n   Please check the dataset structure and update the script accordingly.")
                files_skipped += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"   Files saved:   {files_saved}")
    print(f"   Files skipped: {files_skipped}")
    print(f"   Location:      {TARGET_DIR.absolute()}")
    
    # List saved files
    saved_files = list(TARGET_DIR.glob("*.pdf"))
    if saved_files:
        print(f"\n📂 Files in {TARGET_DIR}:")
        for f in sorted(saved_files)[:10]:
            print(f"      {f.name}")
        if len(saved_files) > 10:
            print(f"      ... and {len(saved_files) - 10} more")
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
