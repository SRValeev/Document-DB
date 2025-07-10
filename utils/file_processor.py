#utils/file_processor.py
import os
import re
import json
import fitz
import spacy
import pytesseract
import logging
from PIL import Image
from io import BytesIO
from datetime import datetime
from docx import Document
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from utils.helpers import load_config, normalize_text, generate_unique_id

class FileProcessor:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        try:
            self.nlp = spacy.load(config['processing']['spacy_model'])
            self.embedding_model = SentenceTransformer(
                config['processing']['embedding_model'],
                device=config['processing']['device']
            )
            self.logger.info("Models loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading models: {str(e)}", exc_info=True)
            raise

        self.header_pattern = re.compile(
            r'^(Глава|Раздел|Часть|Параграф)\s+\d+[.:]?\s+', 
            re.IGNORECASE
        )
        self.subheader_pattern = re.compile(r'^\d+\.\d+\.\s+', re.IGNORECASE)
        self.global_headers = {}
        self.file_index = {}
        self.min_similarity = config['processing']['min_similarity']
        self.use_ocr = config['processing'].get('use_ocr', False)

    def process_file(self, file_path):
        if not hasattr(self, 'nlp') or not hasattr(self, 'embedding_model'):
            self.logger.error("Models not loaded")
            return []
            
        file_id = generate_unique_id()
        self.file_index[file_id] = file_path
        
        try:
            if file_path.lower().endswith('.pdf'):
                return self._process_pdf(file_path, file_id)
            elif file_path.lower().endswith(('.doc', '.docx')):
                return self._process_docx(file_path, file_id)
            else:
                self.logger.warning(f"Unsupported file format: {file_path}")
                return []
        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {str(e)}", exc_info=True)
            return []

    def _process_pdf(self, file_path, file_id):
        chunks = []
        current_chapter = ""
        current_section = ""
        
        try:
            with fitz.open(file_path) as doc:
                try:
                    toc = doc.get_toc()
                except Exception as e:
                    self.logger.warning(f"Could not extract TOC: {str(e)}")
                    toc = []
                
                for page_num in tqdm(range(len(doc)), desc=f"Processing {file_id}"):
                    page = doc.load_page(page_num)
                    
                    # Обработка оглавления
                    for item in toc:
                        if item[2] == page_num + 1:
                            if item[0] == 1:
                                current_chapter = normalize_text(item[1])
                            elif item[0] == 2:
                                current_section = normalize_text(item[1])
                    
                    # Обработка изображений (OCR)
                    if self.use_ocr:
                        image_list = page.get_images(full=True)
                        for img_index, img in enumerate(image_list, 1):
                            try:
                                base_image = doc.extract_image(img[0])
                                image = Image.open(BytesIO(base_image["image"]))
                                ocr_text = pytesseract.image_to_string(image, lang='rus+eng')
                                if ocr_text.strip():
                                    chunks.append(self._create_chunk(
                                        f"Изображение {img_index}: {normalize_text(ocr_text)}",
                                        file_id, 
                                        page_num,
                                        "image",
                                        current_chapter,
                                        current_section
                                    ))
                            except Exception as e:
                                self.logger.warning(f"OCR failed: {str(e)}")
                    
                    # Обработка текста
                    text = page.get_text("text")
                    if text.strip():
                        chunks.extend(self._split_text_into_chunks(
                            text, 
                            file_id, 
                            page_num,
                            "text",
                            current_chapter,
                            current_section
                        ))
            
            self.logger.info(f"Processed PDF: {file_path}, chunks: {len(chunks)}")
            return chunks
        
        except Exception as e:
            self.logger.error(f"PDF processing failed: {str(e)}", exc_info=True)
            return []

    def _process_docx(self, file_path, file_id):
        chunks = []
        current_page = 0
        current_chapter = ""
        current_section = ""
        
        try:
            doc = Document(file_path)
            full_text = ""
            
            for para in doc.paragraphs:
                text = normalize_text(para.text.strip())
                if not text:
                    continue
                    
                style_name = para.style.name.lower() if para.style else ""
                
                if 'heading 1' in style_name:
                    current_chapter = text
                elif 'heading 2' in style_name:
                    current_section = text
                
                full_text += text + " "
            
            if full_text.strip():
                chunks.extend(self._split_text_into_chunks(
                    full_text, 
                    file_id, 
                    current_page,
                    "text",
                    current_chapter,
                    current_section
                ))
            
            # Обработка таблиц
            for table in doc.tables:
                table_text = "ТАБЛИЦА: "
                for row in table.rows:
                    for cell in row.cells:
                        table_text += cell.text + " | "
                chunks.append(self._create_chunk(
                    table_text, 
                    file_id, 
                    current_page,
                    "table",
                    current_chapter,
                    current_section
                ))
            
            self.logger.info(f"Processed DOCX: {file_path}, chunks: {len(chunks)}")
            return chunks
            
        except Exception as e:
            self.logger.error(f"DOCX processing failed: {str(e)}", exc_info=True)
            return []

    def _split_text_into_chunks(self, text, file_id, page, content_type, chapter, section):
        words = text.split()
        chunk_size = self.config['processing']['chunk_size']
        chunk_overlap = self.config['processing']['chunk_overlap']
        chunks = []
        
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_text = ' '.join(words[start:end])
            
            context = ""
            if chapter:
                context += f"Раздел: {chapter}. "
            if section:
                context += f"Подраздел: {section}. "
                
            full_text = context + chunk_text
            
            chunks.append(self._create_chunk(
                full_text, 
                file_id, 
                page,
                content_type,
                chapter,
                section
            ))
            start += (chunk_size - chunk_overlap)
        
        return chunks

    def _create_chunk(self, text, file_path, page, content_type, chapter, section):
        chunk_id = generate_unique_id()
        chunk = {
            "id": chunk_id,
            "text": text,
            "metadata": {
                "file_id": file_path,
                "page": page,
                "type": content_type,
                "chapter": chapter,
                "section": section,
                "source": os.path.basename(file_path),
                "processing_date": datetime.now().strftime('%Y-%m-%d'),
                "text_length": len(text)
            }
        }
        return chunk

    def vectorize_chunks(self, chunks):
        """Векторизация чанков"""
        try:
            texts = [chunk['text'] for chunk in chunks]
            embeddings = []
            
            batch_size = self.config['performance']['embedding_batch_size']
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i+batch_size]
                embeddings.extend(self.embedding_model.encode(batch))
            
            for i, chunk in enumerate(chunks):
                chunk['embedding'] = embeddings[i].tolist()
            
            self.logger.info(f"Vectorized {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            self.logger.error(f"Vectorization failed: {str(e)}", exc_info=True)
            return []

    def save_chunks(self, chunks, output_file):
        chunks = self.vectorize_chunks(chunks)
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Saved chunks to {output_file}")
        except Exception as e:
            self.logger.error(f"Failed to save chunks: {str(e)}", exc_info=True)

    def create_global_index(self, output_dir):
        try:
            index_file = os.path.join(output_dir, "global_index.json")
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "file_index": self.file_index,
                    "global_headers": self.global_headers
                }, f, ensure_ascii=False, indent=4)
            self.logger.info("Created global index")
        except Exception as e:
            self.logger.error(f"Failed to create index: {str(e)}", exc_info=True)