import os
import re
import json
import yaml
import chardet
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import uuid
import streamlit as st
import shutil

# ==============================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ШАБЛОНАМИ
# ==============================================

def load_templates():
    """Загружает шаблоны из templates.json"""
    templates_path_str = CONFIG.get("templates_path", "")
    
    if templates_path_str:
        templates_path = Path(templates_path_str)
    else:
        project_dir = Path(__file__).parent
        templates_path = project_dir / "templates.json"
    
    if templates_path.exists():
        try:
            with open(templates_path, 'r', encoding='utf-8') as f:
                templates_data = json.load(f)
                print(f"✅ Шаблоны загружены из {templates_path}")
                if isinstance(templates_data, list):
                    return templates_data
                else:
                    if "templates" in templates_data:
                        templates_list = templates_data["templates"]
                        if templates_list and len(templates_list) > 0:
                            return templates_list
        except Exception as e:
            print(f"❌ Ошибка загрузки шаблонов: {e}")
    
    return [
        {
            "id": "standard",
            "name": "📝 Стандартный ответ",
            "description": "Развернутый профессиональный ответ с анализом",
            "prompt": "Ты — эксперт в области землепользования и кадастра.\n\nНа основе предоставленных материалов подготовь развернутый профессиональный ответ.",
            "selected": True
        }
    ]

def save_templates(templates_data):
    """Сохраняет шаблоны в templates.json"""
    templates_path_str = CONFIG.get("templates_path", "")
    
    if templates_path_str:
        templates_path = Path(templates_path_str)
    else:
        project_dir = Path(__file__).parent
        templates_path = project_dir / "templates.json"
    
    try:
        templates_path.parent.mkdir(exist_ok=True, parents=True)
        with open(templates_path, 'w', encoding='utf-8') as f:
            json.dump(templates_data, f, ensure_ascii=False, indent=2)
        print(f"✅ Шаблоны сохранены в {templates_path}")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения шаблонов: {e}")
        return False

def get_selected_template(templates_data):
    """Возвращает выбранный шаблон"""
    if not templates_data:
        return None
    for template in templates_data:
        if template.get("selected", False):
            return template
    return templates_data[0] if templates_data else None

def update_selected_template(templates_data, selected_id):
    """Обновляет выбранный шаблон"""
    for template in templates_data:
        template["selected"] = (template["id"] == selected_id)
    return templates_data

# ==============================================
# КОНФИГУРАЦИЯ
# ==============================================

def get_default_config():
    """Возвращает конфигурацию по умолчанию"""
    project_dir = Path(__file__).parent
    project_dir.mkdir(exist_ok=True)
    
    return {
        "folders": {
            "normative": str(project_dir / "NORMATIVE"),
            "methodology": str(project_dir / "METHODOLOGY"),
            "structured": str(project_dir / "STRUCTURED"),
            "expertise": str(project_dir / "EXPERTISE")
        },
        "database_path": str(project_dir / "knowledge_database.db"),
        "sessions_path": str(project_dir / "sessions"),
        "templates_path": str(project_dir / "templates.json"),
        "supported_extensions": [".md", ".txt"],
        "admin_enabled": True,
        "max_upload_size_mb": 100
    }

def load_config():
    """Загружает конфигурацию из JSON файла"""
    config_path = Path(__file__).parent / "config.json"
    
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print(f"✅ Конфигурация загружена из {config_path}")
                default_config = get_default_config()
                for key, value in default_config.items():
                    if key not in config:
                        print(f"⚠ В конфигурации отсутствует ключ: {key}. Используется значение по умолчанию.")
                        config[key] = value
                return config
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка в формате JSON: {e}")
            return get_default_config()
        except Exception as e:
            print(f"❌ Ошибка загрузки конфигурации: {e}")
            return get_default_config()
    
    print("⚠ Файл config.json не найден. Используются значения по умолчанию.")
    return get_default_config()

def save_config(config):
    """Сохраняет конфигурацию в JSON файл"""
    try:
        config_path = Path(__file__).parent / "config.json"
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"✅ Конфигурация сохранена в {config_path}")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения конфигурации: {e}")
        return False

def validate_folders(folders_config):
    """Проверяет существование папки из конфигурации"""
    missing = []
    existing = []
    
    for folder_type, folder_path in folders_config.items():
        if not folder_path or folder_path.strip() == "":
            missing.append((folder_type, "(пустой путь)"))
            continue
            
        path = Path(folder_path)
        if path.exists() and path.is_dir():
            existing.append((folder_type, folder_path))
        else:
            missing.append((folder_type, folder_path))
    
    return {
        "all_exist": len(missing) == 0,
        "existing": existing,
        "missing": missing
    }

def create_default_folders(folders_config):
    """Создает папки по умолчанию если они не существуют"""
    created = []
    for folder_type, folder_path in folders_config.items():
        if folder_path:
            path = Path(folder_path)
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    created.append((folder_type, folder_path))
                except Exception as e:
                    print(f"❌ Не удалось создать папку {folder_path}: {e}")
    return created

def load_default_prompt():
    """Загружает промт из выбранного шаблона"""
    templates_data = load_templates()
    selected_template = get_selected_template(templates_data)
    return selected_template.get("prompt", "") if selected_template else ""

# ==============================================
# КЛАСС ДЛЯ РАБОТЫ С ФАЙЛАМИ
# ==============================================

