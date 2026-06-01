import os
import re
import json
import chardet
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import streamlit as st

# ==============================================
# КОНФИГУРАЦИЯ
# ==============================================

def get_default_config():
    """Возвращает конфигурацию по умолчанию"""
    project_dir = Path(__file__).parent
    return {
        "folders": {
            "normative": str(project_dir / "NORMATIVE"),
            "methodology": str(project_dir / "METHODOLOGY"),
            "structured": str(project_dir / "STRUCTURED"),
            "expertise": str(project_dir / "EXPERTISE")
        },
        "data_path": str(project_dir / "data"),
        "sets_file": str(project_dir / "sets.json"),
        "supported_extensions": [".md", ".txt"]
    }

def load_config():
    """Загружает конфигурацию из JSON файла"""
    config_path = Path(__file__).parent / "config.json"
    
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                default_config = get_default_config()
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception:
            return get_default_config()
    
    return get_default_config()

CONFIG = load_config()

# Создаем необходимые папки
Path(CONFIG["data_path"]).mkdir(exist_ok=True, parents=True)
for folder_path in CONFIG["folders"].values():
    Path(folder_path).mkdir(exist_ok=True, parents=True)

# ==============================================
# ЧТЕНИЕ ФАЙЛОВ
# ==============================================

class FileReader:
    """Класс для чтения текстовых файлов"""
    
    @staticmethod
    def read_file(file_path: Path) -> Optional[str]:
        """Читает файлы форматов .md и .txt"""
        if not file_path.exists():
            return None
        
        extension = file_path.suffix.lower()
        
        if extension not in ['.md', '.txt']:
            return None
        
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
            
            if not raw_data:
                return ""
            
            # Определяем кодировку
            encoding_result = chardet.detect(raw_data)
            encoding = encoding_result.get('encoding', 'utf-8')
            
            try:
                return raw_data.decode(encoding, errors='ignore')
            except:
                return raw_data.decode('utf-8', errors='ignore')
                
        except Exception as e:
            print(f"Ошибка чтения {file_path}: {e}")
            return None

# ==============================================
# РАЗБОР НОРМАТИВНЫХ ДОКУМЕНТОВ
# ==============================================

