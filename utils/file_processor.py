# file_processor.py
import os
import re
import json
import fitz
import spacy
import camelot
import logging
import tempfile
import uuid
import numpy as np
import pytesseract
from PIL import Image
from io import BytesIO
from datetime import datetime
from docx import Document
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from .helpers import load_config, normalize_text, windows_path, generate_unique_id

class FileProcessor:
    def __init__(self, config):
        self.config = config
        self.perf_config = config.get('performance', {})
        
        try:
            self.nlp = spacy.load(config['processing']['spacy_model'])
        except Exception as e:
            logging.error(f"Ошибка загрузки модели Spacy: {str(e)}")
            self.nlp = None
        
        # Настройки производительности
        device = self.perf_config.get('device', 'cpu')
        low_memory = self.perf_config.get('low_memory_mode', True)
        
        try:
            self.embedding_model = SentenceTransformer(
                config['processing']['embedding_model'],
                device=device
            )
            
            # Оптимизации для режима экономии памяти
            if low_memory:
                self.embedding_model.max_seq_length = 128
                self.embedding_model._first_module().max_seq_length = 128
        except Exception as e:
            logging.error(f"Ошибка загрузки модели эмбеддингов: {str(e)}")
            self.embedding_model = None

        self.header_pattern = re.compile(
            r'^(Глава|Раздел|Часть|Параграф)\s+\d+[.:]?\s+', 
            re.IGNORECASE
        )
        self.subheader_pattern = re.compile(r'^\d+\.\d+\.\s+', re.IGNORECASE)
        self.global_headers = {}
        self.file_index = {}
        self.min_similarity = config['processing']['min_similarity']
        self.temp_dir = config['paths']['tempdir']
        self.use_ocr = config['processing'].get('use_ocr', False)
        self.images_dir = config['paths']['images_dir']
        
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.images_dir, exist_ok=True)
        
        self.chunk_index = {}
        self.header_index = {}
        self.section_index = {}
        self.chunk_counter = 1

    def process_file(self, file_path):
        if not self.nlp or not self.embedding_model:
            logging.error("Модели не загружены, обработка невозможна")
            return []
            
        file_id = generate_unique_id()
        self.file_index[file_id] = windows_path(file_path)
        
        if file_path.lower().endswith('.pdf'):
            return self._process_pdf(file_path, file_id)
        elif file_path.lower().endswith(('.doc', '.docx')):
            return self._process_docx(file_path, file_id)
        else:
            raise ValueError(f"Неподдерживаемый формат: {file_path}")

    def _process_pdf(self, file_path, file_id):
        chunks = []
        current_chapter = ""
        current_section = ""
        
        try:
            with fitz.open(file_path) as doc:
                try:
                    toc = doc.get_toc()
                except:
                    toc = []
                    logging.warning(f"Не удалось извлечь оглавление для {file_path}")
                
                for page_num in tqdm(range(len(doc)), desc=f"Обработка {file_id}"):
                    page = doc.load_page(page_num)
                    
                    # Обработка оглавления
                    for item in toc:
                        if item[2] == page_num + 1:
                            if item[0] == 1:
                                current_chapter = normalize_text(item[1])
                            elif item[0] == 2:
                                current_section = normalize_text(item[1])
                    
                    self._register_headers(file_id, page_num, current_chapter, current_section)
                    
                    # Обработка изображений (только если включено в конфиге)
                    if self.use_ocr:
                        image_list = page.get_images(full=True)
                        for img_index, img in enumerate(image_list, 1):
                            xref = img[0]
                            base_image = doc.extract_image(xref)
                            image_bytes = base_image["image"]
                            image = Image.open(BytesIO(image_bytes))
                            
                            # OCR обработка
                            try:
                                ocr_text = pytesseract.image_to_string(image, lang='rus+eng')
                                ocr_text = normalize_text(ocr_text)
                                if ocr_text:
                                    chunks.append(self._create_chunk(
                                        f"Изображение {img_index}: {ocr_text}",
                                        file_id, 
                                        page_num,
                                        "image",
                                        current_chapter,
                                        current_section
                                    ))
                            except Exception as e:
                                logging.error(f"Ошибка OCR: {str(e)}")
                    
                    # Обработка текста
                    blocks = page.get_text("blocks")
                    page_text = ""
                    for block in blocks:
                        if not block[4].strip():
                            continue
                        block_text = normalize_text(block[4].replace('\n', ' '))
                        page_text += block_text + " "
                    
                    # Разбивка на чанки с учетом контекста
                    if page_text:
                        chunks.extend(self._split_text_into_chunks(
                            page_text, 
                            file_id, 
                            page_num,
                            "text",
                            current_chapter,
                            current_section
                        ))
        except Exception as e:
            logging.error(f"Ошибка обработки PDF {file_path}: {str(e)}")
            return []
        
        return chunks

    def _split_text_into_chunks(self, text, file_id, page, content_type, chapter, section):
        """Разбивает текст на чанки с учетом контекста"""
        words = text.split()
        chunk_size = self.config['processing']['chunk_size']
        chunk_overlap = self.config['processing']['chunk_overlap']
        chunks = []
        
        start = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_text = ' '.join(words[start:end])
            
            # Добавляем контекстные заголовки
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

    def _process_docx(self, file_path, file_id):
        doc = Document(file_path)
        chunks = []
        current_page = 0
        current_chapter = ""
        current_section = ""
        paragraph_count = 0
        
        full_text = ""
        for para in doc.paragraphs:
            paragraph_count += 1
            if paragraph_count % 50 == 0:
                current_page += 1
                
            text = normalize_text(para.text.strip())
            if not text:
                continue
                
            content_type = "text"
            style_name = para.style.name.lower() if para.style else ""
            
            if 'heading 1' in style_name:
                current_chapter = text
                content_type = "header"
            elif 'heading 2' in style_name:
                current_section = text
                content_type = "subheader"
                
            self._register_headers(file_id, current_page, current_chapter, current_section)
            full_text += text + " "
        
        # Разбивка на чанки
        if full_text:
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
        
        return chunks

    def _create_chunk(self, text, file_id, page, content_type, chapter, section):
        chunk_id = generate_unique_id()
        
        chunk = {
            "id": chunk_id,
            "text": text,
            "metadata": {
                "file_id": file_id,
                "page": page,
                "type": content_type,
                "chapter": chapter,
                "section": section,
                "source": os.path.basename(self.file_index[file_id]),
                "processing_date": datetime.now().strftime('%Y-%m-%d'),
                "text_length": len(text)
            }
        }
        self.chunk_counter += 1
        return chunk

    def _register_headers(self, file_id, page, chapter, section):
        key = f"{file_id}_{page}"
        self.global_headers[key] = chapter or section

    def vectorize_chunks(self, chunks):
        if not chunks or not self.embedding_model:
            return chunks
            
        texts = [chunk['text'] for chunk in chunks]
        embeddings = []
        
        # Используем настройки производительности из конфига
        batch_size = self.perf_config.get('embedding_batch_size', 8)
        
        for i in tqdm(range(0, len(texts), batch_size), desc="Векторизация"):
            batch = texts[i:i+batch_size]
            try:
                batch_embeddings = self.embedding_model.encode(
                    batch,
                    batch_size=batch_size,
                    convert_to_numpy=True,
                    show_progress_bar=False
                )
                embeddings.extend(batch_embeddings)
            except Exception as e:
                logging.error(f"Ошибка векторизации: {str(e)}")
                # Добавляем нулевые эмбеддинги в случае ошибки
                embeddings.extend([np.zeros(self.config['qdrant']['vector_size'])] * len(batch))
        
        for i, chunk in enumerate(chunks):
            chunk['embedding'] = embeddings[i].tolist()
        
        return chunks

    def save_chunks(self, chunks, output_file):
        chunks = self.vectorize_chunks(chunks)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

    def create_global_index(self, output_dir):
        index_data = {
            "global_headers": self.global_headers,
            "file_index": self.file_index,
            "header_index": self.header_index,
            "section_index": self.section_index,
            "chunk_index": list(self.chunk_index.keys())
        }
        
        index_file = os.path.join(output_dir, "global_index.json")
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=4)
        
        logging.info(f"Создан глобальный индекс с {len(self.chunk_index)} чанками")