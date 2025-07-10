import os
import re
import json
import fitz
import spacy
import pytesseract
import logging
import camelot
import pandas as pd
from pathlib import Path
from PIL import Image
from io import BytesIO
from datetime import datetime
from docx import Document
from tqdm import tqdm
from typing import List, Dict, Optional
from sentence_transformers import SentenceTransformer
from utils.helpers import load_config, normalize_text, generate_unique_id
import warnings

# Игнорируем предупреждения pandas
warnings.filterwarnings('ignore', category=pd.errors.SettingWithCopyWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

class FileProcessor:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Загрузка моделей
        try:
            self.nlp = spacy.load(
                config['processing']['spacy_model'],
                disable=["parser", "lemmatizer", "ner"]  # Упрощаем для скорости
            )
            # Добавляем sentencizer для определения границ предложений
            self.nlp.add_pipe('sentencizer')
            
            self.embedding_model = SentenceTransformer(
                config['processing']['embedding_model'],
                device=config['processing']['device']
            )
            self.logger.info("Модели успешно загружены")
        except Exception as e:
            self.logger.error(f"Ошибка загрузки моделей: {str(e)}", exc_info=True)
            raise

        # Параметры обработки
        self.header_pattern = re.compile(r'^(Глава|Раздел|Часть|Параграф)\s+\d+[.:]?\s+', re.IGNORECASE)
        self.subheader_pattern = re.compile(r'^\d+\.\d+\.\s+', re.IGNORECASE)
        self.min_similarity = config['processing']['min_similarity']
        self.use_ocr = config['processing'].get('use_ocr', False)
        self.extract_tables = config['processing'].get('extract_tables', True)
        self.max_table_size = config['processing'].get('max_table_size', 10)
        self.global_headers = {}
        self.file_index = {}

    def process_file(self, file_path: str) -> List[Dict]:
        """Основной метод обработки файла"""
        if not os.path.exists(file_path):
            self.logger.error(f"Файл не найден: {file_path}")
            return []
        
        # Извлекаем оригинальное имя из названия файла
        file_name = os.path.basename(file_path)
        if '_' in file_name:  # Если имя содержит UUID
            original_name = '_'.join(file_name.split('_')[:-1]) + Path(file_name).suffix
        else:
            original_name = file_name

        file_id = f"{original_name}_{generate_unique_id()}"
        
        try:
            if file_path.lower().endswith('.pdf'):
                return self._process_pdf(file_path, file_id)
            elif file_path.lower().endswith(('.doc', '.docx')):
                return self._process_docx(file_path, file_id)
            else:
                self.logger.warning(f"Неподдерживаемый формат: {file_path}")
                return []
        except Exception as e:
            self.logger.error(f"Ошибка обработки файла: {str(e)}", exc_info=True)
            return []

    def _process_pdf(self, file_path: str, file_id: str) -> List[Dict]:
        chunks = []
        current_chapter = ""
        current_section = ""
        
        try:
            with fitz.open(file_path) as doc:
                toc = doc.get_toc() if hasattr(doc, 'get_toc') else []
                
                # Используем basename для единообразия
                unified_file_id = os.path.basename(file_path)
                
                for page_num in tqdm(range(len(doc)), desc=f"Обработка {os.path.basename(file_path)}"):
                    page = doc.load_page(page_num)
                    text = page.get_text("text")
                    
                    # Обновление разделов из оглавления
                    for item in toc:
                        if item[2] == page_num + 1:
                            if item[0] == 1:
                                current_chapter = normalize_text(item[1])
                            elif item[0] == 2:
                                current_section = normalize_text(item[1])
                    
                    # Обработка текста (используем единый file_id)
                    if text.strip():
                        chunks.extend(self._split_text_into_chunks(
                            text, unified_file_id, page_num, "text", current_chapter, current_section
                        ))
                    
                    # Обработка изображений (OCR)
                    if self.use_ocr:
                        chunks.extend(self._process_pdf_images(page, unified_file_id, page_num))
                    
                    # Извлечение таблиц (передаем тот же file_id)
                    if self.extract_tables:
                        try:
                            tables = self._extract_tables_with_camelot(file_path, page_num+1)
                            for table in tables:
                                table['metadata']['file_id'] = unified_file_id  # Перезаписываем file_id
                            chunks.extend(tables)
                        except Exception as e:
                            self.logger.error(f"Ошибка обработки таблиц на стр. {page_num}: {str(e)}")
            
            return chunks
        except Exception as e:
            self.logger.error(f"Ошибка обработки PDF: {str(e)}", exc_info=True)
            return []

    def _split_text_into_chunks(self, text: str, file_id: str, page: int, content_type: str, 
                              chapter: str, section: str) -> List[Dict]:
        """Умное разделение текста на чанки с контекстом"""
        doc = self.nlp(text)
        chunks = []
        current_chunk = []
        current_length = 0
        chunk_size = self.config['processing']['chunk_size']
        chunk_overlap = self.config['processing']['chunk_overlap']
        min_chunk_size = chunk_size // 3
        
        for sent in doc.sents:
            sent_text = sent.text.strip()
            if not sent_text:
                continue
                
            sent_length = len(sent_text.split())
            
            if current_length + sent_length > chunk_size and current_chunk:
                self._save_chunk(current_chunk, file_id, page, content_type, chapter, section, chunks)
                overlap_size = min(chunk_overlap, len(current_chunk))
                current_chunk = current_chunk[-overlap_size:]
                current_length = sum(len(s.split()) for s in current_chunk)
            
            current_chunk.append(sent_text)
            current_length += sent_length
        
        if current_chunk:
            self._save_chunk(current_chunk, file_id, page, content_type, chapter, section, chunks)
        
        return self._merge_small_chunks(chunks, min_chunk_size)

    def _save_chunk(self, chunk_texts: List[str], file_id: str, page: int, 
                   content_type: str, chapter: str, section: str, chunks: List[Dict]):
        """Сохраняет чанк с метаданными"""
        chunk_text = ' '.join(chunk_texts)
        chunks.append(self._create_chunk(
            text=chunk_text,
            file_id=file_id,
            page=page,
            content_type=content_type,
            chapter=chapter,
            section=section,
            chunk_order=len(chunks)
        ))

    def _merge_small_chunks(self, chunks: List[Dict], min_size: int) -> List[Dict]:
        """Объединяет слишком короткие чанки"""
        if not chunks:
            return []
            
        merged = []
        buffer = [chunks[0]]
        buffer_length = len(chunks[0]['text'].split())
        
        for chunk in chunks[1:]:
            chunk_length = len(chunk['text'].split())
            
            if buffer_length + chunk_length <= min_size:
                buffer.append(chunk)
                buffer_length += chunk_length
            else:
                merged.append(self._merge_chunk_buffer(buffer))
                buffer = [chunk]
                buffer_length = chunk_length
        
        if buffer:
            merged.append(self._merge_chunk_buffer(buffer))
        
        return merged

    def _merge_chunk_buffer(self, chunks: List[Dict]) -> Dict:
        """Объединяет несколько чанков в один"""
        merged_text = ' '.join(chunk['text'] for chunk in chunks)
        first_chunk = chunks[0]
        
        return self._create_chunk(
            text=merged_text,
            file_id=first_chunk['metadata']['file_id'],
            page=first_chunk['metadata']['page'],
            content_type=first_chunk['metadata']['type'],
            chapter=first_chunk['metadata'].get('chapter', ''),
            section=first_chunk['metadata'].get('section', ''),
            chunk_order=first_chunk['metadata']['chunk_order']
        )

    def _extract_tables_with_camelot(self, file_path: str, page: int) -> List[Dict]:
        chunks = []
        try:
            tables = camelot.read_pdf(
                file_path,
                pages=str(page),
                flavor='stream',
                strip_text='\n',
                suppress_stdout=True
            )
            
            for i, table in enumerate(tables):
                try:
                    df = table.df.copy()
                    if df.empty:
                        continue
                        
                    df = df.map(lambda x: str(x).strip() if pd.notna(x) else "")
                    table_text = self._safe_format_table(df, i+1, page)
                    
                    if table_text:
                        # Используем тот же file_id, что и для основного текста
                        file_id = os.path.basename(file_path)
                        chunks.append(self._create_chunk(
                            text=table_text,
                            file_id=file_id,  # Теперь совпадает с основным текстом
                            page=page-1,
                            content_type="table",
                            chapter=f"Таблица {i+1}",
                            section=f"Страница {page}",
                            chunk_order=0
                        ))
                except Exception as e:
                    self.logger.error(f"Ошибка обработки таблицы {i+1}: {str(e)}")
        
        except Exception as e:
            self.logger.error(f"Ошибка извлечения таблиц: {str(e)}")
        
        return chunks

    def _safe_format_table(self, df: pd.DataFrame, table_num: int, page_num: int) -> str:
        """Безопасное форматирование таблицы в Markdown"""
        try:
            if len(df) > self.max_table_size:
                df = df.head(self.max_table_size).copy()
                ellipsis_row = pd.Series(["..."] * len(df.columns), index=df.columns)
                df = pd.concat([df, ellipsis_row.to_frame().T])
            
            headers = [str(col).strip() for col in df.columns]
            rows = []
            
            for _, row in df.iterrows():
                rows.append([str(val).strip() if pd.notna(val) else "" for val in row.values])
            
            header_line = "| " + " | ".join(headers) + " |"
            separator = "| " + " | ".join(["---"] * len(headers)) + " |"
            body_lines = ["| " + " | ".join(row) + " |" for row in rows]
            
            return (
                f"Таблица {table_num} (страница {page_num}):\n" +
                header_line + "\n" +
                separator + "\n" +
                "\n".join(body_lines)
            )
        except Exception as e:
            self.logger.error(f"Ошибка форматирования таблицы: {str(e)}")
            return f"Не удалось обработать таблицу {table_num}. Текст:\n{df.to_string()}"

    def _process_pdf_images(self, page, file_id: str, page_num: int) -> List[Dict]:
        """Обработка изображений в PDF через OCR"""
        chunks = []
        image_list = page.get_images(full=True)
        
        for img_index, img in enumerate(image_list, 1):
            try:
                base_image = page.extract_image(img[0])
                image = Image.open(BytesIO(base_image["image"]))
                ocr_text = pytesseract.image_to_string(image, lang='rus+eng')
                
                if ocr_text.strip():
                    chunks.append(self._create_chunk(
                        text=f"Изображение {img_index}:\n{ocr_text}",
                        file_id=file_id,
                        page=page_num,
                        content_type="image",
                        chunk_order=0
                    ))
            except Exception as e:
                self.logger.warning(f"Ошибка OCR: {str(e)}")
        
        return chunks

    def _process_docx(self, file_path: str, file_id: str) -> List[Dict]:
        """Обработка DOCX файлов"""
        chunks = []
        current_chapter = ""
        current_section = ""
        
        try:
            doc = Document(file_path)
            full_text = ""
            
            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue
                    
                style = para.style.name.lower() if para.style else ""
                if 'heading 1' in style:
                    current_chapter = text
                elif 'heading 2' in style:
                    current_section = text
                
                full_text += text + "\n"
            
            if full_text.strip():
                chunks.extend(self._split_text_into_chunks(
                    full_text, file_id, 0, "text", current_chapter, current_section
                ))
            
            # Обработка таблиц
            for table in doc.tables:
                try:
                    table_text = self._format_docx_table(table)
                    chunks.append(self._create_chunk(
                        text=table_text,
                        file_id=file_id,
                        page=0,
                        content_type="table",
                        chapter=current_chapter,
                        section=current_section,
                        chunk_order=0
                    ))
                except Exception as e:
                    self.logger.error(f"Ошибка обработки таблицы DOCX: {str(e)}")
            
            return chunks
        except Exception as e:
            self.logger.error(f"Ошибка обработки DOCX: {str(e)}", exc_info=True)
            return []

    def _format_docx_table(self, table) -> str:
        """Форматирование таблицы из DOCX"""
        try:
            data = []
            for row in table.rows:
                data.append([cell.text.strip() for cell in row.cells])
            
            df = pd.DataFrame(data[1:], columns=data[0])
            return self._safe_format_table(df, 0, 0)
        except Exception as e:
            self.logger.error(f"Ошибка форматирования таблицы DOCX: {str(e)}")
            return "Не удалось обработать таблицу из DOCX"

    def _create_chunk(self, text: str, file_id: str, page: int, content_type: str,
                    chapter: str = "", section: str = "", chunk_order: int = 0) -> Dict:
        """Создает структурированный чанк"""
        try:
            if not isinstance(text, str):
                text = str(text)
        except Exception as e:
            text = f"Ошибка преобразования текста: {str(e)}"
        
        chunk_id = generate_unique_id()
        return {
            "id": chunk_id,
            "text": text,
            "embedding": None,
            "metadata": {
                "file_id": file_id,
                "source": file_id if file_id.endswith(('.pdf','.doc','.docx')) else os.path.basename(file_id),
                "page": page,
                "type": content_type,
                "chapter": chapter,
                "section": section,
                "chunk_order": chunk_order,
                "processing_date": datetime.now().strftime('%Y-%m-%d'),
                "text_length": len(text),
                "language": "ru"
            }
        }

    def vectorize_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """Векторизация чанков"""
        if not chunks:
            return []
        
        try:
            texts = [chunk['text'] for chunk in chunks]
            embeddings = self.embedding_model.encode(
                texts,
                batch_size=self.config['performance']['embedding_batch_size'],
                show_progress_bar=False
            )
            
            for chunk, embedding in zip(chunks, embeddings):
                chunk['embedding'] = embedding.tolist()
            
            return chunks
        except Exception as e:
            self.logger.error(f"Ошибка векторизации: {str(e)}", exc_info=True)
            return []

    def save_chunks(self, chunks: List[Dict], output_file: str) -> None:
        """Сохранение чанков в файл"""
        try:
            chunks = self.vectorize_chunks(chunks)
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения чанков: {str(e)}", exc_info=True)

    def create_global_index(self, index_dir: str) -> None:
        """Создает/обновляет глобальный индекс"""
        try:
            index_data = {
                "files": [],
                "total_chunks": 0,
                "timestamp": datetime.now().isoformat()
            }

            # Сканируем processed директорию
            processed_dir = self.config['paths']['output_dir']
            for file in os.listdir(processed_dir):
                if file.endswith('.json') and file != 'global_index.json':
                    file_path = os.path.join(processed_dir, file)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        chunks = json.load(f)
                    
                    # Добавляем метаданные файла
                    if chunks:
                        first_chunk = chunks[0]
                        index_data['files'].append({
                            "id": first_chunk['metadata']['file_id'],
                            "path": first_chunk['metadata']['source'],
                            "chunks_count": len(chunks),
                            "timestamp": first_chunk['metadata']['processing_date']
                        })
                        index_data['total_chunks'] += len(chunks)

            # Сохраняем индекс
            os.makedirs(index_dir, exist_ok=True)
            index_file = os.path.join(index_dir, "global_index.json")
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, ensure_ascii=False, indent=4)

        except Exception as e:
            self.logger.error(f"Ошибка создания индекса: {str(e)}", exc_info=True)