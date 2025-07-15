"""
Enhanced document processing service with async support and validation
"""
import asyncio
import hashlib
import mimetypes
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from uuid import uuid4
import aiofiles
import fitz  # PyMuPDF
import spacy
from docx import Document as DocxDocument
from sentence_transformers import SentenceTransformer
import nltk
from nltk.tokenize import sent_tokenize
import pytesseract
from PIL import Image
import io

from app.core.config import settings
from app.core.exceptions import DocumentProcessingError, ValidationError
from app.core.logging import get_logger, log_function_call
from app.services.models import DocumentChunk, DocumentMetadata, ProcessingResult

logger = get_logger(__name__)

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)


class DocumentValidator:
    """Document validation service"""
    
    @staticmethod
    def validate_file_size(file_size: int) -> None:
        """Validate file size"""
        max_size = settings.processing.max_file_size_mb * 1024 * 1024
        if file_size > max_size:
            raise ValidationError(
                f"File size ({file_size / 1024 / 1024:.1f}MB) exceeds maximum allowed size ({settings.processing.max_file_size_mb}MB)",
                details={"file_size_mb": file_size / 1024 / 1024, "max_size_mb": settings.processing.max_file_size_mb}
            )
    
    @staticmethod
    def validate_file_type(filename: str, content_type: Optional[str] = None) -> str:
        """Validate and return file extension"""
        file_path = Path(filename)
        extension = file_path.suffix.lower()
        
        if extension not in settings.processing.supported_formats:
            raise ValidationError(
                f"Unsupported file format: {extension}",
                details={"extension": extension, "supported_formats": settings.processing.supported_formats}
            )
        
        # Additional MIME type validation
        if content_type:
            expected_mime_types = {
                '.pdf': 'application/pdf',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.doc': 'application/msword',
                '.txt': 'text/plain'
            }
            
            expected_mime = expected_mime_types.get(extension)
            if expected_mime and content_type != expected_mime:
                logger.warning_ctx(
                    "MIME type mismatch",
                    expected=expected_mime,
                    actual=content_type,
                    filename=filename
                )
        
        return extension
    
    @staticmethod
    def validate_content(content: str) -> None:
        """Validate extracted content"""
        if not content or not content.strip():
            raise ValidationError("Document contains no extractable text")
        
        if len(content.strip()) < 50:
            raise ValidationError(
                "Document content is too short",
                details={"content_length": len(content.strip()), "min_length": 50}
            )