class FileFormatReader:
    """Класс для чтения текстовых файлов"""
    
    @staticmethod
    def read_file(file_path: Path) -> Optional[str]:
        """Читает файлы форматов .md и .txt"""
        if not file_path.exists():
            return None
        
        extension = file_path.suffix.lower()
        
        try:
            if extension in ['.md', '.txt']:
                return FileFormatReader._read_text(file_path)
            else:
                print(f"⚠ Неподдерживаемый формат файла: {extension}")
                return None
        except Exception as e:
            print(f"❌ Ошибка чтения файла {file_path}: {e}")
            return None
    
    @staticmethod
    def _read_text(file_path: Path) -> Optional[str]:
        """Читает текстовые файлы с определением кодировки"""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
            
            if not raw_data:
                return ""
            
            encoding_result = chardet.detect(raw_data)
            encoding = encoding_result['encoding']
            confidence = encoding_result['confidence']
            
            if not encoding or confidence < 0.7:
                encodings_to_try = ['utf-8', 'utf-16-le', 'utf-16-be', 'cp1251', 'iso-8859-1']
            else:
                encodings_to_try = [encoding, 'utf-8', 'utf-16-le', 'utf-16-be']
            
            for enc in encodings_to_try:
                try:
                    if enc.startswith('utf-16'):
                        if len(raw_data) >= 2:
                            bom = raw_data[:2]
                            if bom == b'\xff\xfe':
                                content = raw_data[2:].decode('utf-16-le')
                                return content
                            elif bom == b'\xfe\xff':
                                content = raw_data[2:].decode('utf-16-be')
                                return content
                            else:
                                try:
                                    content = raw_data.decode('utf-16-le')
                                    return content
                                except:
                                    content = raw_data.decode('utf-16-be')
                                    return content
                    
                    content = raw_data.decode(enc, errors='strict')
                    return content
                except (UnicodeDecodeError, LookupError):
                    continue
            
            try:
                return raw_data.decode('utf-8', errors='ignore')
            except:
                return raw_data.decode('latin-1', errors='ignore')
                
        except Exception as e:
            print(f"❌ Ошибка чтения текстового файла {file_path}: {e}")
            return None

# ==============================================
# СИСТЕМА УПРАВЛЕНИЯ БАЗОЙ РАЗДЕЛОВ
# ==============================================

