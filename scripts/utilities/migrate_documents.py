#!/usr/bin/env python3
"""
Migrate existing documents to company-specific indexes.

This script:
1. Updates existing documents to have correct company_hr_dataset
2. Rebuilds FAISS indexes in company-specific directories
3. Cleans up old root-level indexes
"""
import sys
import asyncio
from pathlib import Path
from sqlalchemy import create_engine, text
from src.core.config import get_settings
from src.services.vector_service import VectorService
from src.services.settings_service import SettingsService
from src.models import Document, DocumentChunk

async def main():
    print("=" * 80)
    print("Document Migration Script")
    print("=" * 80)
    print()

    settings = get_settings()
    engine = create_engine(settings.database_url)
    
    # Get default company - use direct SQL since SettingsService needs db
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT setting_value 
            FROM system_settings 
            WHERE setting_key = 'default_company_hr_dataset'
        """)).fetchone()
        default_company = result[0] if result else 'caylent'
    print(f"📋 Default company: {default_company}")
    print()

    # Step 1: Update documents with company_hr_dataset
    print("Step 1: Updating documents with company_hr_dataset...")
    with engine.connect() as conn:
        # Get documents without company_hr_dataset
        result = conn.execute(text("""
            SELECT id, filename, customer_id, company_hr_dataset
            FROM documents
            WHERE company_hr_dataset IS NULL OR company_hr_dataset = ''
        """)).fetchall()
        
        if not result:
            print("  ✓ All documents already have company_hr_dataset set")
        else:
            print(f"  Found {len(result)} documents to update")
            
            # Update with default company (or could use customer_id)
            # Using default company since all existing docs should go to same company
            conn.execute(text("""
                UPDATE documents
                SET company_hr_dataset = :company
                WHERE company_hr_dataset IS NULL OR company_hr_dataset = ''
            """), {"company": default_company})
            conn.commit()
            
            print(f"  ✓ Updated {len(result)} documents to company_hr_dataset = '{default_company}'")
    print()

    # Step 2: Update document chunks with company_hr_dataset
    print("Step 2: Updating document chunks with company_hr_dataset...")
    with engine.connect() as conn:
        # Update chunks from their parent documents
        result = conn.execute(text("""
            UPDATE document_chunks dc
            SET company_hr_dataset = d.company_hr_dataset
            FROM documents d
            WHERE dc.document_id = d.id
                AND (dc.company_hr_dataset IS NULL 
                     OR dc.company_hr_dataset = '' 
                     OR dc.company_hr_dataset != d.company_hr_dataset)
        """))
        conn.commit()
        
        print(f"  ✓ Updated {result.rowcount} document chunks")
    print()

    # Step 3: Get list of companies with documents
    print("Step 3: Identifying companies with documents...")
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT DISTINCT company_hr_dataset, COUNT(*) as doc_count
            FROM documents
            WHERE company_hr_dataset IS NOT NULL
            GROUP BY company_hr_dataset
            ORDER BY company_hr_dataset
        """)).fetchall()
        
        companies = [(row[0], row[1]) for row in result]
        print(f"  Found documents for {len(companies)} companies:")
        for company, count in companies:
            print(f"    - {company}: {count} documents")
    print()

    # Step 4: Rebuild FAISS indexes per company
    print("Step 4: Rebuilding FAISS indexes per company...")
    for company, doc_count in companies:
        print(f"  Processing company: {company}")
        
        # Create VectorService for this company
        vector_service = VectorService(company_hr_dataset=company)
        
        # Get all documents for this company
        with engine.connect() as conn:
            docs = conn.execute(text("""
                SELECT id, filename
                FROM documents
                WHERE company_hr_dataset = :company
                    AND status = 'completed'
                ORDER BY id
            """), {"company": company}).fetchall()
            
            print(f"    Found {len(docs)} completed documents")
            
            # Regenerate embeddings for each document
            for doc_id, filename in docs:
                try:
                    print(f"      Processing: {filename} (ID: {doc_id})")
                    success = await vector_service.generate_embeddings_for_document(doc_id)
                    if success:
                        print(f"        ✓ Generated embeddings")
                    else:
                        print(f"        ⚠ No chunks found or embedding failed")
                except Exception as e:
                    print(f"        ✗ Error: {e}")
        
        print(f"  ✓ Completed rebuilding index for {company}")
        print()

    # Step 5: Clean up old root-level indexes
    print("Step 5: Cleaning up old root-level indexes...")
    vector_base_dir = Path(settings.vector_index_directory)
    
    old_index_file = vector_base_dir / "faiss_index.bin"
    old_mapping_file = vector_base_dir / "chunk_mapping.json"
    
    files_removed = []
    if old_index_file.exists():
        # Backup before deleting
        backup_file = vector_base_dir / "faiss_index.bin.backup"
        old_index_file.rename(backup_file)
        files_removed.append(str(old_index_file))
        print(f"  ✓ Backed up {old_index_file} to {backup_file}")
    
    if old_mapping_file.exists():
        backup_file = vector_base_dir / "chunk_mapping.json.backup"
        old_mapping_file.rename(backup_file)
        files_removed.append(str(old_mapping_file))
        print(f"  ✓ Backed up {old_mapping_file} to {backup_file}")
    
    if not files_removed:
        print("  ✓ No old root-level indexes found")
    else:
        print(f"  ✓ Cleaned up {len(files_removed)} old index files")
    print()

    # Step 6: Verify migration
    print("Step 6: Verifying migration...")
    with engine.connect() as conn:
        # Check documents
        result = conn.execute(text("""
            SELECT COUNT(*) FROM documents WHERE company_hr_dataset IS NULL
        """)).fetchone()
        docs_without_company = result[0]
        
        # Check chunks
        result = conn.execute(text("""
            SELECT COUNT(*) FROM document_chunks WHERE company_hr_dataset IS NULL
        """)).fetchone()
        chunks_without_company = result[0]
        
        if docs_without_company == 0 and chunks_without_company == 0:
            print("  ✓ All documents and chunks have company_hr_dataset set")
        else:
            print(f"  ⚠ Warning: {docs_without_company} documents and {chunks_without_company} chunks still missing company_hr_dataset")
        
        # Check company-specific directories
        for company, _ in companies:
            company_dir = vector_base_dir / company
            index_file = company_dir / "faiss_index.bin"
            mapping_file = company_dir / "chunk_mapping.json"
            
            if index_file.exists() and mapping_file.exists():
                print(f"  ✓ Index files exist for {company}")
            else:
                print(f"  ⚠ Warning: Missing index files for {company}")
    
    print()
    print("=" * 80)
    print("✅ Migration Complete!")
    print("=" * 80)
    print()
    print("Summary:")
    print(f"  - Migrated documents for {len(companies)} companies")
    print(f"  - Total documents processed: {sum(count for _, count in companies)}")
    print(f"  - Company-specific indexes created in: {vector_base_dir}")
    print()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠ Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

