import os
import re
import json
import fitz
import spacy
import camelot
import logging
import tempfile
import uuid
from docx import Document
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from .helpers import load_config, normalize_text, windows_path

class FileProcessor:
    def __init__(self, config):
        self.config = config
        self.nlp = spacy.load(config['processing']['spacy_model'])
        self.embedding_model = SentenceTransformer(
            config['processing']['embedding_model']
        )
        self.header_pattern = re.compile(
            r'^(Глава|Раздел|Часть|Параграф)\s+\d+[.:]?\s+', 
            re.IGNORECASE
        )
        self.subheader_pattern = re.compile(r'^\d+\.\d+\.\s+', re.IGNORECASE)
        self.global_headers = {}
        self.file_index = {}
        self.min_similarity = config['processing']['min_similarity']
        self.temp_dir = config['paths']['tempdir']
        
        # Создаем каталоги
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Системы индексов
        self.chunk_index = {}
        self.header_index = {}
        self.section_index = {}
        self.chunk_counter = 1

    def process_file(self, file_path):
        file_id = os.path.basename(file_path)
        self.file_index[file_id] = windows_path(file_path)
        
        if file_path.lower().endswith('.pdf'):
            return self._process_pdf(file_path, file_id)
        elif file_path.lower().endswith(('.doc', '.docx')):
            return self._process_docx(file_path, file_id)
        else:
            raise ValueError(f"Неподдерживаемый формат: {file_path}")

    def _process_pdf(self, file_path, file_id):
        # Используем Ghostscript для ускорения обработки
        doc = fitz.open(file_path, filetype="pdf")
        chunks = []
        current_chapter = ""
        current_section = ""
        
        try:
            toc = doc.get_toc()
        except:
            toc = []
            logging.warning(f"Не удалось извлечь оглавление для {file_path}")
        
        for page_num in tqdm(range(len(doc)), desc=f"Обработка {file_id}"):
            page = doc.load_page(page_num)
            text = page.get_text("text", sort=True)
            
            # Обработка оглавления
            for item in toc:
                if item[2] == page_num + 1:
                    if item[0] == 1:
                        current_chapter = normalize_text(item[1])
                    elif item[0] == 2:
                        current_section = normalize_text(item[1])
            
            self._register_headers(file_id, page_num, current_chapter, current_section)
            
            # Обработка таблиц
            tmp_path = None
            try:
                # Создаем временный файл только для текущей страницы
                with tempfile.NamedTemporaryFile(
                    dir=self.temp_dir, 
                    suffix=".pdf", 
                    delete=False
                ) as tmp:
                    tmp_path = tmp.name
                
                # Сохраняем только текущую страницу
                single_page = fitz.open()
                single_page.insert_pdf(doc, from_page=page_num, to_page=page_num)
                single_page.save(tmp_path)
                single_page.close()

                tables = camelot.read_pdf(
                    windows_path(tmp_path), 
                    pages="1",  # Всегда первая страница во временном файле
                    flavor='lattice'
                )
            except Exception as e:
                logging.error(f"Ошибка обработки таблиц: {str(e)}")
                tables = []
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except Exception as e:
                        logging.error(f"Ошибка удаления временного файла: {str(e)}")
            
            # Обработка извлеченных таблиц
            for i, table in enumerate(tables):
                table_text = f"ТАБЛИЦА {file_id}-{page_num+1}.{i+1}: {table.df.to_csv(sep='|', index=False)}"
                chunks.append(self._create_chunk(
                    table_text, 
                    file_id, 
                    page_num,
                    "table",
                    current_chapter,
                    current_section
                ))
            
            # Обработка текста
            blocks = page.get_text("blocks")
            for block in blocks:
                if not block[4].strip():
                    continue
                    
                block_text = normalize_text(block[4].replace('\n', ' '))
                content_type = "text"
                
                if "рисунок" in block_text.lower() or "изображение" in block_text.lower():
                    content_type = "image_caption"
                elif self.header_pattern.match(block_text):
                    content_type = "header"
                elif self.subheader_pattern.match(block_text):
                    content_type = "subheader"
                
                # Разбивка на предложения
                doc_text = self.nlp(block_text)
                for sent in doc_text.sents:
                    if len(sent.text.strip()) > 10:
                        chunks.append(self._create_chunk(
                            sent.text, 
                            file_id, 
                            page_num,
                            content_type,
                            current_chapter,
                            current_section
                        ))
        
        doc.close()
        return chunks

    def _process_docx(self, file_path, file_id):
        doc = Document(file_path)
        chunks = []
        current_page = 0
        current_chapter = ""
        current_section = ""
        paragraph_count = 0
        
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
            
            # Разбивка на предложения
            doc_text = self.nlp(text)
            for sent in doc_text.sents:
                if len(sent.text.strip()) > 10:
                    chunks.append(self._create_chunk(
                        sent.text, 
                        file_id, 
                        current_page,
                        content_type,
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
        chunk_id = f"{file_id}_{page}_{self.chunk_counter}"
        self.chunk_counter += 1
        
        chunk = {
            "id": chunk_id,
            "text": text,
            "metadata": {
                "file_id": file_id,
                "page": page,
                "type": content_type,
                "chapter": chapter,
                "section": section,
                "source": os.path.basename(file_id)
            }
        }
        
        # Индексация
        self.chunk_index[chunk_id] = chunk
        if chapter:
            self.header_index.setdefault(chapter, []).append(chunk_id)
        if section:
            self.section_index.setdefault(section, []).append(chunk_id)
        
        return chunk

    def _register_headers(self, file_id, page, chapter, section):
        key = f"{file_id}_{page}"
        self.global_headers[key] = chapter or section

    def vectorize_chunks(self, chunks):
        texts = [chunk['text'] for chunk in chunks]
        embeddings = []
        
        batch_size = 32  # Уменьшено для экономии памяти
        for i in tqdm(range(0, len(texts), batch_size), desc="Векторизация"):
            batch = texts[i:i+batch_size]
            embeddings.extend(self.embedding_model.encode(batch))
        
        for i, chunk in enumerate(chunks):
            chunk['embedding'] = embeddings[i].tolist()
        
        return chunks

    def save_chunks(self, chunks, output_file):
        chunks = self.vectorize_chunks(chunks)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

    def create_global_index(self, output_dir):
        """Создает глобальные индексы для быстрого поиска"""
        # Сохраняем индексы
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