class SimpleSectionDatabase:
    """Простая система для создания и управления базой разделов"""
    
    def __init__(self):
        self.db_path = Path(CONFIG["database_path"])
        self.sections_db = self.db_path / "sections.json"
        self.metadata_db = self.db_path / "metadata.json"
        self.file_reader = FileFormatReader()
        
        self.db_path.mkdir(exist_ok=True, parents=True)
        self.sections = self._load_sections()
        self.metadata = self._load_metadata()
    
    def _load_sections(self) -> List[Dict]:
        """Загружаем базу разделов"""
        if self.sections_db.exists():
            try:
                with open(self.sections_db, 'r', encoding='utf-8') as f:
                    sections = json.load(f)
                    print(f"✅ База разделов загружена из {self.sections_db}")
                    return sections
            except json.JSONDecodeError as e:
                print(f"❌ Ошибка JSON в файле разделов: {e}")
                return []
            except Exception as e:
                print(f"❌ Ошибка загрузки базы разделов: {e}")
                return []
        else:
            print("📁 База разделов не найдена, создается новая")
            return []
    
    def _load_metadata(self) -> Dict:
        """Загружаем метаданные базы"""
        if self.metadata_db.exists():
            try:
                with open(self.metadata_db, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    print(f"✅ Метаданные базы загружены из {self.metadata_db}")
                    return metadata
            except json.JSONDecodeError as e:
                print(f"❌ Ошибка JSON в файле метаданных: {e}")
                return self._create_default_metadata()
            except Exception as e:
                print(f"❌ Ошибка загрузки метаданных: {e}")
                return self._create_default_metadata()
        else:
            print("📁 Метаданные базы не найдены, создаются новые")
            return self._create_default_metadata()
    
    def _create_default_metadata(self) -> Dict:
        """Создает метаданные по умолчанию"""
        return {
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "total_sections": 0,
            "total_documents": 0,
            "version": "1.0"
        }
    
    def _clean_text_from_comments(self, text: str) -> str:
        """Очищает текст от примечаний КонсультантПлюс/ГАРАНТ"""
        if not text:
            return text
        
        cleaned_text = text
        
        consultant_patterns = [
            r'КонсультантПлюс: примечание\.[^\n]*\n',
            r'\[Консультант[^\]]*примечание[^\]]*\][^\n]*\n',
        ]
        
        for pattern in consultant_patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.MULTILINE)
        
        garant_patterns = [
            r'ГАРАНТ:\s*\n\s*См\. [^\n]*\n',
            r'ГАРАНТ:\s*\n\s*[^\n]*См\. [^\n]*\n',
        ]
        
        for pattern in garant_patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.MULTILINE)
        
        return cleaned_text.strip()
    
    def _clean_special_characters(self, text: str) -> str:
        """Очищает текст от специальных символов"""
        if not text:
            return text
        
        cleaned = re.sub(r'[ \t]+', ' ', text)
        cleaned = cleaned.replace('\xad', '')
        cleaned = cleaned.replace('\xa0', ' ')
        cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = cleaned.strip()
        
        return cleaned
    
    def _extract_yaml_metadata(self, content: str) -> Dict:
        """Извлекает метаданные из YAML заголовка"""
        metadata = {}
        
        try:
            content_stripped = content.strip()
            if content_stripped.startswith('---'):
                parts = content_stripped.split('---', 2)
                if len(parts) >= 3:
                    yaml_content = parts[1].strip()
                    if yaml_content:
                        metadata = yaml.safe_load(yaml_content) or {}
                        if not isinstance(metadata, dict):
                            metadata = {}
        except (yaml.YAMLError, AttributeError) as e:
            print(f"  ⚠ Не удалось прочитать YAML: {e}")
        
        return metadata
    
    def save_database(self):
        """Сохраняем базу на диск"""
        try:
            self.db_path.mkdir(exist_ok=True, parents=True)
            
            with open(self.sections_db, 'w', encoding='utf-8') as f:
                json.dump(self.sections, f, ensure_ascii=False, indent=2)
            
            with open(self.metadata_db, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
            
            print(f"💾 База данных сохранена в {self.db_path}")
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения базы данных: {e}")
            return False
    
    def _recalculate_metadata(self, sections: List[Dict]) -> Dict:
        """Пересчитывает метаданные на основе списка разделов"""
        if not sections:
            return self._create_default_metadata()
        
        unique_documents = set()
        
        for section in sections:
            doc_path = section.get("document_path", "")
            doc_name = section.get("document", "")
            if doc_path or doc_name:
                doc_key = f"{doc_path}_{doc_name}"
                unique_documents.add(doc_key)
        
        created_at = self.metadata.get("created_at", datetime.now().isoformat())
        
        return {
            "created_at": created_at,
            "last_updated": datetime.now().isoformat(),
            "total_sections": len(sections),
            "total_documents": len(unique_documents),
            "version": "1.0"
        }
    
    def scan_and_build_database(self):
        """Сканируем папки и строим базу разделов"""
        print("🔍 Начинаем сканирование папок...")
        
        all_sections = []
        
        for folder_name, folder_path in CONFIG["folders"].items():
            if not folder_path or not Path(folder_path).exists():
                print(f"⚠ Папка не найдена: {folder_path}")
                continue
            
            folder = Path(folder_path)
            print(f"\n📁 Сканируем: {folder} ({folder_name})")
            
            files = []
            for ext in SUPPORTED_EXTENSIONS:
                files.extend(list(folder.rglob(f"*{ext}")))
            
            folder_documents = len(files)
            folder_sections = 0
            
            for file_path in files:
                print(f"  📄 {file_path.name} ({file_path.suffix})...", end="")
                
                try:
                    content = self.file_reader.read_file(file_path)
                    
                    if content is None:
                        print(f" ❌ Не удалось прочитать файл")
                        continue
                    
                    metadata = self._extract_yaml_metadata(content)
                    document_title = metadata.get('title', file_path.stem)
                    cleaned_content = self._clean_special_characters(content)
                    
                    sections = self._split_document_by_type(
                        cleaned_content,
                        file_path, 
                        folder_name, 
                        document_title,
                        metadata
                    )
                    
                    print(f" → {len(sections)} разделов")
                    folder_sections += len(sections)
                    
                    for i, section in enumerate(sections):
                        section_content = section.get("content", "")
                        final_content = self._clean_text_from_comments(section_content)
                        
                        all_sections.append({
                            "id": f"{file_path.stem}_{i}_{uuid.uuid4().hex[:8]}",
                            "folder": folder_name,
                            "document": file_path.name,
                            "document_extension": file_path.suffix,
                            "document_title": document_title,
                            "document_path": str(file_path),
                            "title": section.get("title", document_title),
                            "content": final_content,
                            "section_type": section.get("type", "text"),
                            "word_count": len(final_content.split()),
                            "metadata": metadata,
                            "selected": False,
                            "scan_date": datetime.now().isoformat()
                        })
                        
                except Exception as e:
                    print(f" ❌ Ошибка: {e}")
        
        self.sections = all_sections
        self.metadata = self._recalculate_metadata(all_sections)
        
        success = self.save_database()
        
        if success:
            print(f"\n✅ База создана!")
            print(f"   Всего документов: {self.metadata['total_documents']}")
            print(f"   Всего разделов: {self.metadata['total_sections']}")
            
        return all_sections
    
    def _split_document_by_type(self, content: str, file_path: Path, folder_type: str, 
                               doc_title: str, metadata: Dict = None) -> List[Dict]:
        """Разбиваем документ на разделы в зависимости от типа папки"""
        
        if folder_type == "normative":
            return self._split_normative_document(content, file_path, doc_title, metadata or {})
        elif folder_type == "methodology":
            return self._split_methodology_document(content, file_path, doc_title)
        elif folder_type == "structured":
            return self._split_structured_document(content, file_path, doc_title)
        elif folder_type == "expertise":
            return self._split_expertise_document(content, file_path, doc_title)
        else:
            return [{
                "title": doc_title,
                "content": content.strip() if content else "",
                "type": "full_document"
            }]
    
    def _split_normative_document(self, content: str, file_path: Path, doc_title: str, 
                                metadata: Dict) -> List[Dict]:
        """Разделение нормативных документов"""
        sections = []
        
        if not content:
            return [{
                "title": doc_title,
                "content": "",
                "type": "empty_document"
            }]
        
        content_to_process = content
        if content.strip().startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                content_to_process = parts[2].strip()
        
        # Разделение по главам
        lines = content_to_process.split('\n')
        current_section = []
        current_title = doc_title
        current_type = "document"
        
        chapter_pattern = re.compile(
            r'^(ГЛАВА|Глава)\s+'
            r'([IVXLCDM]+|\d+(?:\.\d+)*)'
            r'\.\s+'
            r'(.+)$'
        )
        
        for line in lines:
            line_stripped = line.strip()
            match = chapter_pattern.match(line_stripped)
            
            if match:
                if current_section:
                    sections.append({
                        "title": current_title,
                        "content": "\n".join(current_section).strip(),
                        "type": current_type
                    })
                
                chapter_word = match.group(1)
                chapter_number = match.group(2)
                chapter_name = match.group(3).strip()
                
                current_title = f"{chapter_word} {chapter_number}. {chapter_name}"
                current_type = "chapter"
                current_section = []
            else:
                current_section.append(line)
        
        if current_section:
            sections.append({
                "title": current_title,
                "content": "\n".join(current_section).strip(),
                "type": current_type
            })
        
        if not sections:
            sections.append({
                "title": doc_title,
                "content": content_to_process.strip(),
                "type": "full_document"
            })
        
        return sections
    
    def _split_methodology_document(self, content: str, file_path: Path, doc_title: str) -> List[Dict]:
        """Разделение методических документов"""
        return [{
            "title": doc_title,
            "content": content.strip() if content else "",
            "type": "methodology_document"
        }]
    
    def _split_structured_document(self, content: str, file_path: Path, doc_title: str) -> List[Dict]:
        """Разделение структурированных документов"""
        sections = []
        
        if not content:
            return [{
                "title": doc_title,
                "content": "",
                "type": "empty_document"
            }]
        
        content_to_process = content
        if content.strip().startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                content_to_process = parts[2].strip()
        
        lines = content_to_process.split('\n')
        current_section = []
        current_title = doc_title
        current_type = "document"
        
        bracket_pattern = r'^\[([^\[\]]+)\]$'
        
        for line in lines:
            line_stripped = line.strip()
            is_header = False
            
            match = re.match(bracket_pattern, line_stripped)
            if match:
                header_content = match.group(1).strip()
                
                if (len(header_content) > 3 and 
                    len(header_content) <= 200 and
                    re.search(r'[А-Яа-яЁёA-Za-z]', header_content)):
                    
                    if current_section:
                        sections.append({
                            "title": current_title,
                            "content": "\n".join(current_section).strip(),
                            "type": current_type
                        })
                    
                    current_title = header_content
                    current_type = "bracketed_section"
                    current_section = []
                    is_header = True
            
            if not is_header:
                current_section.append(line)
        
        if current_section:
            sections.append({
                "title": current_title,
                "content": "\n".join(current_section).strip(),
                "type": current_type
            })
        
        if not sections:
            sections.append({
                "title": doc_title,
                "content": content_to_process.strip(),
                "type": "full_document"
            })
        
        return sections
    
    def _split_expertise_document(self, content: str, file_path: Path, doc_title: str) -> List[Dict]:
        """Экспертные документы сохраняем полностью"""
        if not content:
            return [{
                "title": doc_title,
                "content": "",
                "type": "empty_document"
            }]
        
        content_to_process = content
        if content.strip().startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                content_to_process = parts[2].strip()
        
        return [{
            "title": doc_title,
            "content": content_to_process.strip(),
            "type": "expertise_document"
        }]
    
    def get_sections_for_display(self) -> List[Dict]:
        """Возвращает разделы для отображения"""
        display_data = []
        
        for section in self.sections:
            section_id = section.get("id", str(uuid.uuid4()))
            folder = section.get("folder", "unknown")
            doc_file = section.get("document", "")
            doc_ext = section.get("document_extension", ".txt")
            doc_title = section.get("document_title", doc_file)
            section_title = section.get("title", doc_title)
            content = section.get("content", "")
            word_count = section.get("word_count", 0)
            selected = section.get("selected", False)
            scan_date = section.get("scan_date", "")
            
            short_doc_title = doc_title[:40] + "..." if len(doc_title) > 40 else doc_title
            short_section_title = section_title[:60] + "..." if len(section_title) > 60 else section_title
            
            if folder == "structured" and not section_title.startswith("["):
                short_section_title = f"[{short_section_title}]"
                section_title = f"[{section_title}]"
            
            format_icon = {
                ".md": "📝",
                ".txt": "📄"
            }.get(doc_ext.lower(), "📎")
            
            date_info = ""
            if scan_date:
                try:
                    scan_date_obj = datetime.fromisoformat(scan_date.replace('Z', '+00:00'))
                    date_info = f" (сканировано: {scan_date_obj.strftime('%d.%m.%Y')})"
                except:
                    pass
            
            display_data.append({
                "id": section_id,
                "folder": folder,
                "document": f"{format_icon} {short_doc_title}{date_info}",
                "document_full": doc_title,
                "file": doc_file,
                "extension": doc_ext,
                "section": short_section_title,
                "section_full": section_title,
                "type": section.get("section_type", "text"),
                "words": word_count,
                "selected": selected,
                "content_full": content,
                "scan_date": scan_date
            })
        
        return display_data
    
    def update_selections(self, selected_ids: List[str]):
        """Обновляет выбор эксперта"""
        updated_count = 0
        for section in self.sections:
            section_id = section.get("id", "")
            old_selected = section.get("selected", False)
            new_selected = section_id in selected_ids
            
            if old_selected != new_selected:
                section["selected"] = new_selected
                updated_count += 1
        
        if updated_count > 0:
            self.save_database()
            print(f"💾 Обновлено {updated_count} выборов")
        
        return updated_count
    
    def get_selected_sections(self) -> List[Dict]:
        """Возвращает выбранные экспертом разделы"""
        return [s for s in self.sections if s.get("selected", False)]
    
    def clear_selections(self):
        """Очищает все выборы"""
        cleared_count = 0
        for section in self.sections:
            if section.get("selected", False):
                section["selected"] = False
                cleared_count += 1
        
        if cleared_count > 0:
            self.save_database()
            print(f"🗑️ Очищено {cleared_count} выборов")
        
        return cleared_count
    
    def export_selected_to_json(self, output_path: Path) -> bool:
        """Экспортирует выбранные разделы в JSON файл"""
        try:
            selected_sections = self.get_selected_sections()
            
            if not selected_sections:
                print("⚠ Нет выбранных разделов для экспорта")
                return False
            
            export_data = []
            
            for section in selected_sections:
                doc_title = section.get("document_title", "")
                section_title = section.get("title", "")
                content = section.get("content", "")
                
                if section.get("folder") == "structured" and not section_title.startswith("["):
                    section_title = f"[{section_title}]"
                
                export_data.append({
                    "title": doc_title,
                    "section_title": section_title,
                    "content": content
                })
            
            output_path.parent.mkdir(exist_ok=True, parents=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Экспортировано {len(selected_sections)} разделов в {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка экспорта в JSON: {e}")
            return False
    
    def get_database_stats(self) -> Dict:
        """Возвращает базовую статистику базы данных"""
        return {
            "total_sections": len(self.sections),
            "selected_sections": sum(1 for s in self.sections if s.get("selected", False)),
            "total_documents": self.metadata.get("total_documents", 0)
        }

# ==============================================
# СИСТЕМА УПРАВЛЕНИЯ СЕССИЯМИ (УПРОЩЕННАЯ)
# ==============================================

class SessionManager:
    """Упрощенное управление рабочими сессиями экспертов"""
    
    def __init__(self, sessions_path: str = None):
        self.sessions_path = Path(sessions_path or CONFIG["sessions_path"])
        self.sessions_path.mkdir(exist_ok=True, parents=True)
    
    def create_session(self, session_name: str = None, template_prompt: str = None) -> Optional[Path]:
        """Создает новую рабочую сессию"""
        try:
            if not session_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                session_name = f"session_{timestamp}"
            
            session_path = self.sessions_path / session_name
            session_path.mkdir(exist_ok=True, parents=True)
            
            # Создаем папку attachments (без управления файлами)
            attachments_dir = session_path / "attachments"
            attachments_dir.mkdir(exist_ok=True)
            
            templates_data = load_templates()
            selected_template = get_selected_template(templates_data)
            
            # Создаем только один файл промта
            prompt_file = session_path / "prompt.txt"
            
            if template_prompt:
                prompt_content = template_prompt
            else:
                prompt_content = selected_template.get("prompt", "") if selected_template else ""
            
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(prompt_content)
            
            print(f"✅ Создана сессия: {session_path}")
            return session_path
            
        except Exception as e:
            print(f"❌ Ошибка создания сессии: {e}")
            return None
    
    def get_session_info(self, session_path: Path) -> Dict:
        """Получает базовую информацию о сессии"""
        return {
            "session_name": session_path.name,
            "session_path": str(session_path),
            "created": datetime.fromtimestamp(session_path.stat().st_ctime).isoformat(),
            "has_prompt": (session_path / "prompt.txt").exists(),
            "has_materials": (session_path / "materials.json").exists(),
            "has_attachments": (session_path / "attachments").exists()
        }
    
    def list_sessions(self) -> List[Dict]:
        """Возвращает список всех сессий"""
        sessions = []
        
        for session_dir in self.sessions_path.glob("session_*"):
            if session_dir.is_dir():
                session_info = self.get_session_info(session_dir)
                sessions.append(session_info)
        
        sessions.sort(key=lambda x: x["created"], reverse=True)
        
        return sessions
    
    def delete_session(self, session_path: Path) -> bool:
        """Удаляет сессию"""
        try:
            if session_path.exists() and session_path.is_dir():
                shutil.rmtree(session_path)
                print(f"🗑️ Удалена сессия: {session_path}")
                return True
            else:
                print(f"⚠ Сессия не найдена: {session_path}")
                return False
        except Exception as e:
            print(f"❌ Ошибка удаления сессии: {e}")
            return False
    
    def export_to_session(self, session_path: Path, database: SimpleSectionDatabase) -> bool:
        """Экспортирует выбранные разделы в сессию"""
        try:
            materials_file = session_path / "materials.json"
            return database.export_selected_to_json(materials_file)
            
        except Exception as e:
            print(f"❌ Ошибка экспорта в сессию: {e}")
            return False

# ==============================================
# ЗАГРУЗКА КОНФИГУРАЦИИ
# ==============================================

CONFIG = load_config()
DEFAULT_PROMPT = load_default_prompt()
SUPPORTED_EXTENSIONS = CONFIG.get("supported_extensions", [".md", ".txt"])

if not Path(CONFIG["folders"]["normative"]).exists():
    created = create_default_folders(CONFIG["folders"])
    if created:
        print(f"📁 Созданы папки по умолчанию:")
        for folder_type, path in created:
            print(f"   - {folder_type}: {path}")

folder_status = validate_folders(CONFIG["folders"])
if not folder_status["all_exist"]:
    print("⚠ Предупреждение: некоторые папки недоступны:")
    for folder_type, path in folder_status["missing"]:
        print(f"   - {folder_type}: {path}")

# ==============================================
# ВЕБ-ИНТЕРФЕЙС
# ==============================================

st.markdown("""
<style>
.section-item {
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    margin-bottom: 4px;
    background-color: white;
    transition: all 0.2s;
}
.section-item:hover {
    border-color: #4CAF50;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.section-header {
    font-weight: 600;
    font-size: 0.9rem;
    margin-bottom: 2px;
}
.section-meta {
    font-size: 0.75rem;
    margin-bottom: 2px;
}
.section-title {
    font-weight: 500;
    font-size: 0.85rem;
    margin-top: 2px;
    margin-bottom: 0;
}
.selected-section {
    border-color: #4CAF50;
    background-color: #f8fff8;
}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_database():
    return SimpleSectionDatabase()

@st.cache_resource
def init_session_manager():
    return SessionManager()

if 'db' not in st.session_state:
    st.session_state.db = init_database()
    st.session_state.session_manager = init_session_manager()
    st.session_state.current_session = None
    st.session_state.has_unsaved_changes = False

db = st.session_state.db
session_manager = st.session_state.session_manager


#st.set_page_config(
#    layout="wide",
#    initial_sidebar_state="expanded"    
#)

tab1, tab2, tab3 = st.tabs([
    "📋 Выбор разделов",
    "📁 Рабочие сессии", 
    "⚙️ Настройки"
])

with tab1:
    st.subheader("📋 ВЫБОР РАЗДЕЛОВ ДЛЯ ЭКСПЕРТНОГО ОТВЕТА")
    
    display_data = db.get_sections_for_display()
    
    if not display_data:
        st.info("База пуста. Нажмите 'Сканировать папки' в боковой панели.")
    else:
        with st.container():
            col1, col2 = st.columns([0.3, 0.7])
            
            with col1:
                search_text = st.text_input("Поиск:", placeholder="По документу или разделу...", key="search_input_tab1")
            
            with col2:
                doc_options = list(set(item["document_full"] for item in display_data))
                doc_options.sort()
                doc_filter = st.multiselect(
                    "Фильтр по документу:",
                    options=doc_options,
                    format_func=lambda x: x[:40] + "..." if len(x) > 40 else x,
                    help="Выберите конкретный документ",
                    key="doc_filter_tab1"
                )
        
        filtered_data = display_data.copy()
        
        if search_text:
            search_lower = search_text.lower()
            filtered_data = [
                item for item in filtered_data
                if (search_lower in item["document_full"].lower() or
                    search_lower in item["section_full"].lower())
            ]
        
        if doc_filter:
            filtered_data = [item for item in filtered_data if item["document_full"] in doc_filter]
        
        with st.container():
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            
            with col_stat1:
                st.metric("Найдено", len(filtered_data), delta=f"из {len(display_data)}")
            
            with col_stat2:
                selected_count = sum(1 for item in filtered_data if item["selected"])
                total_selected = sum(1 for item in display_data if item["selected"])
                st.metric("Выбрано", selected_count)
            
            with col_stat3:
                if st.button("✅ Выбрать все", use_container_width=True, key="select_all_tab1"):
                    for item in filtered_data:
                        for section in db.sections:
                            if section.get("id") == item["id"]:
                                section["selected"] = True
                    st.session_state.has_unsaved_changes = True
                    st.success(f"Выбрано {len(filtered_data)}")
                    st.rerun()
            
            with col_stat4:
                if st.button("❌ Снять все", use_container_width=True, key="deselect_all_tab1"):
                    for item in filtered_data:
                        for section in db.sections:
                            if section.get("id") == item["id"]:
                                section["selected"] = False
                    st.session_state.has_unsaved_changes = True
                    st.info(f"Снято {len(filtered_data)}")
                    st.rerun()
        
        if filtered_data:
            changes_made = False
            
            with st.container():
                for idx, item in enumerate(filtered_data):
                    css_class = "section-item"
                    if item["selected"]:
                        css_class += " selected-section"
                    
                    col_check, col_content = st.columns([0.4, 11.6])
                    
                    with col_check:
                        current_selected = item["selected"]
                        new_selected = st.checkbox(
                            "",
                            value=current_selected,
                            key=f"select_{item['id']}_{search_text}_{doc_filter}",
                            label_visibility="collapsed"
                        )
                        
                        if new_selected != current_selected:
                            for section in db.sections:
                                if section.get("id") == item["id"]:
                                    section["selected"] = new_selected
                                    changes_made = True
                                    break
                    
                    with col_content:
                        st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
                        
                        folder_icon = {
                            "normative": "📖",
                            "methodology": "📚",
                            "structured": "🗂️",
                            "expertise": "👨‍⚖️"
                        }.get(item["folder"], "📄")
                        
                        st.markdown(
                            f'<div class="section-header">'
                            f'<span style="font-weight: 600; color: inherit;">{folder_icon} {item["document"]}</span>'
                            f'</div>', 
                            unsafe_allow_html=True
                        )
                        
                        meta_info = []
                        meta_info.append(f"Формат: {item.get('extension', '.txt')}")
                        meta_info.append(f"Слов: {item['words']}")
                        if item["selected"]:
                            meta_info.append("✅ Выбрано")
                        
                        st.markdown(f'<div class="section-meta">{" • ".join(meta_info)}</div>', 
                                unsafe_allow_html=True)
                        
                        st.markdown(
                            f'<div class="section-title">'
                            f'<span style="font-weight: 500; color: inherit;">{item["section"]}</span>'
                            f'</div>', 
                            unsafe_allow_html=True
                        )
                        
                        st.markdown('</div>', unsafe_allow_html=True)
            
            if changes_made:
                st.session_state.has_unsaved_changes = True
            
            st.markdown("---")
            
            with st.container():
                col_manage1, col_manage2 = st.columns(2)
                
                with col_manage1:
                    save_disabled = not st.session_state.has_unsaved_changes
                    
                    if st.button("💾 Сохранить выбор", type="primary", 
                               disabled=save_disabled, use_container_width=True, key="save_tab1"):
                        db.save_database()
                        st.success("✅ Выбор сохранен!")
                        st.session_state.has_unsaved_changes = False
                        st.rerun()
                
                with col_manage2:
                    if st.session_state.has_unsaved_changes:
                        st.warning("⚠️ Есть несохраненные изменения")
                    else:
                        st.info("💾 Все сохранено")
        
        else:
            st.info("Нет разделов, соответствующих выбранным фильтрам.")

with tab2:
    st.subheader("📁 УПРАВЛЕНИЕ РАБОЧИМИ СЕССИЯМИ")
    
    col_create1, col_create2 = st.columns([3, 1])
    
    with col_create1:
        new_session_name = st.text_input(
            "Имя сессии (оставьте пустым для автоимени):",
            placeholder="session_жалоба",
            key="new_session_name"
        )
    
    with col_create2:
        if st.button("📁 Создать", type="primary", use_container_width=True):
            templates_data = load_templates()
            selected_template = get_selected_template(templates_data)
            template_prompt = selected_template.get("prompt", "") if selected_template else ""
            
            session_path = session_manager.create_session(
                session_name=new_session_name.strip() if new_session_name else None,
                template_prompt=template_prompt
            )
            
            if session_path:
                st.session_state.current_session = str(session_path)
                st.success(f"✅ Создана сессия: {session_path.name}")
                st.success(f"📝 Шаблон: {selected_template['name'] if selected_template else 'Неизвестно'}")
                st.rerun()
            else:
                st.error("❌ Ошибка при создании сессии")
    
    st.markdown("---")
    
    sessions = session_manager.list_sessions()
    
    if not sessions:
        st.info("📭 Нет созданных сессий")
    else:
        st.markdown(f"### 📂 ВСЕГО СЕССИЙ: {len(sessions)}")
        
        search_term = st.text_input("🔍 Поиск сессии:", 
                                  placeholder="Введите часть имени...")
        
        if search_term:
            filtered_sessions = [s for s in sessions if search_term.lower() in s['session_name'].lower()]
        else:
            filtered_sessions = sessions
        
        for session_info in filtered_sessions:
            with st.expander(f"📁 {session_info['session_name']}", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    created_date = session_info['created'][:10]
                    st.caption(f"Создана: {created_date}")
                    
                    status_parts = []
                    if session_info['has_prompt']:
                        status_parts.append("🎯 Промт")
                    if session_info['has_materials']:
                        status_parts.append("📚 Материалы")
                    if session_info['has_attachments']:
                        status_parts.append("📎 Папка для вложений")
                    
                    if status_parts:
                        st.caption(" • ".join(status_parts))
                    else:
                        st.caption("📭 Пустая сессия")
                
                with col2:
                    is_current = (st.session_state.current_session == session_info['session_path'])
                    
                    if not is_current:
                        if st.button("Выбрать", 
                                   key=f"select_{session_info['session_name']}",
                                   use_container_width=True):
                            st.session_state.current_session = session_info['session_path']
                            st.success(f"✅ Выбрана сессия: {session_info['session_name']}")
                            st.rerun()
                    else:
                        st.success("✅ Активна")
                
                col_act1, col_act2, col_act3 = st.columns(3)
                
                with col_act1:
                    selected_count = sum(1 for section in db.sections if section.get("selected", False))
                    
                    if selected_count > 0:
                        if st.button("📤 Экспорт", 
                                   key=f"export_{session_info['session_name']}",
                                   use_container_width=True):
                            session_path = Path(session_info['session_path'])
                            success = session_manager.export_to_session(session_path, db)
                            
                            if success:
                                st.success(f"✅ Экспортировано {selected_count} разделов")
                                st.rerun()
                            else:
                                st.error("❌ Ошибка экспорта")
                    else:
                        st.caption("Нет выборки")
                
                with col_act2:
                    if st.button("👁️ Просмотр", 
                               key=f"view_{session_info['session_name']}",
                               use_container_width=True):
                        session_path = Path(session_info['session_path'])
                        st.info(f"**Содержимое сессии:** {session_info['session_name']}")
                        
                        if session_info['has_prompt']:
                            st.write("**Промт:** присутствует (prompt.txt)")
                        else:
                            st.write("**Промт:** отсутствует")
                        
                        if session_info['has_materials']:
                            st.write("**Материалы:** присутствуют (materials.json)")
                        else:
                            st.write("**Материалы:** отсутствуют")
                        
                        if session_info['has_attachments']:
                            st.write("**Вложения:** есть папка для файлов")
                        else:
                            st.write("**Вложения:** нет папки")
                
                with col_act3:
                    if st.button("🗑️ Удалить", 
                               key=f"delete_{session_info['session_name']}",
                               type="secondary",
                               use_container_width=True):
                        session_path = Path(session_info['session_path'])
                        
                        try:
                            if session_path.exists() and session_path.is_dir():
                                shutil.rmtree(session_path)
                                
                                if st.session_state.current_session == str(session_path):
                                    st.session_state.current_session = None
                                
                                st.success(f"✅ Сессия '{session_info['session_name']}' удалена")
                                st.rerun()
                            else:
                                st.error("❌ Сессия не найдена")
                                st.rerun()
                                
                        except Exception as e:
                            st.error(f"❌ Ошибка при удалении: {e}")
    
    st.markdown("---")
    
    if st.session_state.current_session:
        current_path = Path(st.session_state.current_session)
        
        if current_path.exists():
            st.markdown(f"### ✅ АКТИВНАЯ СЕССИЯ: **{current_path.name}**")
            
            session_info = session_manager.get_session_info(current_path)
            
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            
            with col_stat1:
                if session_info['has_prompt']:
                    st.success("🎯 Есть промт")
                else:
                    st.warning("📭 Нет промта")
            
            with col_stat2:
                if session_info['has_materials']:
                    st.success("📚 Есть материалы")
                else:
                    st.warning("📭 Нет материалов")
            
            with col_stat3:
                if session_info['has_attachments']:
                    st.info("📎 Есть папка для вложений")
                else:
                    st.info("📎 Нет папки для вложений")
            
            selected_count = sum(1 for section in db.sections if section.get("selected", False))
            
            if selected_count > 0:
                if st.button("🚀 БЫСТРЫЙ ЭКСПОРТ В АКТИВНУЮ СЕССИЮ", 
                           type="primary", 
                           use_container_width=True):
                    success = session_manager.export_to_session(current_path, db)
                    
                    if success:
                        st.success(f"✅ Экспортировано {selected_count} разделов")
                        st.rerun()
                    else:
                        st.error("❌ Ошибка экспорта")
            else:
                st.info("ℹ️ Выберите разделы во вкладке 'Выбор разделов' для экспорта")
        else:
            st.error("❌ Активная сессия не найдена")
            st.session_state.current_session = None
    else:
        st.info("📭 Нет активной сессии. Выберите или создайте сессию.")

with tab3:
    st.subheader("⚙️ НАСТРОЙКИ СИСТЕМЫ")
    
    col_info1, col_info2 = st.columns(2)
    
    with col_info1:
        stats = db.get_database_stats()
        st.metric("Всего разделов в базе", stats["total_sections"])
    
    with col_info2:
        st.metric("Выбрано разделов", stats["selected_sections"])
    
    st.markdown("---")
    
    st.markdown("### 📊 ОСНОВНЫЕ ОПЕРАЦИИ")
    
    col_db1, col_db2, col_db3 = st.columns(3)
    
    with col_db1:
        if st.button("🔍 Сканировать папки", type="primary", use_container_width=True):
            with st.spinner("Сканирую папки..."):
                db.scan_and_build_database()
                st.success("✅ База данных обновлена!")
                st.rerun()
    
    with col_db2:
        if st.button("🗑️ Очистить все выборы", type="secondary", use_container_width=True):
            cleared = db.clear_selections()
            if cleared > 0:
                st.success(f"✅ Очищено {cleared} выборов")
                st.session_state.has_unsaved_changes = False
                st.rerun()
            else:
                st.info("ℹ️ Нет выбранных разделов для очистки")
    
    with col_db3:
        if st.button("📤 Экспорт выбранных", type="secondary", use_container_width=True):
            selected_count = sum(1 for section in db.sections if section.get("selected", False))
            if selected_count > 0:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                export_path = Path(CONFIG["sessions_path"]) / f"selected_sections_{timestamp}.json"
                
                success = db.export_selected_to_json(export_path)
                if success:
                    st.success(f"✅ Экспортировано {selected_count} разделов")
                    
                    with open(export_path, 'r', encoding='utf-8') as f:
                        export_data = f.read()
                    
                    st.download_button(
                        label=f"⬇️ Скачать {export_path.name}",
                        data=export_data,
                        file_name=export_path.name,
                        mime="application/json",
                        use_container_width=True
                    )
                else:
                    st.error("❌ Ошибка экспорта")
            else:
                st.info("ℹ️ Нет выбранных разделов для экспорта")
    
    st.markdown("---")
    st.markdown("### 🎯 ВЫБОР ШАБЛОНА ВОПРОСА")
    
    templates_data = load_templates()
    selected_template = get_selected_template(templates_data)
    
    if selected_template:
        st.info(f"**Текущий шаблон:** {selected_template['name']}")
        st.caption(f"{selected_template['description']}")
    else:
        st.warning("⚠️ Нет доступных шаблонов")
    
    if templates_data:
        template_options = {t["id"]: t["name"] for t in templates_data}
        selected_id = st.radio(
            "Выберите шаблон для новых сессий:",
            options=list(template_options.keys()),
            format_func=lambda x: template_options[x],
            index=list(template_options.keys()).index(selected_template["id"]) if selected_template else 0,
            key="template_selector"
        )
        
        col_template1, col_template2 = st.columns([1, 2])
        
        with col_template1:
            if st.button("💾 Сохранить выбор шаблона", type="primary", use_container_width=True):
                updated_templates = update_selected_template(templates_data, selected_id)
                if save_templates(updated_templates):
                    st.success(f"✅ Шаблон сохранен: {template_options[selected_id]}")
                    st.rerun()
        
        with col_template2:
            selected_prompt = next((t["prompt"] for t in templates_data if t["id"] == selected_id), "")
            
            if st.button("👁️ Просмотр промта шаблона", use_container_width=True):
                with st.expander("📝 Промт шаблона", expanded=True):
                    st.text_area("", value=selected_prompt, height=300, disabled=True, key="template_preview")
    else:
        st.info("📭 Нет доступных шаблонов")
    
    st.markdown("---")
    st.markdown("### 📄 КОНФИГУРАЦИЯ")
    
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config_content = f.read()
        
        st.download_button(
            label="⬇️ Скачать config.json",
            data=config_content,
            file_name="config.json",
            mime="application/json",
            use_container_width=True
        )
        
        with st.expander("👁️ Показать конфигурацию"):
            st.code(config_content, language="json")
    else:
        st.info("Файл config.json не найден")
        
        if st.button("📄 Создать config.json", type="primary"):
            if save_config(CONFIG):
                st.success("✅ Файл config.json создан")
                st.rerun()
    
    st.markdown("---")
    st.markdown("### 📋 ВСЕ ШАБЛОНЫ")
    
    if templates_data:
        for template in templates_data:
            is_selected = template.get("selected", False)
            badge = "✅" if is_selected else ""
            
            with st.expander(f"{badge} {template['name']}", expanded=False):
                st.caption(template["description"])
                st.text_area("Промт:", value=template["prompt"], height=200, disabled=True, key=f"prompt_{template['id']}")
    else:
        st.info("📭 Нет доступных шаблонов")

with st.sidebar:
    st.header("📊 СТАТИСТИКА")
    
    stats = db.get_database_stats()
    
    st.metric("Всего разделов", stats["total_sections"])
    st.metric("Всего документов", stats["total_documents"])
    
    selected_count = stats["selected_sections"]
    st.metric("Выбрано разделов", selected_count)
    
    st.markdown("---")
    st.header("🎯 ШАБЛОН ВОПРОСА")
    
    templates_data = load_templates()
    selected_template = get_selected_template(templates_data)
    if selected_template:
        st.caption(f"{selected_template['name']}")
        st.caption(f"{selected_template['description'][:60]}...")
    else:
        st.caption("📭 Нет шаблона")
    
    st.markdown("---")
    st.header("⚡ БЫСТРЫЕ ДЕЙСТВИЯ")
    
    if st.session_state.has_unsaved_changes:
        if st.button("💾 Сохранить выбор", type="primary", use_container_width=True):
            db.save_database()
            st.success("Сохранено!")
            st.session_state.has_unsaved_changes = False
            st.rerun()
    
    if st.session_state.current_session and selected_count > 0:
        if st.button("📤 Экспорт в активную сессию", type="secondary", use_container_width=True):
            session_path = Path(st.session_state.current_session)
            success = session_manager.export_to_session(session_path, db)
            
            if success:
                st.success(f"✅ Экспортировано {selected_count} разделов")
                st.rerun()
    
    if st.button("📁 Создать новую сессию", type="secondary", use_container_width=True):
        templates_data = load_templates()
        selected_template = get_selected_template(templates_data)
        template_prompt = selected_template.get("prompt", "") if selected_template else ""
        
        session_path = session_manager.create_session(template_prompt=template_prompt)
        if session_path:
            st.session_state.current_session = str(session_path)
            st.success(f"Создана сессия с шаблоном: {selected_template['name'] if selected_template else 'Без шаблона'}")
            st.rerun()
    
    st.markdown("---")
    st.header("🛠️ АДМИНИСТРАТИВНЫЕ")
    
    if st.button("🔍 Сканировать папки", use_container_width=True, 
               help="Ручное сканирование папок с документами"):
        with st.spinner("Сканирую..."):
            db.scan_and_build_database()
            st.success("Сканирование завершено!")
            st.rerun()
    
    if selected_count > 0:
        if st.button(f"📤 Экспорт разделов ({selected_count})", use_container_width=True):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = Path(CONFIG["sessions_path"]) / f"export_{timestamp}.json"
            success = db.export_selected_to_json(export_path)
            
            if success:
                st.success(f"Экспортировано {selected_count} разделов")
                with open(export_path, 'r', encoding='utf-8') as f:
                    st.download_button(
                        label="⬇️ Скачать",
                        data=f.read(),
                        file_name=export_path.name,
                        mime="application/json"
                    )
    
    if st.button("🎯 Изменить шаблон", use_container_width=True):
        st.session_state.active_tab = "tab3"
        st.rerun()
    
    st.markdown("---")
    
    if st.session_state.current_session:
        session_path = Path(st.session_state.current_session)
        if session_path.exists():
            st.header("✅ АКТИВНАЯ СЕССИЯ")
            st.markdown(f"**{session_path.name}**")
            
            session_info = session_manager.get_session_info(session_path)
            
            if session_info['has_prompt']:
                st.caption("🎯 Есть промт")
            
            if session_info['has_materials']:
                st.caption("📚 Есть материалы")
            
            if session_info['has_attachments']:
                st.caption("📎 Есть папка для вложений")
            
            if st.button("📂 Открыть папку", use_container_width=True):
                st.info(f"Путь: `{session_path}`")
        else:
            st.warning("❌ Сессия не найдена")
            st.session_state.current_session = None
    else:
        st.info("📭 Нет активной сессии")

print("\n" + "="*60)
print("🚀 Экспертная система запущена!")
print("="*60)