class NormativeParser:
    """Парсер нормативных документов"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Очищает текст от примечаний и специальных символов"""
        if not text:
            return text
        
        # Очистка от примечаний КонсультантПлюс
        patterns = [
            r'КонсультантПлюс: примечание\.[^\n]*\n',
            r'\[Консультант[^\]]*примечание[^\]]*\][^\n]*\n',
            r'ГАРАНТ:\s*\n\s*См\. [^\n]*\n',
            r'ГАРАНТ:\s*\n\s*[^\n]*См\. [^\n]*\n',
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
        
        # Очистка специальных символов
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.replace('\xad', '')
        text = text.replace('\xa0', ' ')
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    @staticmethod
    def parse_document(file_path: Path) -> Dict:
        """Разбирает документ на главы и статьи"""
        reader = FileReader()
        content = reader.read_file(file_path)
        
        if not content:
            return {"full_content": "", "chapters": {}, "articles": {}}
        
        content = NormativeParser.clean_text(content)
        lines = content.split('\n')
        
        chapters = {}
        articles = {}
        current_chapter = None
        current_article = None
        article_content = []
        
        # Паттерны для распознавания
        chapter_pattern = re.compile(
            r'^(ГЛАВА|Глава)\s+'
            r'([IVXLCDM]+|\d+(?:\.\d+)*)'
            r'\.\s+'
            r'(.+)$'
        )
        
        article_pattern = re.compile(r'^Статья\s+(\d+[\.\d]*)\s*\.\s*(.*)$')
        
        for line in lines:
            line_stripped = line.strip()
            
            # Проверяем на главу
            chapter_match = chapter_pattern.match(line_stripped)
            if chapter_match:
                if current_article and current_article:
                    articles[current_article] = "\n".join(article_content).strip()
                    article_content = []
                    current_article = None
                
                chapter_number = chapter_match.group(2)
                chapter_name = chapter_match.group(3).strip()
                current_chapter = f"Глава {chapter_number}. {chapter_name}"
                chapters[current_chapter] = []
                continue
            
            # Проверяем на статью
            article_match = article_pattern.match(line_stripped)
            if article_match:
                if current_article and article_content:
                    articles[current_article] = "\n".join(article_content).strip()
                    article_content = []
                
                article_num = article_match.group(1)
                article_title = article_match.group(2).strip()
                current_article = article_num
                article_content.append(line)
                
                if current_chapter:
                    chapters[current_chapter].append(article_num)
                continue
            
            # Собираем содержимое статьи
            if current_article:
                article_content.append(line)
        
        # Добавляем последнюю статью
        if current_article and article_content:
            articles[current_article] = "\n".join(article_content).strip()
        
        return {
            "full_content": content,
            "chapters": chapters,
            "articles": articles,
            "filename": file_path.name,
            "title": file_path.stem
        }
    
    @staticmethod
    def get_articles_in_chapter(parsed_doc: Dict, chapter_name: str) -> List[str]:
        """Возвращает список статей в главе"""
        chapters = parsed_doc.get("chapters", {})
        
        # Ищем главу по частичному совпадению
        for ch_name, articles in chapters.items():
            if chapter_name.lower() in ch_name.lower() or ch_name.lower() in chapter_name.lower():
                return articles
        
        return []
    
    @staticmethod
    def expand_article_range(article_range: str) -> List[str]:
        """Разворачивает диапазон статей (например, '1-5' -> ['1','2','3','4','5'])"""
        if '-' not in article_range:
            return [article_range.strip()]
        
        parts = article_range.split('-')
        if len(parts) != 2:
            return [article_range.strip()]
        
        try:
            start = int(parts[0].strip())
            end = int(parts[1].strip())
            return [str(i) for i in range(start, end + 1)]
        except ValueError:
            return [article_range.strip()]

# ==============================================
# ВАЛИДАЦИЯ НАБОРОВ
# ==============================================

class SetsValidator:
    """Валидатор структуры sets.json"""
    
    VALID_TYPES = ["normative", "structured", "methodology", "expertise"]
    
    @staticmethod
    def validate(sets_data: List[Dict]) -> Tuple[bool, List[str]]:
        """
        Проверяет структуру sets.json
        Возвращает: (валидно, список_ошибок)
        """
        errors = []
        warnings = []
        
        # Проверка 1: должен быть список
        if not isinstance(sets_data, list):
            errors.append("sets.json должен содержать массив (список) наборов")
            return False, errors
        
        if len(sets_data) == 0:
            warnings.append("sets.json пуст. Добавьте хотя бы один набор")
            return True, warnings  # Не ошибка, но предупреждение
        
        # Проверка уникальности id
        ids = set()
        
        # Проверка каждого набора
        for idx, set_item in enumerate(sets_data):
            prefix = f"Набор #{idx+1}"
            
            # Проверка наличия id
            if "id" not in set_item:
                errors.append(f"{prefix}: отсутствует обязательное поле 'id'")
            else:
                set_id = set_item["id"]
                if not isinstance(set_id, str):
                    errors.append(f"{prefix}: поле 'id' должно быть строкой")
                elif set_id in ids:
                    errors.append(f"{prefix}: id '{set_id}' уже используется")
                else:
                    ids.add(set_id)
            
            # Проверка наличия name
            if "name" not in set_item:
                errors.append(f"{prefix}: отсутствует обязательное поле 'name'")
            elif not isinstance(set_item["name"], str):
                errors.append(f"{prefix}: поле 'name' должно быть строкой")
            elif len(set_item["name"].strip()) == 0:
                errors.append(f"{prefix}: поле 'name' не может быть пустым")
            
            # description необязательное, но если есть - должна быть строка
            if "description" in set_item and not isinstance(set_item["description"], str):
                errors.append(f"{prefix}: поле 'description' должно быть строкой")
            
            # Проверка items (обязательное поле)
            if "items" not in set_item:
                errors.append(f"{prefix}: отсутствует обязательное поле 'items'")
                continue
            
            items = set_item["items"]
            if not isinstance(items, list):
                errors.append(f"{prefix}: поле 'items' должно быть массивом")
                continue
            
            # Проверка каждого элемента в items
            for item_idx, item in enumerate(items):
                item_prefix = f"{prefix} - элемент #{item_idx+1}"
                
                # Проверка type
                if "type" not in item:
                    errors.append(f"{item_prefix}: отсутствует поле 'type'")
                else:
                    item_type = item["type"]
                    if item_type not in SetsValidator.VALID_TYPES:
                        errors.append(f"{item_prefix}: недопустимый type '{item_type}'. Допустимые: {', '.join(SetsValidator.VALID_TYPES)}")
                
                # Проверка document
                if "document" not in item:
                    errors.append(f"{item_prefix}: отсутствует поле 'document'")
                elif not isinstance(item["document"], str):
                    errors.append(f"{item_prefix}: поле 'document' должно быть строкой")
                elif not item["document"]:
                    errors.append(f"{item_prefix}: поле 'document' не может быть пустым")
                
                # Проверка chapters (для normative)
                item_type = item.get("type", "")
                if item_type == "normative":
                    chapters = item.get("chapters", [])
                    articles = item.get("articles", [])
                    
                    # Проверяем, что chapters - это список
                    if "chapters" in item and not isinstance(chapters, list):
                        errors.append(f"{item_prefix}: поле 'chapters' должно быть массивом")
                    
                    # Проверяем, что articles - это список
                    if "articles" in item and not isinstance(articles, list):
                        errors.append(f"{item_prefix}: поле 'articles' должно быть массивом")
                    
                    # Проверка формата статей (диапазоны)
                    if articles:
                        for article in articles:
                            if not isinstance(article, str):
                                errors.append(f"{item_prefix}: статья '{article}' должна быть строкой")
                            elif '-' in article:
                                parts = article.split('-')
                                if len(parts) != 2:
                                    errors.append(f"{item_prefix}: неверный формат диапазона '{article}'. Используйте 'X-Y'")
                                else:
                                    try:
                                        int(parts[0].strip())
                                        int(parts[1].strip())
                                    except ValueError:
                                        errors.append(f"{item_prefix}: диапазон '{article}' должен содержать числа")
                            elif article.strip():
                                try:
                                    # Проверка, что статья - число
                                    float(article.strip())
                                except ValueError:
                                    warnings.append(f"{item_prefix}: статья '{article}' имеет нестандартный формат")
                
                # Проверка sections (для structured)
                if item_type == "structured":
                    sections = item.get("sections", [])
                    
                    if "sections" in item and not isinstance(sections, list):
                        errors.append(f"{item_prefix}: поле 'sections' должно быть массивом")
                    
                    if sections:
                        for section in sections:
                            if not isinstance(section, str):
                                errors.append(f"{item_prefix}: раздел '{section}' должен быть строкой")
                            elif not (section.strip().startswith('[') and section.strip().endswith(']')):
                                warnings.append(f"{item_prefix}: раздел '{section}' рекомендуется оформлять в квадратных скобках")
                
                # Проверка, что для методических и экспертных документов нет лишних полей
                if item_type in ["methodology", "expertise"]:
                    if "chapters" in item:
                        warnings.append(f"{item_prefix}: для type '{item_type}' поле 'chapters' игнорируется")
                    if "articles" in item:
                        warnings.append(f"{item_prefix}: для type '{item_type}' поле 'articles' игнорируется")
                    if "sections" in item:
                        warnings.append(f"{item_prefix}: для type '{item_type}' поле 'sections' игнорируется")
        
        return len(errors) == 0, errors + warnings

# ==============================================
# РАБОТА С НАБОРАМИ
# ==============================================

class SetsManager:
    """Управление наборами документов"""
    
    def __init__(self):
        self.sets_file = Path(CONFIG["sets_file"])
        self.reader = FileReader()
        self.parser = NormativeParser()
        self._loaded_docs = {}  # Кеш для загруженных документов
        self.validation_errors = []
        self.validation_warnings = []
    
    def load_sets(self) -> List[Dict]:
        """Загружает и валидирует наборы из JSON файла"""
        if not self.sets_file.exists():
            # Создаем пример файла наборов
            example_sets = [
                {
                    "id": "example_1",
                    "name": "Пример набора",
                    "description": "Пример набора для тестирования",
                    "selected": True,
                    "items": [
                        {
                            "type": "normative",
                            "document": "Земельный кодекс РФ.txt",
                            "chapters": ["Глава 1"],
                            "articles": ["1", "2", "5-10"]
                        },
                        {
                            "type": "structured",
                            "document": "Порядок действий.md",
                            "sections": ["[Раздел 1]", "[Раздел 2]"]
                        },
                        {
                            "type": "methodology",
                            "document": "Методика расчета.md"
                        },
                        {
                            "type": "expertise",
                            "document": "Заключение эксперта.md"
                        }
                    ]
                }
            ]
            self._save_sets(example_sets)
            self.validation_errors = []
            self.validation_warnings = []
            return example_sets
        
        try:
            with open(self.sets_file, 'r', encoding='utf-8') as f:
                sets = json.load(f)
                
                # Валидация структуры
                is_valid, messages = SetsValidator.validate(sets)
                
                # Разделяем ошибки и предупреждения
                self.validation_errors = [m for m in messages if "неверный" in m.lower() or "отсутствует" in m.lower() or "должен" in m.lower()]
                self.validation_warnings = [m for m in messages if m not in self.validation_errors]
                
                if not is_valid:
                    return []  # Возвращаем пустой список при критических ошибках
                
                if isinstance(sets, list):
                    return sets
                return []
                
        except json.JSONDecodeError as e:
            st.error(f"❌ Ошибка синтаксиса JSON: {e}")
            self.validation_errors = [f"Ошибка синтаксиса JSON: {e}"]
            return []
        except Exception as e:
            st.error(f"❌ Ошибка загрузки наборов: {e}")
            self.validation_errors = [f"Ошибка загрузки: {e}"]
            return []
    
    def get_validation_status(self) -> Tuple[bool, List[str], List[str]]:
        """Возвращает статус валидации: (есть_ли_ошибки, ошибки, предупреждения)"""
        has_errors = len(self.validation_errors) > 0
        return has_errors, self.validation_errors, self.validation_warnings
    
    def _save_sets(self, sets: List[Dict]) -> bool:
        """Сохраняет наборы в JSON файл"""
        try:
            with open(self.sets_file, 'w', encoding='utf-8') as f:
                json.dump(sets, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            st.error(f"Ошибка сохранения наборов: {e}")
            return False
    
    def save_sets(self, sets: List[Dict]) -> bool:
        """Сохраняет наборы (публичный метод)"""
        # Перед сохранением проверяем валидность
        is_valid, errors, _ = SetsValidator.validate(sets)
        if not is_valid:
            for error in errors:
                st.error(f"❌ {error}")
            return False
        return self._save_sets(sets)
    
    def get_document_content(self, doc_type: str, filename: str) -> Optional[Dict]:
        """Получает содержимое документа по типу и имени"""
        cache_key = f"{doc_type}/{filename}"
        
        if cache_key in self._loaded_docs:
            return self._loaded_docs[cache_key]
        
        folder = CONFIG["folders"].get(doc_type)
        if not folder:
            return None
        
        file_path = Path(folder) / filename
        
        if not file_path.exists():
            return None
        
        if doc_type == "normative":
            result = self.parser.parse_document(file_path)
        else:
            content = self.reader.read_file(file_path)
            if content:
                content = self.parser.clean_text(content)
            result = {
                "full_content": content or "",
                "filename": filename,
                "title": file_path.stem
            }
        
        self._loaded_docs[cache_key] = result
        return result
    
    def extract_from_normative(self, doc_data: Dict, item: Dict) -> Tuple[str, List[str]]:
        """Извлекает содержимое из нормативного документа"""
        filename = item.get("document", "")
        parsed_doc = doc_data
        
        if not parsed_doc or not parsed_doc.get("full_content"):
            return f"\n## ⚠️ {filename}\n\n**Ошибка:** Документ не найден или пуст\n", ["Файл не найден"]
        
        result_parts = []
        warnings = []
        
        chapters = item.get("chapters", [])
        articles = item.get("articles", [])
        
        # Режим: весь документ целиком
        if not chapters and not articles:
            result_parts.append(f"\n## 📖 {filename} (полный документ)\n")
            result_parts.append(parsed_doc["full_content"])
            return "\n".join(result_parts), warnings
        
        # Добавляем заголовок
        result_parts.append(f"\n## 📖 {filename}\n")
        
        # Обрабатываем главы (все статьи из глав)
        for chapter in chapters:
            chapter_articles = self.parser.get_articles_in_chapter(parsed_doc, chapter)
            if chapter_articles:
                result_parts.append(f"\n### {chapter}\n")
                for art_num in chapter_articles:
                    art_content = parsed_doc["articles"].get(art_num, "")
                    if art_content:
                        result_parts.append(art_content)
                        result_parts.append("")
                    else:
                        warnings.append(f"Статья {art_num} из главы '{chapter}' не найдена в {filename}")
            else:
                warnings.append(f"Глава '{chapter}' не найдена в {filename}")
        
        # Обрабатываем отдельные статьи
        for article in articles:
            # Разворачиваем диапазоны
            article_numbers = self.parser.expand_article_range(article)
            
            for art_num in article_numbers:
                art_content = parsed_doc["articles"].get(art_num, "")
                if art_content:
                    result_parts.append(f"\n### Статья {art_num}\n")
                    result_parts.append(art_content)
                    result_parts.append("")
                else:
                    warnings.append(f"Статья {art_num} не найдена в {filename}")
        
        return "\n".join(result_parts), warnings
    
    def extract_from_structured(self, doc_data: Dict, item: Dict) -> Tuple[str, List[str]]:
        """Извлекает содержимое из структурированного документа"""
        filename = item.get("document", "")
        sections = item.get("sections", [])
        content = doc_data.get("full_content", "")
        
        if not content:
            return f"\n## ⚠️ {filename}\n\n**Ошибка:** Документ не найден или пуст\n", ["Файл не найден"]
        
        result_parts = []
        warnings = []
        
        result_parts.append(f"\n## 📑 {filename}\n")
        
        # Если разделы не указаны - выводим весь документ
        if not sections:
            result_parts.append(content)
            return "\n".join(result_parts), warnings
        
        # Ищем указанные разделы (в квадратных скобках)
        lines = content.split('\n')
        current_section = None
        section_content = []
        found_sections = set()
        
        for line in lines:
            line_stripped = line.strip()
            
            # Проверяем, является ли строка заголовком раздела
            is_section_header = False
            if line_stripped.startswith('[') and line_stripped.endswith(']'):
                header_content = line_stripped[1:-1].strip()
                if header_content and len(header_content) <= 200:
                    # Сохраняем предыдущий раздел
                    if current_section and section_content:
                        if current_section in sections:
                            result_parts.append(f"\n### {current_section}\n")
                            result_parts.append("\n".join(section_content).strip())
                            result_parts.append("")
                            found_sections.add(current_section)
                    
                    current_section = line_stripped
                    section_content = []
                    is_section_header = True
            
            if not is_section_header and current_section:
                section_content.append(line)
        
        # Добавляем последний раздел
        if current_section and section_content:
            if current_section in sections:
                result_parts.append(f"\n### {current_section}\n")
                result_parts.append("\n".join(section_content).strip())
                result_parts.append("")
                found_sections.add(current_section)
        
        # Проверяем, какие разделы не найдены
        for section in sections:
            if section not in found_sections:
                warnings.append(f"Раздел '{section}' не найден в {filename}")
        
        if not result_parts:
            warnings.append(f"Ни один из указанных разделов не найден в {filename}")
            result_parts.append(f"\n⚠️ В документе {filename} не найдены указанные разделы\n")
        
        return "\n".join(result_parts), warnings
    
    def extract_from_simple(self, doc_type: str, doc_data: Dict, item: Dict) -> Tuple[str, List[str]]:
        """Извлекает содержимое из простых документов (methodology, expertise)"""
        filename = item.get("document", "")
        content = doc_data.get("full_content", "")
        
        if not content:
            return f"\n## ⚠️ {filename}\n\n**Ошибка:** Документ не найден или пуст\n", ["Файл не найден"]
        
        icon = "📚" if doc_type == "methodology" else "👨‍⚖️"
        title = "Методический документ" if doc_type == "methodology" else "Экспертное заключение"
        
        result_parts = [
            f"\n## {icon} {filename} ({title})\n",
            content
        ]
        
        return "\n".join(result_parts), []
    
    def generate_output(self, selected_set_ids: List[str]) -> Tuple[Optional[str], List[str]]:
        """Генерирует выходной JSON для выбранных наборов"""
        all_sets = self.load_sets()
        selected_sets = [s for s in all_sets if s.get("id") in selected_set_ids]
        
        if not selected_sets:
            return None, ["Не выбрано ни одного набора"]
        
        output_data = []
        all_warnings = []
        
        for set_data in selected_sets:
            set_output = {
                "set_id": set_data.get("id"),
                "set_name": set_data.get("name"),
                "set_description": set_data.get("description", ""),
                "export_date": datetime.now().isoformat(),
                "items": []
            }
            
            for item in set_data.get("items", []):
                doc_type = item.get("type")
                filename = item.get("document", "")
                
                if not filename:
                    continue
                
                # Получаем документ
                doc_data = self.get_document_content(doc_type, filename)
                
                if not doc_data:
                    all_warnings.append(f"Документ не найден: {doc_type}/{filename}")
                    set_output["items"].append({
                        "document": filename,
                        "type": doc_type,
                        "error": "Документ не найден",
                        "content": ""
                    })
                    continue
                
                # Извлекаем содержимое в зависимости от типа
                if doc_type == "normative":
                    content, warnings = self.extract_from_normative(doc_data, item)
                elif doc_type == "structured":
                    content, warnings = self.extract_from_structured(doc_data, item)
                elif doc_type in ["methodology", "expertise"]:
                    content, warnings = self.extract_from_simple(doc_type, doc_data, item)
                else:
                    all_warnings.append(f"Неизвестный тип документа: {doc_type}")
                    continue
                
                all_warnings.extend(warnings)
                
                set_output["items"].append({
                    "document": filename,
                    "type": doc_type,
                    "content": content,
                    "warnings": warnings
                })
            
            output_data.append(set_output)
        
        # Сохраняем в JSON файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(CONFIG["data_path"]) / f"export_{timestamp}.json"
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            return str(output_path), all_warnings
        except Exception as e:
            return None, [f"Ошибка сохранения файла: {e}"]

# ==============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ИНТЕРФЕЙСА
# ==============================================

def format_items_summary(items: List[Dict]) -> str:
    """Форматирует краткое описание элементов набора"""
    summaries = []
    
    for item in items:
        doc_type = item.get("type", "")
        filename = item.get("document", "")
        
        # Сокращаем имя файла
        short_name = filename[:40] + "..." if len(filename) > 40 else filename
        
        if doc_type == "normative":
            chapters = item.get("chapters", [])
            articles = item.get("articles", [])
            
            parts = []
            if chapters:
                parts.append(f"{len(chapters)} гл.")
            if articles:
                # Показываем первые 3 статьи
                arts_preview = articles[:3]
                arts_str = ", ".join(arts_preview)
                if len(articles) > 3:
                    arts_str += f" +{len(articles)-3}"
                parts.append(f"ст. {arts_str}")
            
            if not parts:
                summary = f"📖 {short_name} (полностью)"
            else:
                summary = f"📖 {short_name} — {' • '.join(parts)}"
        
        elif doc_type == "structured":
            sections = item.get("sections", [])
            if sections:
                secs_preview = [s[:30] + "..." if len(s) > 30 else s for s in sections[:2]]
                secs_str = ", ".join(secs_preview)
                if len(sections) > 2:
                    secs_str += f" +{len(sections)-2}"
                summary = f"📑 {short_name} — [{secs_str}]"
            else:
                summary = f"📑 {short_name} (полностью)"
        
        elif doc_type == "methodology":
            summary = f"📚 {short_name}"
        
        elif doc_type == "expertise":
            summary = f"👨‍⚖️ {short_name}"
        
        else:
            summary = f"📄 {short_name}"
        
        summaries.append(summary)
    
    return "\n".join(summaries)

# ==============================================
# ВЕБ-ИНТЕРФЕЙС
# ==============================================

st.set_page_config(page_title="Экспертная система", layout="wide")

st.title("📋 Экспертная система по нормативным документам")

# Инициализация менеджера
if 'sets_manager' not in st.session_state:
    st.session_state.sets_manager = SetsManager()
    st.session_state.sets = st.session_state.sets_manager.load_sets()
    st.session_state.selected_ids = []  # Храним выбранные ID

sets_manager = st.session_state.sets_manager

# Отображение ошибок валидации
has_errors, errors, warnings = sets_manager.get_validation_status()
if has_errors:
    with st.sidebar:
        st.error("❌ Ошибки в структуре sets.json")
        for error in errors:
            st.error(f"• {error}")
        st.info("Исправьте ошибки в файле sets.json и перезагрузите страницу")

if warnings:
    with st.sidebar:
        st.warning("⚠️ Предупреждения в структуре sets.json")
        for warning in warnings:
            st.warning(f"• {warning}")

# Основной интерфейс
st.subheader("📌 Выбор наборов документов")

if not st.session_state.sets:
    st.info("Нет доступных наборов. Создайте файл sets.json в корне программы.")
    
    # Показываем пример структуры
    with st.expander("📖 Пример структуры sets.json"):
        st.code("""
[
    {
        "id": "example_1",
        "name": "Проверка земельного участка",
        "description": "Набор для проверки земельного участка",
        "selected": true,
        "items": [
            {
                "type": "normative",
                "document": "Земельный кодекс РФ.txt",
                "chapters": ["Глава 1"],
                "articles": ["1", "2", "5-10"]
            },
            {
                "type": "structured",
                "document": "Порядок действий.md",
                "sections": ["[Раздел 1]", "[Раздел 2]"]
            },
            {
                "type": "methodology",
                "document": "Методика расчета.md"
            },
            {
                "type": "expertise",
                "document": "Заключение эксперта.md"
            }
        ]
    }
]
        """, language="json")
    
    # Кнопка создания примера
    if st.button("📄 Создать пример sets.json"):
        example_sets = [
            {
                "id": "example_1",
                "name": "Пример набора",
                "description": "Пример набора для тестирования",
                "selected": True,
                "items": []
            }
        ]
        sets_manager.save_sets(example_sets)
        st.rerun()
else:
    # Отображение наборов с чекбоксами (без слова "Выбрать")
    selected_ids = []
    
    for i, set_data in enumerate(st.session_state.sets):
        with st.container():
            col1, col2 = st.columns([0.3, 9.7])
            
            with col1:
                is_selected = st.checkbox(
                    " ",  # Пустая метка вместо "Выбрать"
                    value=set_data.get("selected", False),
                    key=f"set_{set_data.get('id', i)}"
                )
                if is_selected:
                    selected_ids.append(set_data.get("id"))
            
            with col2:
                st.markdown(f"**{set_data.get('name', 'Без названия')}**")
                if set_data.get("description"):
                    st.caption(set_data.get("description"))
                
                # Показываем краткий список глав и статей из набора
                items = set_data.get("items", [])
                if items:
                    summary = format_items_summary(items)
                    st.caption(summary)
    
    st.session_state.selected_ids = selected_ids
    st.markdown("---")

# Боковая панель
with st.sidebar:
    st.header("🚀 Генерация")
    
    # Кнопка генерации перенесена в боковую панель
    if st.button("📄 Сгенерировать выходной файл", type="primary", use_container_width=True):
        if has_errors:
            st.error("❌ Невозможно сгенерировать файл: есть ошибки в структуре sets.json")
        elif not st.session_state.selected_ids:
            st.warning("⚠️ Выберите хотя бы один набор для генерации")
        else:
            with st.spinner("Генерация файла..."):
                output_path, warnings_list = sets_manager.generate_output(st.session_state.selected_ids)
                
                if output_path:
                    st.success(f"✅ Файл сохранён")
                    
                    # Показываем предупреждения
                    if warnings_list:
                        with st.expander(f"⚠️ Предупреждения ({len(warnings_list)})"):
                            for warning in warnings_list:
                                st.warning(warning)
                    
                    # Кнопка скачивания
                    with open(output_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    
                    st.download_button(
                        label="⬇️ Скачать файл",
                        data=file_content,
                        file_name=Path(output_path).name,
                        mime="application/json",
                        use_container_width=True
                    )
                else:
                    st.error(f"❌ Ошибка: {warnings_list[0] if warnings_list else 'Неизвестная ошибка'}")
    
    st.markdown("---")
    
    st.header("📊 Информация")
    
    # Статистика по папкам
    st.subheader("📁 Доступные документы")
    
    for folder_type, folder_path in CONFIG["folders"].items():
        folder = Path(folder_path)
        if folder.exists():
            files = []
            for ext in [".md", ".txt"]:
                files.extend(list(folder.glob(f"*{ext}")))
            
            icon = {
                "normative": "📖",
                "methodology": "📚",
                "structured": "🗂️",
                "expertise": "👨‍⚖️"
            }.get(folder_type, "📄")
            
            st.caption(f"{icon} {folder_type}: {len(files)} файлов")
    
    st.markdown("---")
    
    # Статистика по наборам
    st.subheader("📋 Наборы")
    st.caption(f"Всего наборов: {len(st.session_state.sets)}")
    
    total_items = sum(len(s.get("items", [])) for s in st.session_state.sets)
    st.caption(f"Всего элементов: {total_items}")
    
    st.markdown("---")
    
    # Редактирование sets.json
    st.subheader("✏️ Редактирование")
    
    if st.button("📝 Редактировать sets.json", use_container_width=True):
        sets_path = Path(CONFIG["sets_file"])
        if sets_path.exists():
            with open(sets_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            st.session_state.show_editor = True
            st.session_state.sets_content = content
        else:
            st.error("Файл sets.json не найден")
    
    if st.session_state.get("show_editor", False):
        new_content = st.text_area(
            "Редактирование sets.json",
            value=st.session_state.get("sets_content", ""),
            height=400,
            key="sets_editor"
        )
        
        col_save, col_cancel = st.columns(2)
        
        with col_save:
            if st.button("💾 Сохранить", use_container_width=True):
                try:
                    # Проверка валидности JSON
                    parsed = json.loads(new_content)
                    
                    # Проверка структуры
                    is_valid, validation_messages = SetsValidator.validate(parsed)
                    
                    if not is_valid:
                        for msg in validation_messages:
                            st.error(f"❌ {msg}")
                    else:
                        with open(CONFIG["sets_file"], 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        st.success("✅ Сохранено!")
                        st.session_state.sets = sets_manager.load_sets()
                        st.session_state.show_editor = False
                        st.rerun()
                        
                except json.JSONDecodeError as e:
                    st.error(f"❌ Ошибка синтаксиса JSON: {e}")
        
        with col_cancel:
            if st.button("❌ Отмена", use_container_width=True):
                st.session_state.show_editor = False
                st.rerun()
    
    st.markdown("---")
    st.caption("💡 Формат наборов описан в документации")
    st.caption("📌 Обязательные поля: id, name, items")
    st.caption("📌 Допустимые типы: normative, structured, methodology, expertise")

# Вывод при запуске
print("\n" + "="*60)
print("🚀 Экспертная система запущена!")
print("="*60)