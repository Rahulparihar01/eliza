#!/usr/bin/env python3
"""
Download FASB ASC PDFs from Hugging Face dataset.

Usage:
    HF_TOKEN=hf_xxx python scripts/download_fasb_pdfs.py

The PDFs will be saved to data/eval/fasb_docs/ with filenames like 105.pdf, 815.pdf etc.
"""
import os
import sys
import re
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def extract_doc_id_from_path(path: str) -> str:
    """Extract ASC topic number from file path like 'hf://datasets/.../ASC105.pdf'"""
    # Try to find ASC followed by numbers
    match = re.search(r'ASC[_-]?(\d+)', path, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Fallback: get filename without extension
    filename = Path(path).stem
    # Remove 'ASC' prefix if present
    filename = re.sub(r'^ASC[_-]?', '', filename, flags=re.IGNORECASE)
    return filename

def main():
    from datasets import load_dataset
    from huggingface_hub import hf_hub_download, list_repo_files
    
    # Get HF token from environment
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        print("ERROR: HF_TOKEN environment variable not set")
        print("Usage: HF_TOKEN=hf_xxx python scripts/download_fasb_pdfs.py")
        sys.exit(1)
    
    # Output directory
    output_dir = project_root / "data" / "eval" / "fasb_docs"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Downloading FASB PDFs to: {output_dir}")
    
    repo_id = "adarshxs/asc-blah"
    
    # Method 1: Try to list and download files directly from the repo
    print("\nListing files in repository...")
    try:
        files = list_repo_files(repo_id, repo_type="dataset", token=hf_token)
        pdf_files = [f for f in files if f.endswith('.pdf')]
        
        if pdf_files:
            print(f"Found {len(pdf_files)} PDF files in repository")
            
            for pdf_file in pdf_files:
                print(f"  Downloading: {pdf_file}")
                try:
                    local_path = hf_hub_download(
                        repo_id=repo_id,
                        filename=pdf_file,
                        repo_type="dataset",
                        token=hf_token
                    )
                    
                    # Extract doc_id from filename
                    doc_id = extract_doc_id_from_path(pdf_file)
                    target_path = output_dir / f"{doc_id}.pdf"
                    
                    # Copy to our output directory
                    import shutil
                    shutil.copy(local_path, target_path)
                    print(f"    Saved as: {target_path.name}")
                except Exception as e:
                    print(f"    Error downloading {pdf_file}: {e}")
            
            print(f"\n=== Download Complete ===")
            saved_files = list(output_dir.glob("*.pdf"))
            print(f"Total PDFs saved: {len(saved_files)}")
            print(f"Output directory: {output_dir}")
            
            if saved_files:
                print(f"\nSaved files ({len(saved_files)}):")
                for f in sorted(saved_files, key=lambda x: int(x.stem) if x.stem.isdigit() else 999):
                    print(f"  - {f.name}")
            return
    except Exception as e:
        print(f"Direct file listing failed: {e}")
    
    # Method 2: Load dataset and access raw arrow table
    print("\nTrying to load dataset with raw access...")
    
    # Load without decoding the PDF feature
    ds = load_dataset(
        repo_id, 
        token=hf_token,
        trust_remote_code=True
    )
    
    print(f"Dataset loaded. Keys: {ds.keys()}")
    
    train_data = ds['train']
    print(f"Columns: {train_data.column_names}")
    print(f"Number of rows: {len(train_data)}")
    
    # Access the underlying arrow table to get raw bytes
    arrow_table = train_data.data
    pdf_column = arrow_table.column('pdf')
    
    pdf_count = 0
    for i in range(len(pdf_column)):
        try:
            # Get the struct from arrow
            pdf_struct = pdf_column[i].as_py()
            
            if pdf_struct is None:
                print(f"  Row {i}: No PDF data")
                continue
            
            # The PDF feature stores data as {'path': ..., 'bytes': ...}
            if isinstance(pdf_struct, dict):
                pdf_bytes = pdf_struct.get('bytes')
                pdf_path = pdf_struct.get('path', '')
                
                if pdf_bytes:
                    # Extract doc_id from path
                    doc_id = extract_doc_id_from_path(pdf_path) if pdf_path else str(i)
                    target_path = output_dir / f"{doc_id}.pdf"
                    
                    with open(target_path, 'wb') as f:
                        f.write(pdf_bytes)
                    print(f"  Saved: {target_path.name} (from {pdf_path})")
                    pdf_count += 1
                elif pdf_path:
                    print(f"  Row {i}: Found path {pdf_path} but no bytes (need to download)")
            else:
                print(f"  Row {i}: Unexpected type {type(pdf_struct)}")
                
        except Exception as e:
            print(f"  Row {i}: Error - {e}")
    
    print(f"\n=== Download Complete ===")
    print(f"Total PDFs saved: {pdf_count}")
    print(f"Output directory: {output_dir}")
    
    # List what was saved
    saved_files = list(output_dir.glob("*.pdf"))
    if saved_files:
        print(f"\nSaved files ({len(saved_files)}):")
        for f in sorted(saved_files, key=lambda x: int(x.stem) if x.stem.isdigit() else 999):
            print(f"  - {f.name}")
    else:
        print("\nNo PDF files were saved.")

if __name__ == "__main__":
    main()
