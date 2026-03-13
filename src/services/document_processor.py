"""
Document processing service for the AI Enablement Platform.
Handles file upload, format detection, content extraction, and chunking.
"""

import os
import hashlib
import mimetypes
import asyncio
import logging
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime
import uuid

import aiofiles
import filetype
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .base_service import BaseService
from ..models import (
    Document, DocumentChunk, UploadBatch, DocumentStatus, ChunkingStrategy,
    get_db
)
from ..models.database import SessionLocal
from ..models.document import (
    DocumentUploadRequest, DocumentInfo, UploadBatchInfo
)
from ..core.config import get_settings
from .chunking_service import (
    ChunkingService,
    SemanticChunker,
    FixedChunker,
    HierarchicalChunker
)
from .vector_service import VectorService

logger = logging.getLogger(__name__)


class DocumentProcessor(BaseService):
    """Main document processing service"""

    def __init__(self):
        self.settings = get_settings()
        self.chunking_service = ChunkingService()
        # Note: VectorService is created per-document with company_hr_dataset
        # See _generate_embeddings_sync method

        # Ensure upload directory exists
        self.upload_dir = Path(self.settings.upload_directory)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Supported file types - maps full MIME types to simplified document types
        self.mime_type_mapping = {
            'application/pdf': 'pdf',
            'application/msword': 'doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
            'text/plain': 'txt',
            'text/markdown': 'md',
            'application/vnd.ms-excel': 'xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
            'text/csv': 'csv',
            'application/json': 'json'
        }
        
        # Reverse mapping for serving files with correct Content-Type
        self.simplified_to_mime = {v: k for k, v in self.mime_type_mapping.items()}
        
        # Maximum file size (100MB)
        self.max_file_size = 100 * 1024 * 1024

    # get_db_session() method is now inherited from BaseService
    
    async def create_upload_batch(
        self,
        customer_id: str,
        upload_request: DocumentUploadRequest
    ) -> str:
        """Create a new upload batch with proper session management"""
        batch_id = f"batch_{uuid.uuid4().hex[:12]}"

        try:
            with self.get_db_session() as db:
                batch = UploadBatch(
                    batch_id=batch_id,
                    customer_id=customer_id,
                    chunking_strategy=upload_request.chunking_strategy,
                    chunking_config=upload_request.chunking_config or {},
                    qa_rag_enabled=upload_request.enable_qa_rag,
                    batch_metadata=upload_request.metadata or {}
                )
                db.add(batch)
                # Session will be committed by context manager

        except SQLAlchemyError as e:
            logger.error(f"Database error creating upload batch: {e}")
            raise

        logger.info(f"Created upload batch {batch_id} for customer {customer_id}")
        return batch_id
    
    async def process_uploaded_file(
        self,
        file_content: bytes,
        filename: str,
        customer_id: str,
        batch_id: str,
        upload_request: DocumentUploadRequest
    ) -> Dict[str, Any]:
        """Process a single uploaded file"""

        operation_id = str(uuid.uuid4())[:8]

        try:
            logger.info(f"🔍 DEBUG: process_uploaded_file called for {filename}")
            logger.info(f"🔍 DEBUG: SessionLocal in process_uploaded_file: {SessionLocal}")
            logger.info(f"[DOCUMENT_PROCESSING] Starting file processing for {filename}")

            # Validate file
            logger.info(f"[DOCUMENT_PROCESSING] Step 1: Validating file {filename}")
            validation_result = await self._validate_file(file_content, filename)
            if not validation_result['valid']:
                logger.error(f"[DOCUMENT_PROCESSING] File validation failed for {filename}: {validation_result['error']}")
                return {
                    'success': False,
                    'error': validation_result['error'],
                    'filename': filename
                }

            logger.info(f"[DOCUMENT_PROCESSING] Step 2: Saving file {filename} to disk")
            # Save file to disk
            file_info = await self._save_file(file_content, filename, customer_id)
            logger.info(f"[DOCUMENT_PROCESSING] Step 3: File {filename} saved successfully")

            logger.info(f"[DOCUMENT_PROCESSING] Step 4: Creating document record for {filename}")
            # Create document record
            document_id = await self._create_document_record(
                file_info, customer_id, batch_id, upload_request
            )
            logger.info(f"[DOCUMENT_PROCESSING] Step 5: Document record created successfully with ID {document_id}")

            # Enqueue Celery task for async processing
            from src.tasks.documents import process_document_task
            task_result = process_document_task.delay(document_id)
            logger.info(f"Document {document_id} uploaded successfully, Celery task queued: {task_result.id}")

            return {
                'success': True,
                'document_id': document_id,
                'filename': filename,
                'file_size': len(file_content),
                'mime_type': file_info['mime_type']
            }
            
        except ValueError as ve:
            # Re-raise validation errors (like duplicate filenames) so they return proper HTTP errors
            logger.warning(f"[DOCUMENT_PROCESSING] Validation error for {filename}: {str(ve)}")
            raise
        except Exception as e:
            error_id = str(uuid.uuid4())[:8]
            logger.error(f"🔍 DEBUG: Exception caught in process_uploaded_file: {type(e).__name__}: {e}")
            logger.error(f"🔍 DEBUG: Stack trace: {traceback.format_exc()}")
            logger.error(
                f"[DOCUMENT_PROCESSING] Failed to process file {filename}",
                extra={
                    'error_id': error_id,
                    'file_name': filename,  # Changed from 'filename' to avoid Python logging conflict
                    'customer_id': customer_id,
                    'batch_id': batch_id,
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'stack_trace': traceback.format_exc(),
                    'operation': 'process_uploaded_file',
                    'category': 'data_processing'
                }
            )
            return {
                'success': False,
                'error': f"Processing failed (Error ID: {error_id}): {str(e)}",
                'filename': filename
            }
    
    async def _validate_file(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Validate uploaded file"""
        
        # Check file size
        if len(file_content) > self.max_file_size:
            return {
                'valid': False,
                'error': f'File too large. Maximum size is {self.max_file_size // (1024*1024)}MB'
            }
        
        # Check if file is empty
        if len(file_content) == 0:
            return {
                'valid': False,
                'error': 'File is empty'
            }
        
        # Detect file type
        detected_type = filetype.guess(file_content)
        full_mime_type = detected_type.mime if detected_type else mimetypes.guess_type(filename)[0]
        
        # Check if file type is supported
        if full_mime_type not in self.mime_type_mapping:
            return {
                'valid': False,
                'error': f'Unsupported file type: {full_mime_type}. Supported types: {list(self.mime_type_mapping.keys())}'
            }
        
        # Normalize to simplified document type
        simplified_type = self.mime_type_mapping[full_mime_type]
        
        return {
            'valid': True,
            'mime_type': simplified_type,  # Store simplified type (e.g., "pdf" instead of "application/pdf")
            'file_extension': simplified_type
        }
    
    async def _save_file(self, file_content: bytes, filename: str, customer_id: str) -> Dict[str, Any]:
        """Save file to disk and return file info"""
        
        # Generate file hash
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        # Create customer directory
        customer_dir = self.upload_dir / customer_id
        customer_dir.mkdir(exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
        unique_filename = f"{timestamp}_{file_hash[:8]}_{safe_filename}"
        
        file_path = customer_dir / unique_filename
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
        # Detect MIME type and normalize to simplified type
        detected_type = filetype.guess(file_content)
        full_mime_type = detected_type.mime if detected_type else mimetypes.guess_type(filename)[0]
        
        # Normalize to simplified document type
        simplified_type = self.mime_type_mapping.get(full_mime_type, full_mime_type)
        
        return {
            'file_path': str(file_path),
            'filename': unique_filename,
            'original_filename': filename,
            'file_size': len(file_content),
            'file_hash': file_hash,
            'mime_type': simplified_type  # Store simplified type (e.g., "pdf")
        }
    
    async def _create_document_record(
        self,
        file_info: Dict[str, Any],
        customer_id: str,
        batch_id: str,
        upload_request: DocumentUploadRequest
    ) -> int:
        """Create document record with proper session management"""

        try:
            logger.info(f"🔍 DEBUG: Starting document record creation for {file_info.get('filename')}")
            logger.info(f"🔍 DEBUG: SessionLocal type: {type(SessionLocal)}, value: {SessionLocal}")

            with self.get_db_session() as db:
                logger.info(f"🔍 DEBUG: Session created successfully: {db}")
                
                # Check for duplicate filename in the same customer context
                logger.info(f"🔍 DUPLICATE_CHECK: Checking for existing document with filename='{file_info['original_filename']}' for customer='{customer_id}'")
                
                existing_doc = db.query(Document).filter(
                    Document.customer_id == customer_id,
                    Document.original_filename == file_info['original_filename'],
                    Document.status != DocumentStatus.DELETED  # Only check non-deleted documents
                ).first()
                
                if existing_doc:
                    error_msg = f"A document with the name '{file_info['original_filename']}' already exists. Please rename the file and try again."
                    logger.warning(f"🔍 DUPLICATE_CHECK: Duplicate filename detected! File='{file_info['original_filename']}' (existing doc_id: {existing_doc.id}, status: {existing_doc.status})")
                    raise ValueError(error_msg)
                else:
                    logger.info(f"🔍 DUPLICATE_CHECK: No duplicate found. Proceeding with document creation.")
                
                # Create document instance
                logger.info(f"🔍 DEBUG: Creating Document object...")
                document = Document(
                    filename=file_info['filename'],
                    original_filename=file_info['original_filename'],
                    file_path=file_info['file_path'],
                    file_size=file_info['file_size'],
                    mime_type=file_info['mime_type'],
                    file_hash=file_info['file_hash'],
                    customer_id=customer_id,
                    company_hr_dataset=upload_request.company_hr_dataset,  # Set company association
                    upload_batch_id=batch_id,
                    source_id=upload_request.source_id,
                    chunking_strategy=upload_request.chunking_strategy,
                    chunking_config=upload_request.chunking_config or {},
                    qa_rag_enabled=upload_request.enable_qa_rag,
                    document_metadata=upload_request.metadata or {},
                    status=DocumentStatus.UPLOADED
                )
                logger.info(f"🔍 DEBUG: Document object created with company_hr_dataset={upload_request.company_hr_dataset}")

                # Add to session and flush to get ID
                logger.info(f"🔍 DEBUG: Adding document to session...")
                db.add(document)
                logger.info(f"🔍 DEBUG: Document added to session, flushing...")
                db.flush()  # Get ID without committing yet
                logger.info(f"🔍 DEBUG: Session flushed, getting document ID...")
                document_id = document.id
                logger.info(f"🔍 DEBUG: Document ID obtained: {document_id}")

                # Update batch file count in same transaction
                batch = db.query(UploadBatch).filter(UploadBatch.batch_id == batch_id).first()
                if batch:
                    batch.total_files += 1

                # Transaction will be committed by context manager
                logger.info(f"Document {document_id} created successfully")
                return document_id

        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemy error in document creation: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in document creation: {e}")
            raise
    
    async def _process_document_async(self, document_id: int):
        """Process document asynchronously with manual session management"""
        
        # Create session manually to avoid context manager commit issues in async
        db = SessionLocal()
        
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                logger.error(f"Document {document_id} not found")
                return

            # Update status to processing
            document.status = DocumentStatus.PROCESSING
            document.processing_started_at = datetime.utcnow()
            db.commit()  # Commit status update immediately

            try:
                logger.info(f"Starting processing for document {document_id}: {document.original_filename}")

                # Extract text content
                text_content = await self._extract_text_content(document)

                # Update document with extracted content info
                document.total_characters = len(text_content)
                document.total_tokens = len(text_content.split())

                # Extract metadata
                extracted_metadata = await self._extract_metadata(document, text_content)
                document.extracted_metadata = extracted_metadata

                # Chunk the document
                chunks = await self.chunking_service.chunk_document(
                    text_content,
                    document.chunking_strategy,
                    document.chunking_config or {}
                )

                # Save chunks to database (in same session)
                await self._save_chunks(db, document, chunks)

                # Generate embeddings for chunks
                await self.vector_service.generate_embeddings_for_document(document_id)

                # Calculate quality score
                quality_score = await self._calculate_quality_score(document, chunks)
                document.quality_score = quality_score

                # Update document status
                document.status = DocumentStatus.COMPLETED
                document.processing_completed_at = datetime.utcnow()
                document.total_chunks = len(chunks)

                # Update batch progress
                await self._update_batch_progress(db, document.upload_batch_id, completed=True)

                # Commit all changes
                db.commit()
                logger.info(f"Successfully processed document {document_id}: {len(chunks)} chunks created")

            except Exception as e:
                logger.error(f"Failed to process document {document_id}: {e}")
                logger.error(f"Stack trace: {traceback.format_exc()}")

                # Update document status to failed
                document.status = DocumentStatus.FAILED
                document.processing_error = str(e)
                document.processing_completed_at = datetime.utcnow()

                # Update batch progress
                await self._update_batch_progress(db, document.upload_batch_id, failed=True)
                
                # Commit failure state
                db.commit()

        except Exception as e:
            logger.error(f"Critical error in document processing {document_id}: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
            logger.debug(f"Database session closed for document {document_id} processing")
    
    def process_document_sync(self, document_id: int, force: bool = False) -> None:
        """
        Process document synchronously for Celery workers.
        
        This is the main processing pipeline that:
        1. Checks idempotency (skip if already processed)
        2. Extracts text from the document
        3. Chunks the content
        4. Generates embeddings
        5. Updates document status
        
        Args:
            document_id: ID of the document to process
            force: If True, reprocess even if already completed
        """
        with self.get_db_session() as db:
            try:
                # Load document
                document = db.query(Document).filter(Document.id == document_id).first()
                if not document:
                    logger.error(f"Document {document_id} not found")
                    raise ValueError(f"Document {document_id} not found")
                
                # Idempotency check
                if document.status == DocumentStatus.COMPLETED and not force:
                    logger.info(f"Document {document_id} already processed, skipping")
                    return
                
                # CLEANUP LOGIC: If retrying or force, remove any existing chunks for this document
                if force or document.status in [DocumentStatus.PROCESSING, DocumentStatus.FAILED]:
                    logger.info(f"[DOC-{document_id}] Cleaning up existing chunks before retry")
                    db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
                    document.total_chunks = 0
                    document.duplicate_chunks_count = 0
                    db.commit()
                
                # Update status to processing
                document.status = DocumentStatus.PROCESSING
                document.processing_started_at = datetime.utcnow()
                document.processing_error = None  # Clear any previous errors
                db.commit()  # Commit status immediately for visibility
                
                logger.info(f"[DOC-{document_id}] Starting processing: {document.original_filename}")
                
                # Step 1: Extract text content
                logger.info(f"[DOC-{document_id}] Step 1/5: Extracting text")
                text_content = self._extract_text_content_sync(document)
                
                # Step 2: Update document with content info
                logger.info(f"[DOC-{document_id}] Step 2/5: Analyzing content")
                document.total_characters = len(text_content)
                document.total_tokens = len(text_content.split())
                
                # Extract metadata
                extracted_metadata = self._extract_metadata_sync(document, text_content)
                document.extracted_metadata = extracted_metadata
                
                # Step 3: Chunk the document
                logger.info(f"[DOC-{document_id}] Step 3/5: Chunking ({document.chunking_strategy})")
                chunks = self._chunk_document_sync(
                    text_content,
                    document.chunking_strategy,
                    document.chunking_config or {}
                )
                logger.info(f"[DOC-{document_id}] Created {len(chunks)} chunks")
                
                # Step 4: Save chunks to database
                logger.info(f"[DOC-{document_id}] Step 4/5: Saving chunks")
                self._save_chunks_sync(db, document, chunks)
                
                # Commit chunks to make them visible to vector service's separate session
                db.commit()
                
                # Step 5: Generate embeddings
                logger.info(f"[DOC-{document_id}] Step 5/5: Generating embeddings")
                self._generate_embeddings_sync(document_id, db)
                
                # Calculate quality score
                quality_score = self._calculate_quality_score_sync(document, chunks)
                document.quality_score = quality_score
                
                # Update document status to completed
                document.status = DocumentStatus.COMPLETED
                document.processing_completed_at = datetime.utcnow()
                # total_chunks is already set by _save_chunks_sync (saved count, excluding duplicates)
                document.total_chunks = len(chunks) - document.duplicate_chunks_count
                
                # Update batch progress
                self._update_batch_progress_sync(db, document.upload_batch_id, completed=True)
                
                # Final commit happens via context manager
                logger.info(f"[DOC-{document_id}] ✓ Processing complete: {len(chunks)} chunks, quality={quality_score:.2f}")
                
            except Exception as e:
                error_id = str(uuid.uuid4())[:8]
                logger.error(
                    f"[DOC-{document_id}] ✗ Processing failed",
                    extra={
                        'error_id': error_id,
                        'document_id': document_id,
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'stack_trace': traceback.format_exc()
                    }
                )
                
                # Update document status to failed
                document.status = DocumentStatus.FAILED
                document.processing_error = f"{type(e).__name__}: {str(e)} (Error ID: {error_id})"
                document.processing_completed_at = datetime.utcnow()
                
                # Update batch progress
                self._update_batch_progress_sync(db, document.upload_batch_id, failed=True)
                
                # Re-raise to trigger Celery retry
                raise
    
    async def _extract_text_content(self, document: Document) -> str:
        """Extract text content from document based on file type"""
        
        file_path = Path(document.file_path)
        
        if document.mime_type == 'txt':
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                return await f.read()
        
        elif document.mime_type == 'pdf':
            return await self._extract_pdf_text(file_path)
        
        elif document.mime_type in ['docx', 'doc']:
            return await self._extract_docx_text(file_path)
        
        else:
            # For unsupported types, try to read as text
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    return await f.read()
            except UnicodeDecodeError:
                # Try with different encoding
                async with aiofiles.open(file_path, 'r', encoding='latin-1') as f:
                    return await f.read()
    
    async def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF file"""
        try:
            import PyPDF2
            
            text_content = []
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text_content.append(page.extract_text())
            
            return '\n'.join(text_content)
            
        except Exception as e:
            logger.error(f"Failed to extract PDF text from {file_path}: {e}")
            raise
    
    async def _extract_docx_text(self, file_path: Path) -> str:
        """Extract text from DOCX file"""
        try:
            from docx import Document as DocxDocument
            
            doc = DocxDocument(file_path)
            text_content = []
            
            for paragraph in doc.paragraphs:
                text_content.append(paragraph.text)
            
            return '\n'.join(text_content)
            
        except Exception as e:
            logger.error(f"Failed to extract DOCX text from {file_path}: {e}")
            raise

    async def _extract_metadata(self, document: Document, text_content: str) -> Dict[str, Any]:
        """Extract metadata from document"""

        metadata = {
            'extraction_timestamp': datetime.utcnow().isoformat(),
            'content_length': len(text_content),
            'word_count': len(text_content.split()),
            'line_count': len(text_content.split('\n')),
            'language': 'en',  # TODO: Add language detection
            'encoding': 'utf-8'
        }

        # Add file-specific metadata
        if document.mime_type == 'pdf':
            metadata.update(await self._extract_pdf_metadata(document.file_path))
        elif document.mime_type in ['doc', 'docx']:
            metadata.update(await self._extract_docx_metadata(document.file_path))

        return metadata

    async def _extract_pdf_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract PDF-specific metadata"""
        try:
            import PyPDF2

            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                metadata = pdf_reader.metadata or {}

                return {
                    'page_count': len(pdf_reader.pages),
                    'title': metadata.get('/Title', ''),
                    'author': metadata.get('/Author', ''),
                    'subject': metadata.get('/Subject', ''),
                    'creator': metadata.get('/Creator', ''),
                    'producer': metadata.get('/Producer', ''),
                    'creation_date': str(metadata.get('/CreationDate', '')),
                    'modification_date': str(metadata.get('/ModDate', ''))
                }
        except Exception as e:
            logger.warning(f"Failed to extract PDF metadata: {e}")
            return {}

    async def _extract_docx_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract DOCX-specific metadata"""
        try:
            from docx import Document as DocxDocument

            doc = DocxDocument(file_path)
            props = doc.core_properties

            return {
                'title': props.title or '',
                'author': props.author or '',
                'subject': props.subject or '',
                'keywords': props.keywords or '',
                'comments': props.comments or '',
                'category': props.category or '',
                'created': props.created.isoformat() if props.created else '',
                'modified': props.modified.isoformat() if props.modified else '',
                'last_modified_by': props.last_modified_by or '',
                'revision': props.revision or 0
            }
        except Exception as e:
            logger.warning(f"Failed to extract DOCX metadata: {e}")
            return {}

    async def _save_chunks(self, db: Session, document: Document, chunks: List[Dict[str, Any]]):
        """Save document chunks to database - FIXED: Removed await"""

        for i, chunk_data in enumerate(chunks):
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=i,
                chunk_id=chunk_data['chunk_id'],
                text=chunk_data['text'],
                start_char=chunk_data['start_char'],
                end_char=chunk_data['end_char'],
                character_count=len(chunk_data['text']),
                token_count=len(chunk_data['text'].split()),
                quality_score=chunk_data.get('quality_score'),
                section_title=chunk_data.get('section_title'),
                section_level=chunk_data.get('section_level'),
                metadata=chunk_data.get('metadata', {})
            )
            db.add(chunk)

        # FIXED: Removed await - commit is synchronous and handled by context manager
        logger.info(f"Saved {len(chunks)} chunks for document {document.id}")

    async def _calculate_quality_score(self, document: Document, chunks: List[Dict[str, Any]]) -> float:
        """Calculate overall quality score for document"""

        if not chunks:
            return 0.0

        # Simple quality scoring based on various factors
        scores = []

        # Content length score (prefer documents with reasonable content)
        content_length = document.total_characters
        if content_length > 100:
            length_score = min(content_length / 10000, 1.0)  # Cap at 10k chars
        else:
            length_score = content_length / 100  # Penalize very short documents
        scores.append(length_score)

        # Chunk quality scores
        chunk_scores = [chunk.get('quality_score', 0.5) for chunk in chunks]
        if chunk_scores:
            avg_chunk_score = sum(chunk_scores) / len(chunk_scores)
            scores.append(avg_chunk_score)

        # Text extraction confidence (if available)
        if document.extraction_confidence:
            scores.append(document.extraction_confidence)

        # Calculate weighted average
        return sum(scores) / len(scores) if scores else 0.5

    async def _update_batch_progress(self, db: Session, batch_id: str, completed: bool = False, failed: bool = False):
        """Update batch progress - FIXED: Removed await from sync operations"""

        batch = db.query(UploadBatch).filter(UploadBatch.batch_id == batch_id).first()
        if not batch:
            return

        if completed:
            batch.completed_files += 1
        elif failed:
            batch.failed_files += 1

        # Check if batch is complete
        total_processed = batch.completed_files + batch.failed_files
        if total_processed >= batch.total_files:
            batch.status = "completed"
            batch.completed_at = datetime.utcnow()

            # Calculate total chunks created
            from sqlalchemy import func
            result = db.execute(
                db.query(func.sum(Document.total_chunks))
                .filter(Document.upload_batch_id == batch_id)
            )
            batch.total_chunks_created = result.scalar() or 0

        # Commit handled by context manager

    async def get_upload_batch_status(self, batch_id: str) -> Optional[UploadBatchInfo]:
        """Get upload batch status with proper session management"""

        try:
            with self.get_db_session() as db:
                batch = db.query(UploadBatch).filter(UploadBatch.batch_id == batch_id).first()
                if not batch:
                    return None

                return UploadBatchInfo.model_validate(batch)
        except Exception as e:
            logger.error(f"Error getting batch status: {e}")
            return None

    async def get_document_info(self, document_id: int) -> Optional[DocumentInfo]:
        """Get document information with proper session management"""

        try:
            with self.get_db_session() as db:
                document = db.query(Document).filter(Document.id == document_id).first()
                if not document:
                    return None

                return DocumentInfo.model_validate(document)
        except Exception as e:
            logger.error(f"Error getting document info: {e}")
            return None

    async def list_documents(
        self,
        customer_id: str,
        source_id: Optional[str] = None,
        status: Optional[DocumentStatus] = None,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False
    ) -> List[DocumentInfo]:
        """List documents for customer with proper session management"""

        try:
            with self.get_db_session() as db:
                query = db.query(Document).filter(Document.customer_id == customer_id)

                # Filter out deleted documents by default
                if not include_deleted:
                    query = query.filter(Document.status != DocumentStatus.DELETED)

                if source_id:
                    query = query.filter(Document.source_id == source_id)

                if status:
                    query = query.filter(Document.status == status)

                query = query.order_by(Document.created_at.desc()).offset(offset).limit(limit)

                documents = query.all()
                return [DocumentInfo.model_validate(doc) for doc in documents]
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []

    async def delete_document(self, document_id: int, customer_id: str) -> bool:
        """Soft delete document - mark as deleted but keep file on disk"""

        try:
            with self.get_db_session() as db:
                document = db.query(Document).filter(Document.id == document_id).first()
                if not document or document.customer_id != customer_id:
                    return False

                # Check if already deleted
                if document.status == DocumentStatus.DELETED:
                    logger.warning(f"Document {document_id} is already deleted")
                    return True

                try:
                    # Soft delete - keep file on disk but mark as deleted
                    document.status = DocumentStatus.DELETED
                    document.processing_completed_at = datetime.utcnow()  # Mark deletion time
                    # Commit handled by context manager

                    logger.info(f"Soft deleted document {document_id} (file preserved)")
                    return True

                except Exception as e:
                    logger.error(f"Failed to soft delete document {document_id}: {e}")
                    return False
        except Exception as e:
            logger.error(f"Error in delete_document: {e}")
            return False
    
    # ========================================================================
    # Synchronous Helper Methods for Celery Workers
    # ========================================================================
    
    def _extract_text_content_sync(self, document: Document) -> str:
        """Extract text content from document (sync version for Celery)"""
        file_path = Path(document.file_path)
        
        if document.mime_type == 'txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        elif document.mime_type == 'pdf':
            return self._extract_pdf_text_sync(file_path)
        
        elif document.mime_type in ['docx', 'doc']:
            return self._extract_docx_text_sync(file_path)
        
        else:
            # For unsupported types, try to read as text
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except UnicodeDecodeError:
                # Try with different encoding
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
    
    def _extract_pdf_text_sync(self, file_path: Path) -> str:
        """Extract text from PDF file (sync version)"""
        try:
            import PyPDF2
            
            text_content = []
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text_content.append(page.extract_text())
            
            return '\n'.join(text_content)
            
        except Exception as e:
            logger.error(f"Failed to extract PDF text from {file_path}: {e}")
            raise
    
    def _extract_docx_text_sync(self, file_path: Path) -> str:
        """Extract text from DOCX file (sync version)"""
        try:
            from docx import Document as DocxDocument
            
            doc = DocxDocument(file_path)
            text_content = []
            
            for paragraph in doc.paragraphs:
                text_content.append(paragraph.text)
            
            return '\n'.join(text_content)
            
        except Exception as e:
            logger.error(f"Failed to extract DOCX text from {file_path}: {e}")
            raise
    
    def _extract_metadata_sync(self, document: Document, text_content: str) -> Dict[str, Any]:
        """Extract metadata from document (sync version)"""
        metadata = {
            'extraction_timestamp': datetime.utcnow().isoformat(),
            'content_length': len(text_content),
            'word_count': len(text_content.split()),
            'line_count': len(text_content.split('\n')),
            'language': 'en',  # TODO: Add language detection
            'encoding': 'utf-8'
        }
        
        # Add file-specific metadata
        if document.mime_type == 'pdf':
            metadata.update(self._extract_pdf_metadata_sync(document.file_path))
        elif document.mime_type in ['doc', 'docx']:
            metadata.update(self._extract_docx_metadata_sync(document.file_path))
        
        return metadata
    
    def _extract_pdf_metadata_sync(self, file_path: Path) -> Dict[str, Any]:
        """Extract PDF metadata (sync version)"""
        try:
            import PyPDF2
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                info = pdf_reader.metadata
                
                return {
                    'pages': len(pdf_reader.pages),
                    'title': info.get('/Title', ''),
                    'author': info.get('/Author', ''),
                    'subject': info.get('/Subject', ''),
                    'creator': info.get('/Creator', ''),
                }
        except:
            return {'pages': 0}
    
    def _extract_docx_metadata_sync(self, file_path: Path) -> Dict[str, Any]:
        """Extract DOCX metadata (sync version)"""
        try:
            from docx import Document as DocxDocument
            
            doc = DocxDocument(file_path)
            props = doc.core_properties
            
            return {
                'title': props.title or '',
                'author': props.author or '',
                'subject': props.subject or '',
                'created': props.created.isoformat() if props.created else '',
            }
        except:
            return {}
    
    def _chunk_document_sync(
        self, 
        text: str, 
        strategy: ChunkingStrategy, 
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Chunk document using specified strategy (sync version)"""
        logger.info(f"Chunking document with strategy: {strategy}")
        
        # Get appropriate chunker
        if strategy == ChunkingStrategy.SEMANTIC:
            chunker = SemanticChunker(config)
        elif strategy == ChunkingStrategy.FIXED:
            chunker = FixedChunker(config)
        elif strategy == ChunkingStrategy.HIERARCHICAL:
            chunker = HierarchicalChunker(config)
        else:
            logger.warning(f"Unknown or unimplemented strategy {strategy}, using fixed")
            chunker = FixedChunker(config)
        
        # Chunkers are async; run them in a dedicated event loop for sync processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            chunks = loop.run_until_complete(chunker.chunk_text(text))
        finally:
            loop.close()
        
        return chunks
    
    def _save_chunks_sync(self, db: Session, document: Document, chunks: List[Dict[str, Any]]):
        """Save chunks to database (sync version) - gracefully handles duplicates"""        
        # First, check which chunks already exist in the database (from other documents)
        chunk_ids = [chunk['chunk_id'] for chunk in chunks]
        existing_chunk_ids = set(
            row[0] for row in 
            db.query(DocumentChunk.chunk_id)
            .filter(DocumentChunk.chunk_id.in_(chunk_ids))
            .all()
        )
        
        duplicate_count = 0
        saved_count = 0
        seen_in_batch = set()  # Track chunk IDs within this batch
        
        # Only insert chunks that don't already exist (across documents or within batch)
        for idx, chunk_data in enumerate(chunks):
            chunk_id = chunk_data['chunk_id']
            
            # Check for duplicates from other documents in the database
            if chunk_id in existing_chunk_ids:
                duplicate_count += 1
                logger.info(
                    f"[DOC-{document.id}] Skipping duplicate chunk {chunk_id} "
                    f"(already exists in index from another document)"
                )
                continue
            
            # Check for duplicates within this batch
            if chunk_id in seen_in_batch:
                duplicate_count += 1
                logger.warning(
                    f"[DOC-{document.id}] Skipping duplicate chunk {chunk_id} "
                    f"(duplicate within same document - chunker generated same ID twice)"
                )
                continue
            
            # Mark this chunk ID as seen
            seen_in_batch.add(chunk_id)
            
            # Insert new chunk
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=idx,
                chunk_id=chunk_id,
                text=chunk_data['text'],
                start_char=chunk_data['start_char'],
                end_char=chunk_data['end_char'],
                character_count=chunk_data['character_count'],
                token_count=chunk_data['token_count'],
                quality_score=chunk_data.get('quality_score'),
                section_title=chunk_data.get('section_title'),
                section_level=chunk_data.get('section_level'),
                chunk_metadata=chunk_data.get('metadata', {})
            )
            db.add(chunk)
            saved_count += 1
        
        # Flush all new chunks at once
        db.flush()
        
        # Update document with duplicate count
        document.duplicate_chunks_count = duplicate_count
        logger.info(
            f"[DOC-{document.id}] Saved {saved_count} chunks, "
            f"skipped {duplicate_count} duplicates (from database and within batch)"
        )
    
    def _generate_embeddings_sync(self, document_id: int, db: Session):
        """Generate embeddings for document chunks (sync version)"""
        # Get document to retrieve company_hr_dataset for proper vector index
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        # Create VectorService with company-specific index
        vector_service = VectorService(company_hr_dataset=document.company_hr_dataset)
        logger.info(f"[DOC-{document_id}] Using vector index for company: {document.company_hr_dataset}")
        
        # Note: VectorService.generate_embeddings_for_document uses sync DB access
        # despite being declared async. We need to handle it properly.
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(vector_service.generate_embeddings_for_document(document_id))
        finally:
            loop.close()
    
    def _calculate_quality_score_sync(self, document: Document, chunks: List[Dict[str, Any]]) -> float:
        """Calculate quality score for processed document (sync version)"""
        scores = []
        
        # Average chunk quality
        chunk_qualities = [c.get('quality_score', 0.8) for c in chunks]
        if chunk_qualities:
            scores.append(sum(chunk_qualities) / len(chunk_qualities))
        
        # Content coverage (ratio of extracted to total characters)
        if document.file_size > 0:
            coverage = min(1.0, document.total_characters / (document.file_size * 0.7))
            scores.append(coverage)
        
        # Chunk size distribution (penalize very small or very large chunks)
        chunk_sizes = [c['character_count'] for c in chunks]
        if chunk_sizes:
            avg_size = sum(chunk_sizes) / len(chunk_sizes)
            target_size = 1024  # Ideal chunk size
            size_score = 1.0 - min(1.0, abs(avg_size - target_size) / target_size)
            scores.append(size_score)
        
        # Calculate weighted average
        return sum(scores) / len(scores) if scores else 0.5
    
    def _update_batch_progress_sync(self, db: Session, batch_id: str, completed: bool = False, failed: bool = False):
        """Update batch progress (sync version)"""
        batch = db.query(UploadBatch).filter(UploadBatch.batch_id == batch_id).first()
        if not batch:
            return
        
        if completed:
            batch.completed_files += 1
        elif failed:
            batch.failed_files += 1
        
        # Check if batch is complete
        total_processed = batch.completed_files + batch.failed_files
        if total_processed >= batch.total_files:
            batch.status = "completed"
            batch.completed_at = datetime.utcnow()
        
        # Flush changes (commit handled by context manager)
        db.flush()