class DocumentProcessor:
    """Enhanced document processing service"""
    
    def __init__(self):
        self.validator = DocumentValidator()
        self._initialize_models()
        self._processing_stats = {
            "documents_processed": 0,
            "total_chunks": 0,
            "errors": 0
        }
    
    def _initialize_models(self):
        """Initialize NLP models"""
        try:
            # Load spaCy model
            self.nlp = spacy.load(
                settings.processing.spacy_model,
                disable=["parser", "lemmatizer", "ner", "attribute_ruler", "tagger"]
            )
            self.nlp.add_pipe('sentencizer')
            
            # Load embedding model
            self.embedding_model = SentenceTransformer(
                settings.processing.embedding_model,
                device=settings.processing.device
            )
            
            logger.info_ctx(
                "NLP models initialized successfully",
                spacy_model=settings.processing.spacy_model,
                embedding_model=settings.processing.embedding_model,
                device=settings.processing.device
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize NLP models: {e}", exc_info=True)
            raise DocumentProcessingError(
                "Failed to initialize document processing models",
                details={"error": str(e)}
            )
    
    async def process_file(
        self,
        file_path: Union[str, Path],
        filename: str,
        content_type: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> ProcessingResult:
        """Process a document file asynchronously"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            file_path = Path(file_path)
            
            # Validate file
            file_size = file_path.stat().st_size
            self.validator.validate_file_size(file_size)
            extension = self.validator.validate_file_type(filename, content_type)
            
            # Generate document ID and metadata
            document_id = str(uuid4())
            file_hash = await self._calculate_file_hash(file_path)
            
            metadata = DocumentMetadata(
                document_id=document_id,
                filename=filename,
                file_size=file_size,
                file_hash=file_hash,
                content_type=content_type,
                user_id=user_id,
                processed_at=datetime.utcnow()
            )
            
            # Extract text based on file type
            content = await self._extract_text(file_path, extension)
            self.validator.validate_content(content)
            
            # Create chunks
            chunks = await self._create_chunks(content, metadata)
            
            # Generate embeddings
            chunks_with_embeddings = await self._generate_embeddings(chunks)
            
            # Update stats
            self._processing_stats["documents_processed"] += 1
            self._processing_stats["total_chunks"] += len(chunks_with_embeddings)
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            result = ProcessingResult(
                document_id=document_id,
                metadata=metadata,
                chunks=chunks_with_embeddings,
                processing_time=processing_time,
                chunk_count=len(chunks_with_embeddings)
            )
            
            log_function_call(
                "process_file",
                args={"filename": filename, "user_id": user_id},
                result={"chunks": len(chunks_with_embeddings)},
                duration=processing_time
            )
            
            logger.info_ctx(
                "Document processed successfully",
                document_id=document_id,
                filename=filename,
                chunks=len(chunks_with_embeddings),
                processing_time=processing_time
            )
            
            return result
            
        except Exception as e:
            self._processing_stats["errors"] += 1
            logger.error_ctx(
                f"Document processing failed: {str(e)}",
                filename=filename,
                error_type=type(e).__name__
            )
            
            if isinstance(e, (ValidationError, DocumentProcessingError)):
                raise
            else:
                raise DocumentProcessingError(
                    "Document processing failed",
                    details={"filename": filename, "error": str(e)}
                )
    
    async def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file"""
        hash_sha256 = hashlib.sha256()
        
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                hash_sha256.update(chunk)
        
        return hash_sha256.hexdigest()
    
    async def _extract_text(self, file_path: Path, extension: str) -> str:
        """Extract text from document based on file type"""
        try:
            if extension == '.pdf':
                return await self._extract_pdf_text(file_path)
            elif extension in ['.docx', '.doc']:
                return await self._extract_docx_text(file_path)
            elif extension == '.txt':
                return await self._extract_txt_text(file_path)
            else:
                raise DocumentProcessingError(f"Unsupported file extension: {extension}")
                
        except Exception as e:
            logger.error(f"Text extraction failed for {file_path}: {e}")
            raise DocumentProcessingError(
                f"Failed to extract text from {extension} file",
                details={"file_path": str(file_path), "error": str(e)}
            )
    
    async def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF file"""
        def extract_sync():
            text_content = []
            doc = fitz.open(str(file_path))
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                
                if text.strip():
                    text_content.append(text)
                else:
                    # Try OCR for image-based pages
                    try:
                        pix = page.get_pixmap()
                        img_data = pix.tobytes("png")
                        img = Image.open(io.BytesIO(img_data))
                        ocr_text = pytesseract.image_to_string(img, lang='rus+eng')
                        if ocr_text.strip():
                            text_content.append(ocr_text)
                    except Exception as ocr_error:
                        logger.warning(f"OCR failed for page {page_num}: {ocr_error}")
            
            doc.close()
            return '\n\n'.join(text_content)
        
        # Run in thread to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, extract_sync)
    
    async def _extract_docx_text(self, file_path: Path) -> str:
        """Extract text from DOCX file"""
        def extract_sync():
            doc = DocxDocument(str(file_path))
            paragraphs = [paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()]
            return '\n\n'.join(paragraphs)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, extract_sync)
    
    async def _extract_txt_text(self, file_path: Path) -> str:
        """Extract text from TXT file"""
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            return await f.read()
    
    async def _create_chunks(self, content: str, metadata: DocumentMetadata) -> List[DocumentChunk]:
        """Create text chunks from content"""
        def chunk_sync():
            # Clean and normalize text
            content_clean = self._clean_text(content)
            
            # Use spaCy for sentence segmentation
            doc = self.nlp(content_clean)
            sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
            
            chunks = []
            current_chunk = ""
            current_size = 0
            chunk_index = 0
            
            for sentence in sentences:
                sentence_size = len(sentence.split())
                
                # If adding this sentence would exceed chunk size, create a chunk
                if (current_size + sentence_size > settings.processing.chunk_size and 
                    current_size >= settings.processing.min_chunk_size):
                    
                    if current_chunk.strip():
                        chunks.append(self._create_chunk(
                            current_chunk.strip(),
                            chunk_index,
                            metadata
                        ))
                        chunk_index += 1
                    
                    # Start new chunk with overlap
                    if settings.processing.chunk_overlap > 0:
                        overlap_sentences = sentences[max(0, len(chunks) - settings.processing.chunk_overlap//50):]
                        current_chunk = ' '.join(overlap_sentences[-3:]) + " " + sentence
                        current_size = len(current_chunk.split())
                    else:
                        current_chunk = sentence
                        current_size = sentence_size
                else:
                    current_chunk += " " + sentence if current_chunk else sentence
                    current_size += sentence_size
            
            # Add the last chunk
            if current_chunk.strip() and len(current_chunk.split()) >= settings.processing.min_chunk_size:
                chunks.append(self._create_chunk(
                    current_chunk.strip(),
                    chunk_index,
                    metadata
                ))
            
            return chunks
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, chunk_sync)
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Remove special characters but keep punctuation
        import re
        text = re.sub(r'[^\w\s\.\,\!\?\:\;\-\(\)\"\']+', ' ', text)
        
        # Remove excessive punctuation
        text = re.sub(r'\.{3,}', '...', text)
        text = re.sub(r'[\-]{2,}', '--', text)
        
        return text.strip()
    
    def _create_chunk(self, text: str, index: int, metadata: DocumentMetadata) -> DocumentChunk:
        """Create a document chunk"""
        chunk_id = f"{metadata.document_id}_chunk_{index}"
        
        return DocumentChunk(
            id=chunk_id,
            text=text,
            index=index,
            document_id=metadata.document_id,
            metadata={
                "filename": metadata.filename,
                "file_size": metadata.file_size,
                "chunk_index": index,
                "word_count": len(text.split()),
                "char_count": len(text),
                "processed_at": metadata.processed_at.isoformat(),
                "user_id": metadata.user_id
            }
        )
    
    async def _generate_embeddings(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Generate embeddings for chunks"""
        if not chunks:
            return chunks
        
        def generate_sync():
            texts = [chunk.text for chunk in chunks]
            
            # Generate embeddings in batches
            batch_size = settings.processing.batch_size
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                batch_embeddings = self.embedding_model.encode(
                    batch_texts,
                    show_progress_bar=False,
                    normalize_embeddings=True
                )
                all_embeddings.extend(batch_embeddings.tolist())
            
            # Add embeddings to chunks
            for chunk, embedding in zip(chunks, all_embeddings):
                chunk.embedding = embedding
            
            return chunks
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, generate_sync)
    
    async def process_multiple_files(
        self,
        files: List[Dict[str, Any]],
        user_id: Optional[str] = None
    ) -> List[ProcessingResult]:
        """Process multiple files concurrently"""
        semaphore = asyncio.Semaphore(settings.processing.max_workers)
        
        async def process_single_file(file_info):
            async with semaphore:
                return await self.process_file(
                    file_path=file_info['path'],
                    filename=file_info['filename'],
                    content_type=file_info.get('content_type'),
                    user_id=user_id
                )
        
        tasks = [process_single_file(file_info) for file_info in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and log them
        successful_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error_ctx(
                    f"Failed to process file {files[i]['filename']}: {result}",
                    filename=files[i]['filename'],
                    error_type=type(result).__name__
                )
            else:
                successful_results.append(result)
        
        return successful_results
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return self._processing_stats.copy()
    
    async def cleanup_temp_files(self, temp_dir: str):
        """Clean up temporary files"""
        try:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info_ctx("Temporary files cleaned up", temp_dir=temp_dir)
        except Exception as e:
            logger.warning_ctx("Failed to cleanup temp files", error=str(e), temp_dir=temp_dir)


# Global processor instance
document_processor = DocumentProcessor()