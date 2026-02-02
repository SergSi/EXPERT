import os
import re
import json
import yaml
import chardet
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd
from datetime import datetime
import uuid
import streamlit as st
import shutil
import tempfile

# ==============================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ШАБЛОНАМИ
# ==============================================

def load_templates():
    """
    Загружает шаблоны из templates.json
    """
    # Получаем путь из конфигурации или используем путь по умолчанию
    templates_path_str = CONFIG.get("templates_path", "")
    
    if templates_path_str:
        templates_path = Path(templates_path_str)
    else:
        # Если путь не указан в конфигурации, используем путь по умолчанию
        project_dir = Path(__file__).parent
        templates_path = project_dir / "templates.json"
    
    if templates_path.exists():
        try:
            with open(templates_path, 'r', encoding='utf-8') as f:
                templates_data = json.load(f)
                print(f"✅ Шаблоны загружены из {templates_path}")
                # Проверяем структуру - должна быть список
                if isinstance(templates_data, list):
                    return templates_data
                else:
                    # Конвертируем старую структуру в новую
                    print(f"⚠ Конвертируем старую структуру шаблонов в новую")
                    if "templates" in templates_data:
                        templates_list = templates_data["templates"]
                        if templates_list and len(templates_list) > 0:
                            return templates_list
        except Exception as e:
            print(f"❌ Ошибка загрузки шаблонов: {e}")
    
    # Шаблоны по умолчанию если файл не найден или поврежден
    print(f"⚠ Файл шаблонов не найден: {templates_path}")
    return [
        {
            "id": "standard",
            "name": "📝 Стандартный ответ",
            "description": "Развернутый профессиональный ответ с анализом",
            "prompt": "Ты — эксперт в области землепользования и кадастра.\n\nНа основе предоставленных материалов подготовь развернутый профессиональный ответ.\n\nИНСТРУКЦИЯ:\n1. Проанализируй все предоставленные материалы\n2. Используй информацию ТОЛЬКО из предоставленных материалов\n3. Не используй внешние знания или предположения\n\nСТРУКТУРА ОТВЕТА:\n1. ПОВТОРЕНИЕ ВОПРОСА: Сформулируй исходный вопрос своими словами, показывая правильное понимание и задавая рамки анализа\n2. Краткий ответ: 2-3 предложения с дословным ответом\n3. Детальный ответ с анализом (только на основе материалов)\n4. Практические рекомендации (обоснованные материалами)\n5. Выводы\n6. НЕДОСТАЮЩИЕ СВЕДЕНИЯ (при необходимости): Конкретный перечень того, чего не хватает в материалах\n\nОТВЕТ ЭКСПЕРТА:",
            "selected": True
        }
    ]

def save_templates(templates_data):
    """
    Сохраняет шаблоны в templates.json
    """
    # Получаем путь из конфигурации или используем путь по умолчанию
    templates_path_str = CONFIG.get("templates_path", "")
    
    if templates_path_str:
        templates_path = Path(templates_path_str)
    else:
        # Если путь не указан в конфигурации, используем путь по умолчанию
        project_dir = Path(__file__).parent
        templates_path = project_dir / "templates.json"
    
    try:
        # Создаем папку если не существует
        templates_path.parent.mkdir(exist_ok=True, parents=True)
        
        with open(templates_path, 'w', encoding='utf-8') as f:
            json.dump(templates_data, f, ensure_ascii=False, indent=2)
        print(f"✅ Шаблоны сохранены в {templates_path}")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения шаблонов: {e}")
        return False

def get_selected_template(templates_data):
    """
    Возвращает выбранный шаблон
    """
    if not templates_data:
        return None
    
    for template in templates_data:
        if template.get("selected", False):
            return template
    
    # Если ни один не выбран, возвращаем первый
    return templates_data[0] if templates_data else None

def update_selected_template(templates_data, selected_id):
    """
    Обновляет выбранный шаблон
    """
    for template in templates_data:
        template["selected"] = (template["id"] == selected_id)
    
    return templates_data

# ==============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ КОНФИГУРАЦИИ
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
        "allow_database_export": True,
        "allow_database_import": True,
        "max_upload_size_mb": 100
    }

def load_config():
    """
    Загружает конфигурацию из JSON файла.
    Если файл не найден или поврежден, используются значения по умолчанию.
    """
    config_path = Path(__file__).parent / "config.json"
    
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print(f"✅ Конфигурация загружена из {config_path}")
                
                # Проверяем и добавляем отсутствующие ключи
                default_config = get_default_config()
                for key, value in default_config.items():
                    if key not in config:
                        print(f"⚠ В конфигурации отсутствует ключ: {key}. Используется значение по умолчанию.")
                        config[key] = value
                
                return config
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка в формате JSON (строка {e.lineno}, позиция {e.pos}): {e.msg}")
            print("⚠ Используются значения по умолчанию.")
            return get_default_config()
        except Exception as e:
            print(f"❌ Ошибка загрузки конфигурации: {e}")
            print("⚠ Используются значения по умолчанию.")
            return get_default_config()
    
    # Конфигурация по умолчанию если файл не найден или поврежден
    print("⚠ Файл config.json не найден. Используются значения по умолчанию.")
    return get_default_config()

def save_config(config):
    """
    Сохраняет конфигурацию в JSON файл.
    """
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
    """
    Проверяет существование папок из конфигурации.
    """
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
    """
    Создает папки по умолчанию если они не существуют.
    """
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
    """
    Загружает промт из выбранного шаблона
    """
    templates_data = load_templates()
    selected_template = get_selected_template(templates_data)
    return selected_template.get("prompt", "") if selected_template else ""

# ==============================================
# ЗАГРУЗКА КОНФИГУРАЦИИ И ИНИЦИАЛИЗАЦИЯ
# ==============================================

# Загружаем конфигурацию
CONFIG = load_config()

# Загружаем стандартный промт из выбранного шаблона
DEFAULT_PROMPT = load_default_prompt()

# Получаем список поддерживаемых расширений
SUPPORTED_EXTENSIONS = CONFIG.get("supported_extensions", [".md", ".txt"])

# Создаем необходимые папки по умолчанию (если используются пути по умолчанию)
if not Path(CONFIG["folders"]["normative"]).exists():
    created = create_default_folders(CONFIG["folders"])
    if created:
        print(f"📁 Созданы папки по умолчанию:")
        for folder_type, path in created:
            print(f"   - {folder_type}: {path}")

# Проверяем доступность папки
folder_status = validate_folders(CONFIG["folders"])
if not folder_status["all_exist"]:
    print("⚠ Предупреждение: некоторые папки недоступны:")
    for folder_type, path in folder_status["missing"]:
        print(f"   - {folder_type}: {path}")
    print("ℹ️ Проверьте пути в файле config.json")

# Проверяем доступность файла шаблонов
templates_path_str = CONFIG.get("templates_path", "")
if templates_path_str:
    templates_path = Path(templates_path_str)
    if not templates_path.exists():
        print(f"⚠ Файл шаблонов не найден: {templates_path}")
        # Создаем файл с шаблонами по умолчанию
        templates_data = load_templates()  # Загрузит шаблоны по умолчанию
        save_templates(templates_data)

# ==============================================
# КЛАСС ДЛЯ РАБОТЫ С РАЗНЫМИ ФОРМАТАМИ ФАЙЛОВ
# ==============================================

class FileFormatReader:
    """Класс для чтения текстовых файлов"""
    
    @staticmethod
    def read_file(file_path: Path) -> Optional[str]:
        """
        Читает текстовый файл.
        Возвращает текст или None в случае ошибки.
        """
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
        """Читает текстовые файлы (TXT, MD) с определением кодировки"""
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
            
            # Последняя попытка
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
        self.file_reader = FileFormatReader()  # Добавляем ридер файлов
        
        # Создаем папку для базы данных если не существует
        self.db_path.mkdir(exist_ok=True, parents=True)
        
        # Загружаем существующую базу или создаем новую
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
                print(f"   Строка: {e.lineno}, позиция: {e.pos}")
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
                print(f"   Создаю новые метаданные...")
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
            "by_folder": {},
            "format_stats": {},
            "supported_extensions": SUPPORTED_EXTENSIONS,
            "version": "1.0"
        }
    
    def _clean_text_from_comments(self, text: str) -> str:
        """Очищает текст от примечаний КонсультантПлюс/ГАРАНТ и служебных пометок"""
        if not text:
            return text
        
        cleaned_text = text
        
        # 1. Удаляем строки, начинающиеся с КонсультантПлюс примечаний
        consultant_patterns = [
            r'КонсультантПлюс: примечание\.[^\n]*\n',
            r'\[Консультант[^\]]*примечание[^\]]*\][^\n]*\n',
        ]
        
        for pattern in consultant_patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.MULTILINE)
        
        # 2. Удаляем блоки ГАРАНТ
        garant_patterns = [
            r'ГАРАНТ:\s*\n\s*См\. [^\n]*\n',
            r'ГАРАНТ:\s*\n\s*[^\n]*См\. [^\n]*\n',
            r'^\s*См\.\s+Энциклопедии[^\n]*\n',
            r'^\s*См\.\s+схему[^\n]*\n',
            r'^\s*См\.\s+позиции[^\n]*\n',
            r'^\s*См\.\s+[^\n]*к статье[^\n]*\n',
            r'^\s*См\.\s+Федеральный закон[^\n]*\n',
        ]
        
        for pattern in garant_patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.MULTILINE)
        
        # 3. Удаляем информационные блоки об изменениях
        change_info_patterns = [
            r'Информация об изменениях:\s*\n',
            r'Изменения вступают в силу[^\n]*\n',
            r'См\.\s*(?:будущую|предыдущую|текст)[^\n]*редакцию[^\n]*\n',
        ]
        
        for pattern in change_info_patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.MULTILINE)
        
        # 4. Удаляем другие служебные пометки
        service_patterns = [
            r'С \d{2}\.\d{2}\.\d{4}[^\n]*\n',
            r'<\d+>',
            r'--------------------------------\s*\n<[0-9]+>.*?\n',
        ]
        
        for pattern in service_patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.DOTALL)
        
        # 5. Удаляем простые юридические пометки
        legal_patterns = [
            r'\(в ред\. [^)]*\)',
            r'\(введена [^)]*\)',
            r'ред\. \d{2}\.\d{2}\.\d{4}',
            r'©.*',
        ]
        
        for pattern in legal_patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)
        
        # 6. Удаляем строки с конкретными служебными фразами ГАРАНТ
        lines = cleaned_text.split('\n')
        cleaned_lines = []
        
        skip_next_line = False
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Если предыдущая строка была "ГАРАНТ:", пропускаем текущую строку
            if skip_next_line:
                skip_next_line = False
                continue
            
            # Проверяем, является ли строка служебной пометкой ГАРАНТ
            is_garant_service_line = (
                line_stripped.startswith('ГАРАНТ:') or
                line_stripped.startswith('См. ') or
                line_stripped.startswith('См ') or
                'Федеральным законом от' in line_stripped and 'N' in line_stripped or
                'Подпункт' in line_stripped and 'изменен' in line_stripped or
                'Пункт' in line_stripped and 'изменен' in line_stripped and not line_stripped.startswith('Пункт 1.') or
                'Статья' in line_stripped and ('дополнена' in line_stripped or 'изменена' in line_stripped) and not line_stripped.startswith('Статья 1.') or
                line_stripped == 'Информация об изменениях:' or
                'консультант' in line_stripped.lower()
            )
            
            # Если это служебная строка ГАРАНТ, пропускаем ее
            if is_garant_service_line:
                if line_stripped.startswith('ГАРАНТ:'):
                    skip_next_line = True
                continue
            
            # Сохраняем строку
            cleaned_lines.append(line)
        
        cleaned_text = '\n'.join(cleaned_lines)
        
        # 7. Удаляем пустые строки
        lines = cleaned_text.split('\n')
        cleaned_lines = []
        previous_was_empty = False
        
        for line in lines:
            line_stripped = line.strip()
            
            if not line_stripped:
                if not previous_was_empty:
                    cleaned_lines.append('')
                    previous_was_empty = True
            else:
                if not (line_stripped.startswith('N ') or 
                       re.match(r'^N\s+\d+', line_stripped) or
                       line_stripped.startswith('Изменен') and 'г.' in line_stripped):
                    cleaned_lines.append(line)
                    previous_was_empty = False
        
        cleaned_text = '\n'.join(cleaned_lines)
        
        # 8. Финализация
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
        cleaned_text = cleaned_text.strip()
        
        return cleaned_text
    
    def _clean_special_characters(self, text: str) -> str:
        """Очищает текст от специальных символов и форматирования"""
        if not text:
            return text
        
        cleaned = re.sub(r'[ \t]+', ' ', text)
        cleaned = cleaned.replace('\xad', '')
        cleaned = cleaned.replace('\xa0', ' ')
        cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        cleaned = cleaned.strip()
        cleaned = re.sub(r' +', ' ', cleaned)
        
        lines = cleaned.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)
        
        cleaned = '\n'.join(cleaned_lines)
        
        return cleaned
    
    def _extract_yaml_metadata(self, content: str) -> Dict:
        """Извлекает метаданные из YAML заголовка"""
        metadata = {}
        
        try:
            content_stripped = content.strip()
            # Ищем YAML заголовок между ---
            if content_stripped.startswith('---'):
                parts = content_stripped.split('---', 2)
                if len(parts) >= 3:
                    yaml_content = parts[1].strip()
                    if yaml_content:
                        # Загружаем YAML
                        metadata = yaml.safe_load(yaml_content) or {}
                        if not isinstance(metadata, dict):
                            metadata = {}
                        
                        # Обрабатываем extract_only и extract_ranges
                        for key in ['extract_only', 'extract_ranges']:
                            if key in metadata and isinstance(metadata[key], list):
                                # Конвертируем все элементы в строки и очищаем от пробелов
                                metadata[key] = [
                                    str(item).strip() for item in metadata[key]
                                ]
        except (yaml.YAMLError, AttributeError) as e:
            print(f"  ⚠ Не удалось прочитать YAML: {e}")
        
        return metadata
    
    def _normalize_article_number(self, article_num: str) -> str:
        """
        Нормализует номер статьи для сравнения
        Примеры:
        - "6" → "6"
        - "6.1" → "6.1"
        - "6.1.1" → "6.1.1"
        """
        return article_num.strip()        
        
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
            import traceback
            traceback.print_exc()
            return False
    
    def _recalculate_metadata(self, sections: List[Dict]) -> Dict:
        """Пересчитывает метаданные на основе списка разделов"""
        if not sections:
            return self._create_default_metadata()
        
        unique_documents = set()
        folder_stats = {}
        format_stats = {}
        
        for section in sections:
            doc_path = section.get("document_path", "")
            doc_name = section.get("document", "")
            if doc_path or doc_name:
                doc_key = f"{doc_path}_{doc_name}"
                unique_documents.add(doc_key)
            
            folder = section.get("folder", "unknown")
            if folder not in folder_stats:
                folder_stats[folder] = {
                    "documents": set(),
                    "sections": 0,
                    "words": 0,
                    "formats": {}
                }
            
            if doc_path or doc_name:
                folder_stats[folder]["documents"].add(doc_key)
            
            folder_stats[folder]["sections"] += 1
            folder_stats[folder]["words"] += section.get("word_count", 0)
            
            ext = section.get("document_extension", ".txt").lower()
            if ext not in folder_stats[folder]["formats"]:
                folder_stats[folder]["formats"][ext] = 0
            folder_stats[folder]["formats"][ext] += 1
            
            format_stats[ext] = format_stats.get(ext, 0) + 1
        
        by_folder_formatted = {}
        for folder, stats in folder_stats.items():
            by_folder_formatted[folder] = {
                "documents": len(stats["documents"]),
                "sections": stats["sections"],
                "words": stats["words"],
                "formats": stats["formats"]
            }
        
        created_at = self.metadata.get("created_at", datetime.now().isoformat())
        
        return {
            "created_at": created_at,
            "last_updated": datetime.now().isoformat(),
            "total_sections": len(sections),
            "total_documents": len(unique_documents),
            "by_folder": by_folder_formatted,
            "format_stats": format_stats,
            "supported_extensions": SUPPORTED_EXTENSIONS,
            "version": "1.0"
        }
    
    def scan_and_build_database(self):
        """Сканируем папки и строим базу разделов"""
        print("🔍 Начинаем сканирование папок...")
        
        all_sections = []
        folder_stats = {}
        
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
                        metadata  # Передаем метаданные в функцию разделения
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
                    import traceback
                    traceback.print_exc()
            
            folder_stats[folder_name] = {
                "documents": folder_documents,
                "sections": folder_sections
            }
        
        self.sections = all_sections
        self.metadata = self._recalculate_metadata(all_sections)
        
        success = self.save_database()
        
        if success:
            print(f"\n✅ База создана!")
            print(f"   Всего документов: {self.metadata['total_documents']}")
            print(f"   Всего разделов: {self.metadata['total_sections']}")
            print(f"   Дата обновления: {self.metadata['last_updated']}")
            
            if 'format_stats' in self.metadata:
                print(f"   Форматы документов:")
                for ext, count in self.metadata['format_stats'].items():
                    format_name = {
                        ".md": "Markdown",
                        ".txt": "Текстовый"
                    }.get(ext, ext)
                    print(f"     {format_name}: {count} документов")
            
            if 'by_folder' in self.metadata:
                print(f"   Распределение по папкам:")
                for folder_name, stats in self.metadata['by_folder'].items():
                    folder_display = {
                        "normative": "Нормативные",
                        "methodology": "Методические",
                        "structured": "Структурированные",
                        "expertise": "Экспертные"
                    }.get(folder_name, folder_name)
                    print(f"     📁 {folder_display}: {stats.get('documents', 0)} док. → {stats.get('sections', 0)} разд.")
        
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
        """
        Разделение нормативных документов с поддержкой YAML фильтрации статей
        и разделением по главам по умолчанию
        """
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
        
        # Получаем параметры фильтрации из метаданных
        split_by_articles = metadata.get('split_by', '').lower() == 'articles'
        extract_ranges = metadata.get('extract_ranges', [])
        extract_only = metadata.get('extract_only', [])
        
        # Объединяем extract_ranges и extract_only для удобства
        all_extract_items = []
        
        # Добавляем элементы из extract_ranges
        if extract_ranges:
            all_extract_items.extend(extract_ranges)
        
        # Добавляем элементы из extract_only
        if extract_only:
            all_extract_items.extend(extract_only)
        
        # Конвертируем в строки если нужно
        if all_extract_items:
            all_extract_items = [
                str(item).strip() if not isinstance(item, str) else item.strip()
                for item in all_extract_items
            ]
        
        # РЕЖИМ ПО УМОЛЧАНИЮ: РАЗДЕЛЕНИЕ ПО ГЛАВАМ
        if not split_by_articles and not all_extract_items:
            # Разделение по главам (обновленный код с требованием точки)
            print(f"  📖 Разделение по главам (по умолчанию)")
            
            lines = content_to_process.split('\n')
            current_section = []
            current_title = doc_title
            current_type = "document"
            
            # УНИВЕРСАЛЬНЫЙ ПАТТЕРН: Глава/ГЛАВА + номер + ТОЧКА + пробел + название
            # Поддерживает: "Глава I.", "ГЛАВА 1.", "Глава 6.1.", "ГЛАВА 6.1.1."
            chapter_pattern = re.compile(
                r'^(ГЛАВА|Глава)\s+'      # "ГЛАВА" или "Глава"
                r'([IVXLCDM]+|\d+(?:\.\d+)*)'  # номер: римские цифры или арабские (с подразделами)
                r'\.\s+'                   # ТОЧКА после номера (обязательно!)
                r'(.+)$'                   # название главы
            )
            
            for line in lines:
                line_stripped = line.strip()
                match = chapter_pattern.match(line_stripped)
                
                if match:
                    # Нашли заголовок главы
                    if current_section:
                        sections.append({
                            "title": current_title,
                            "content": "\n".join(current_section).strip(),
                            "type": current_type
                        })
                    
                    chapter_word = match.group(1)  # "ГЛАВА" или "Глава"
                    chapter_number = match.group(2)  # номер главы
                    chapter_name = match.group(3).strip()  # название главы
                    
                    current_title = f"{chapter_word} {chapter_number}. {chapter_name}"
                    current_type = "chapter"
                    current_section = []
                else:
                    # Не заголовок главы - добавляем к текущему разделу
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
            
            chapter_count = sum(1 for s in sections if s["type"] == "chapter")
            print(f"    → Найдено {chapter_count} глав")
            
            return sections
        
        # Остальной код остается без изменений...
        # РЕЖИМ РАЗДЕЛЕНИЯ ПО СТАТЬЯМ (с фильтрацией или без)
        lines = content_to_process.split('\n')
        
        # Собираем все статьи сначала
        all_articles = []
        current_article = None
        
        for i, line in enumerate(lines):
            # Проверяем, является ли строка началом статьи
            # Статья должна иметь формат: "Статья X.", "Статья X.Y.", "Статья X.Y.Z."
            article_match = re.match(r'^Статья\s+(\d+[\.\d]*)\.\s*(.*)$', line.strip())
            
            if article_match:
                # Если есть предыдущая статья, сохраняем ее
                if current_article is not None:
                    all_articles.append(current_article)
                
                article_number = article_match.group(1)
                article_title = article_match.group(2).strip()
                
                current_article = {
                    "number": article_number,
                    "title": article_title,
                    "lines": [line],
                    "full_content": line + "\n"
                }
            elif current_article is not None:
                # Добавляем строки к текущей статье
                # Но проверяем, не начинается ли следующая статья
                next_line_starts_article = False
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    next_match = re.match(r'^Статья\s+(\d+[\.\d]*)\.\s*(.*)$', next_line)
                    if next_match:
                        next_line_starts_article = True
                
                # Если текущая строка пустая и следующая строка - новая статья, 
                # то заканчиваем текущую статью
                if line.strip() == "" and next_line_starts_article:
                    all_articles.append(current_article)
                    current_article = None
                else:
                    current_article["lines"].append(line)
                    current_article["full_content"] += line + "\n"
        
        # Добавляем последнюю статью
        if current_article is not None:
            all_articles.append(current_article)
        
        # Функция для проверки, нужно ли включать статью
        def should_include_article(article_num, extract_items):
            """Проверяет, нужно ли включать статью на основе списка извлечения"""
            if not extract_items:
                return True  # Если список пустой, включаем все
            
            article_num_str = str(article_num)
            
            # Пытаемся преобразовать номер статьи в число для сравнения
            try:
                if '.' in article_num_str:
                    main_part = article_num_str.split('.')[0]
                    sub_part = '.'.join(article_num_str.split('.')[1:])
                    article_value = float(f"{main_part}.{sub_part}")
                else:
                    article_value = float(article_num_str)
            except ValueError:
                article_value = None
            
            for item in extract_items:
                item_str = str(item).strip()
                
                # 1. Прямое сравнение строк
                if item_str == article_num_str:
                    return True
                
                # 2. Проверка диапазона (формат "X-Y")
                if '-' in item_str:
                    try:
                        start_str, end_str = item_str.split('-')
                        
                        # Преобразуем границы диапазона
                        if '.' in start_str:
                            start_main = start_str.split('.')[0]
                            start_sub = '.'.join(start_str.split('.')[1:])
                            start_value = float(f"{start_main}.{start_sub}")
                        else:
                            start_value = float(start_str)
                        
                        if '.' in end_str:
                            end_main = end_str.split('.')[0]
                            end_sub = '.'.join(end_str.split('.')[1:])
                            end_value = float(f"{end_main}.{end_sub}")
                        else:
                            end_value = float(end_str)
                        
                        if article_value is not None and start_value <= article_value <= end_value:
                            return True
                    except ValueError:
                        continue
                
                # 3. Проверка частичного совпадения (для "5" и "5.1" - не считаем совпадением)
                #    Но "5" должно совпадать с "5.0"
                if '.' in article_num_str:
                    main_part = article_num_str.split('.')[0]
                    if main_part == item_str:
                        # Только если это целое число, например "5" и "5.0"
                        try:
                            sub_part = float('0.' + '.'.join(article_num_str.split('.')[1:]))
                            if abs(sub_part) < 0.001:  # Практически 0
                                return True
                        except:
                            pass
            
            return False
        
        # Применяем фильтрацию если включен режим статей
        filtered_articles = []
        
        if all_articles:
            if split_by_articles:
                if all_extract_items:
                    print(f"  📑 Разделение по статьям с фильтрацией из YAML")
                    
                    for article in all_articles:
                        article_num = article["number"]
                        
                        if should_include_article(article_num, all_extract_items):
                            filtered_articles.append(article)
                            print(f"    → Статья {article_num} включена")
                    
                    print(f"    → Отфильтровано: {len(filtered_articles)} из {len(all_articles)} статей")
                else:
                    # Разделение по статьям без фильтрации
                    filtered_articles = all_articles
                    print(f"  📑 Разделение по статьям (без фильтрации)")
                    print(f"    → Найдено {len(all_articles)} статей")
        
        # Формируем разделы
        if filtered_articles:
            # Есть отфильтрованные статьи
            for article in filtered_articles:
                sections.append({
                    "title": f"Статья {article['number']}. {article['title']}",
                    "content": article["full_content"].strip(),
                    "type": "article"
                })
        elif all_articles and split_by_articles:
            # Есть статьи, включен режим разделения по статьям, но нет фильтров
            for article in all_articles:
                sections.append({
                    "title": f"Статья {article['number']}. {article['title']}",
                    "content": article["full_content"].strip(),
                    "type": "article"
                })
        else:
            # Если нет статей или не разделяем по статьям, сохраняем как есть
            sections.append({
                "title": doc_title,
                "content": content_to_process.strip(),
                "type": "full_document"
            })
        
        # Если в результате нет разделов, создаем один раздел с полным документом
        if not sections:
            sections.append({
                "title": doc_title,
                "content": content_to_process.strip(),
                "type": "full_document"
            })
        
        return sections
        
        # Функция для проверки, попадает ли статья в указанный диапазон
        def article_in_ranges(article_num, ranges):
            """Проверяет, входит ли номер статьи в указанные диапазоны"""
            article_num_float = float(article_num.replace('.', '', 1))
            
            for range_str in ranges:
                if '-' in range_str:
                    # Диапазон вида "3-7" или "3.1-7.2"
                    try:
                        start_str, end_str = range_str.split('-')
                        start = float(start_str.strip().replace('.', '', 1))
                        end = float(end_str.strip().replace('.', '', 1))
                        
                        if start <= article_num_float <= end:
                            return True
                    except ValueError:
                        continue
                else:
                    # Конкретный номер статьи
                    try:
                        target = float(range_str.strip().replace('.', '', 1))
                        if abs(article_num_float - target) < 0.001:  # Сравнение с учетом float
                            return True
                    except ValueError:
                        continue
            return False
        
        # Функция для проверки, является ли статья конкретной из списка
        def article_in_list(article_num, article_list):
            """Проверяет, есть ли номер статьи в списке"""
            article_num_clean = str(article_num).strip()
            
            for item in article_list:
                if isinstance(item, str):
                    target_clean = item.strip()
                    if target_clean == article_num_clean:
                        return True
                    
                    # Проверяем частичное совпадение для номеров с точками
                    if '.' in article_num_clean and '.' in target_clean:
                        # Сравниваем по частям
                        article_parts = article_num_clean.split('.')
                        target_parts = target_clean.split('.')
                        
                        # Для случаев типа "6" и "6.1" - не считаем совпадением
                        if len(article_parts) == len(target_parts):
                            if all(a == t for a, t in zip(article_parts, target_parts)):
                                return True
            
            return False
        
        # Применяем фильтрацию если указано
        filtered_articles = []
        
        if split_by_articles and (extract_ranges or extract_only):
            print(f"  📑 Разделение по статьям с фильтрацией из YAML")
            
            for article in all_articles:
                article_num = article["number"]
                include_article = False
                
                # Проверяем extract_only (приоритетный список)
                if extract_only:
                    if article_in_list(article_num, extract_only):
                        include_article = True
                        print(f"    → Статья {article_num} включена (extract_only)")
                
                # Проверяем extract_ranges (если не в extract_only)
                if not include_article and extract_ranges:
                    if article_in_ranges(article_num, extract_ranges):
                        include_article = True
                        print(f"    → Статья {article_num} включена (extract_ranges)")
                
                # Если ни один фильтр не указан, включаем все статьи
                if not extract_only and not extract_ranges:
                    include_article = True
                
                if include_article:
                    filtered_articles.append(article)
            
            print(f"    → Отфильтровано: {len(filtered_articles)} из {len(all_articles)} статей")
        
        else:
            # Без фильтрации - все статьи
            filtered_articles = all_articles
            if split_by_articles:
                print(f"  📑 Разделение по статьям (без фильтрации)")
                print(f"    → Найдено {len(all_articles)} статей")
        
        # Формируем разделы из отфильтрованных статей
        if split_by_articles and filtered_articles:
            for article in filtered_articles:
                sections.append({
                    "title": f"Статья {article['number']}. {article['title']}",
                    "content": article["full_content"].strip(),
                    "type": "article"
                })
        else:
            # Если нет статей или не разделяем по статьям, сохраняем как есть
            sections.append({
                "title": doc_title,
                "content": content_to_process.strip(),
                "type": "full_document"
            })
        
        # Если в результате нет разделов, создаем один раздел с полным документом
        if not sections:
            sections.append({
                "title": doc_title,
                "content": content_to_process.strip(),
                "type": "full_document"
            })
        
        return sections
    
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
        """
        Экспортирует выбранные разделы в JSON файл
        
        Args:
            output_path: Путь для сохранения JSON файла
            
        Returns:
            bool: Успешность экспорта
        """
        try:
            selected_sections = self.get_selected_sections()
            
            if not selected_sections:
                print("⚠ Нет выбранных разделов для экспорта")
                return False
            
            # Формируем УПРОЩЕННУЮ структуру данных для экспорта
            export_data = []
            
            for section in selected_sections:
                doc_title = section.get("document_title", "")
                section_title = section.get("title", "")
                content = section.get("content", "")
                
                # Для структурированных документов корректируем заголовок
                if section.get("folder") == "structured" and not section_title.startswith("["):
                    section_title = f"[{section_title}]"
                
                export_data.append({
                    "title": doc_title,
                    "section_title": section_title,
                    "content": content
                })
            
            # Создаем папку если не существует
            output_path.parent.mkdir(exist_ok=True, parents=True)
            
            # Сохраняем в JSON с простой структурой
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Экспортировано {len(selected_sections)} разделов в {output_path}")
            print(f"   Формат: упрощенный JSON (массив объектов)")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка экспорта в JSON: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_database_stats(self) -> Dict:
        """Возвращает статистику базы данных"""
        stats = {
            "total_sections": len(self.sections),
            "selected_sections": sum(1 for s in self.sections if s.get("selected", False)),
            "metadata": self.metadata.copy(),
            "folders_summary": {},
            "formats_summary": {}
        }
        
        folder_stats = {}
        for section in self.sections:
            folder = section.get("folder", "unknown")
            if folder not in folder_stats:
                folder_stats[folder] = {"sections": 0, "selected": 0, "documents": set()}
            
            folder_stats[folder]["sections"] += 1
            if section.get("selected", False):
                folder_stats[folder]["selected"] += 1
            
            doc_key = f"{section.get('document_path', '')}_{section.get('document', '')}"
            folder_stats[folder]["documents"].add(doc_key)
        
        for folder, data in folder_stats.items():
            stats["folders_summary"][folder] = {
                "sections": data["sections"],
                "selected": data["selected"],
                "documents": len(data["documents"]),
                "selected_percentage": round((data["selected"] / data["sections"] * 100), 1) if data["sections"] > 0 else 0
            }
        
        format_stats = {}
        for section in self.sections:
            ext = section.get("document_extension", ".txt").lower()
            format_stats[ext] = format_stats.get(ext, 0) + 1
        
        stats["formats_summary"] = format_stats
        
        return stats

# ==============================================
# СИСТЕМА УПРАВЛЕНИЯ СЕССИЯМИ
# ==============================================

class SessionManager:
    """
    Управление рабочими сессиями экспертов
    
    Структура сессии:
    📁 session_YYYYMMDD_HHMMSS/
    ├── 📄 prompt.txt           # Промт из выбранного шаблона
    ├── 📄 materials.json       # Выбранные разделы из базы (УПРОЩЕННЫЙ ФОРМАТ)
    ├── 📁 attachments/         # Дополнительные файлы
    └── 📄 response.md          # Ответ от AI (будет создан позже)
    """
    
    def __init__(self, sessions_path: str = None):
        """Инициализация менеджера сессий"""
        self.sessions_path = Path(sessions_path or CONFIG["sessions_path"])
        self.sessions_path.mkdir(exist_ok=True, parents=True)
        self.prompt_extensions = ['.txt', '.md']  # Расширения файлов, которые считаются промтами
    
    def create_session(self, session_name: str = None, template_prompt: str = None) -> Optional[Path]:
        """
        Создает новую рабочую сессию
        
        Args:
            session_name: Имя сессии (если None, генерируется автоматически)
            template_prompt: Промт из выбранного шаблона
            
        Returns:
            Path: Путь к созданной сессии или None в случае ошибки
        """
        try:
            # Генерируем имя сессии если не указано
            if not session_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                session_name = f"session_{timestamp}"
            
            # Создаем папку сессии
            session_path = self.sessions_path / session_name
            session_path.mkdir(exist_ok=True, parents=True)
            
            # Создаем структуру папок
            attachments_dir = session_path / "attachments"
            attachments_dir.mkdir(exist_ok=True)
            
            # Получаем промт из выбранного шаблона
            templates_data = load_templates()
            selected_template = get_selected_template(templates_data)
            
            # Создаем файл промта из шаблона
            prompt_file = session_path / "prompt.txt"
            
            # Используем переданный промт или из выбранного шаблона
            if template_prompt:
                prompt_content = template_prompt
            else:
                prompt_content = selected_template.get("prompt", "") if selected_template else ""
            
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(prompt_content)
            
            # Создаем README файл с инструкцией
            readme_file = session_path / "README.md"
            readme_content = f"""# 🎯 РАБОЧАЯ СЕССИЯ: {session_name}

## 📁 СТРУКТУРА ПАПКИ:

1. **`prompt.txt`** - вопрос к AI (создан из выбранного шаблона)
2. **`materials.json`** - выбранные нормативные документы (УПРОЩЕННЫЙ ФОРМАТ)
3. **`attachments/`** - дополнительные файлы
4. **`response.md`** - ответ от AI

## 📝 ИНСТРУКЦИЯ:

1. Файл `prompt.txt` создан автоматически из выбранного шаблона
2. Можете отредактировать его под конкретную задачу
3. Добавьте дополнительные файлы в папку `attachments/`
4. Экспортируйте материалы из веб-интерфейса
5. Используйте все файлы для работы с ИИ

---

**Дата создания:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Шаблон:** {selected_template.get('name', 'Неизвестно') if selected_template else 'Неизвестно'}
**Путь:** `{session_path}`
"""
            
            with open(readme_file, 'w', encoding='utf-8') as f:
                f.write(readme_content)
            
            print(f"✅ Создана сессия: {session_path}")
            print(f"   📝 Шаблон: {selected_template.get('name', 'Неизвестно') if selected_template else 'Неизвестно'}")
            return session_path
            
        except Exception as e:
            print(f"❌ Ошибка создания сессии: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def save_template_to_session(self, session_path: Path, template_prompt: str) -> bool:
        """
        Сохраняет промт из шаблона в сессию
        """
        try:
            prompt_file = session_path / "prompt.txt"
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(template_prompt)
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения шаблона в сессию: {e}")
            return False
    
    def find_prompt_files(self, session_path: Path) -> List[Dict]:
        """
        Находит все файлы промтов в папке сессии
        
        Args:
            session_path: Путь к сессии
            
        Returns:
            List[Dict]: Список файлов промтов с информацией
        """
        prompt_files = []
        
        for ext in self.prompt_extensions:
            for file_path in session_path.glob(f"*{ext}"):
                if file_path.is_file():
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        prompt_files.append({
                            "name": file_path.name,
                            "path": str(file_path),
                            "extension": ext,
                            "content": content,
                            "size": file_path.stat().st_size,
                            "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                        })
                    except Exception as e:
                        print(f"⚠ Ошибка чтения промта {file_path.name}: {e}")
        
        # Сортируем по дате изменения (сначала новые)
        prompt_files.sort(key=lambda x: x["modified"], reverse=True)
        
        return prompt_files
    
    def get_main_prompt(self, session_path: Path) -> Optional[Dict]:
        """
        Получает основной промт сессии (первый найденный файл промта)
        
        Args:
            session_path: Путь к сессии
            
        Returns:
            Optional[Dict]: Информация о основном промте или None
        """
        prompt_files = self.find_prompt_files(session_path)
        
        if prompt_files:
            # Возвращаем первый (самый новый) промт
            return prompt_files[0]
        
        return None
    
    def get_session_files(self, session_path: Path) -> Dict:
        """
        Получает информацию о файлах в сессии
        
        Args:
            session_path: Путь к сессии
            
        Returns:
            Dict: Информация о файлах сессии
        """
        files_info = {
            "session_name": session_path.name,
            "session_path": str(session_path),
            "created": datetime.fromtimestamp(session_path.stat().st_ctime).isoformat(),
            "has_prompt": False,
            "has_materials": False,
            "has_attachments": False,
            "has_response": False,
            "prompt_files": [],
            "main_prompt": None,
            "materials_count": 0,
            "attachments_list": [],
            "response_content": None
        }
        
        # Ищем файлы промтов
        prompt_files = self.find_prompt_files(session_path)
        if prompt_files:
            files_info["prompt_files"] = prompt_files
            files_info["has_prompt"] = True
            files_info["main_prompt"] = prompt_files[0]  # Основной промт
        
        # Проверяем материалы
        materials_file = session_path / "materials.json"
        if materials_file.exists():
            try:
                with open(materials_file, 'r', encoding='utf-8') as f:
                    materials_data = json.load(f)
                    files_info["materials_count"] = len(materials_data)
                files_info["has_materials"] = True
            except Exception as e:
                print(f"⚠ Ошибка чтения материалов: {e}")
        
        # Проверяем вложения
        attachments_dir = session_path / "attachments"
        if attachments_dir.exists():
            attachments = []
            for file_path in attachments_dir.glob("*"):
                if file_path.is_file():
                    attachments.append({
                        "name": file_path.name,
                        "path": str(file_path),
                        "size": file_path.stat().st_size,
                        "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                    })
            files_info["attachments_list"] = attachments
            files_info["has_attachments"] = len(attachments) > 0
        
        # Проверяем ответ
        response_file = session_path / "response.md"
        if response_file.exists():
            try:
                with open(response_file, 'r', encoding='utf-8') as f:
                    files_info["response_content"] = f.read()
                files_info["has_response"] = True
            except Exception as e:
                print(f"⚠ Ошибка чтения ответа: {e}")
        
        return files_info
    
    def list_sessions(self) -> List[Dict]:
        """
        Возвращает список всех сессий
        
        Returns:
            List[Dict]: Список информации о сессиях
        """
        sessions = []
        
        for session_dir in self.sessions_path.glob("session_*"):
            if session_dir.is_dir():
                files_info = self.get_session_files(session_dir)
                sessions.append(files_info)
        
        # Сортируем по дате создания (сначала новые)
        sessions.sort(key=lambda x: x["created"], reverse=True)
        
        return sessions
    
    def delete_session(self, session_path: Path) -> bool:
        """
        Удаляет сессию
        
        Args:
            session_path: Путь к сессии
            
        Returns:
            bool: Успешность удаления
        """
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
        """
        Экспортирует выбранные разделы в сессию
        
        Args:
            session_path: Путь к сессии
            database: База данных разделов
            
        Returns:
            bool: Успешность экспорта
        """
        try:
            materials_file = session_path / "materials.json"
            return database.export_selected_to_json(materials_file)
            
        except Exception as e:
            print(f"❌ Ошибка экспорта в сессию: {e}")
            return False

# ==============================================
# КЛАСС ДЛЯ АДМИНИСТРАТИВНЫХ ОПЕРАЦИЙ
# ==============================================

class DatabaseAdmin:
    """Класс для административных операций с базой данных"""
    
    def __init__(self, database: SimpleSectionDatabase):
        self.db = database
    
    def export_full_database(self, output_path: Path) -> bool:
        """Экспортирует всю базу данных в JSON файл"""
        try:
            export_data = {
                "metadata": self.db.metadata.copy(),
                "sections": self.db.sections.copy(),
                "export_info": {
                    "export_date": datetime.now().isoformat(),
                    "version": "1.0",
                    "total_sections": len(self.db.sections),
                    "total_documents": self.db.metadata.get("total_documents", 0)
                }
            }
            
            output_path.parent.mkdir(exist_ok=True, parents=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Полная база экспортирована в {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка экспорта полной базы: {e}")
            return False
    
    def import_database(self, import_file: Path) -> Dict:
        """Импортирует базу данных из JSON файла"""
        try:
            if not import_file.exists():
                return {"success": False, "error": "Файл не найден"}
            
            with open(import_file, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            # Проверяем структуру
            if "sections" not in import_data:
                return {"success": False, "error": "Неверный формат: отсутствуют разделы"}
            
            # Сохраняем старые данные для отката
            old_sections = self.db.sections.copy()
            old_metadata = self.db.metadata.copy()
            
            try:
                # Импортируем данные
                self.db.sections = import_data["sections"]
                
                # Обновляем метаданные
                if "metadata" in import_data:
                    self.db.metadata = import_data["metadata"]
                else:
                    # Пересчитываем метаданные
                    self.db.metadata = self.db._recalculate_metadata(self.db.sections)
                
                # Сохраняем базу
                self.db.save_database()
                
                return {
                    "success": True,
                    "sections_imported": len(self.db.sections),
                    "documents_imported": self.db.metadata.get("total_documents", 0),
                    "message": f"Импортировано {len(self.db.sections)} разделов"
                }
                
            except Exception as e:
                # Откатываем при ошибке
                self.db.sections = old_sections
                self.db.metadata = old_metadata
                return {"success": False, "error": f"Ошибка импорта: {str(e)}"}
                
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Ошибка JSON: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Ошибка: {str(e)}"}
    
    def validate_database(self) -> Dict:
        """Проверяет целостность базы данных"""
        issues = []
        warnings = []
        
        # Проверяем наличие обязательных полей
        required_fields = ["id", "folder", "document", "content"]
        for i, section in enumerate(self.db.sections):
            for field in required_fields:
                if field not in section or not section[field]:
                    issues.append(f"Раздел #{i}: отсутствует поле '{field}'")
            
            # Проверяем валидность ID
            if "id" in section and not isinstance(section["id"], str):
                issues.append(f"Раздел #{i}: поле 'id' должно быть строкой")
        
        # Проверяем уникальность ID
        ids = [s.get("id") for s in self.db.sections if s.get("id")]
        duplicates = [id for id in set(ids) if ids.count(id) > 1]
        if duplicates:
            issues.append(f"Найдены дублирующиеся ID: {duplicates[:3]}...")
        
        # Проверяем соответствие метаданных
        actual_sections = len(self.db.sections)
        metadata_sections = self.db.metadata.get("total_sections", 0)
        
        if actual_sections != metadata_sections:
            warnings.append(f"Несоответствие: фактически {actual_sections} разделов, в метаданных {metadata_sections}")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "sections_count": actual_sections,
            "metadata_sections_count": metadata_sections,
            "has_duplicate_ids": len(duplicates) > 0
        }
    
    def get_detailed_stats(self) -> Dict:
        """Возвращает детальную статистику базы данных"""
        stats = {
            "total": {
                "sections": len(self.db.sections),
                "documents": self.db.metadata.get("total_documents", 0),
                "words": sum(s.get("word_count", 0) for s in self.db.sections),
                "selected": sum(1 for s in self.db.sections if s.get("selected", False))
            },
            "by_folder": {},
            "by_format": {},
            "recent_updates": []
        }
        
        # Статистика по папкам
        for folder in ["normative", "methodology", "structured", "expertise"]:
            folder_sections = [s for s in self.db.sections if s.get("folder") == folder]
            if folder_sections:
                stats["by_folder"][folder] = {
                    "sections": len(folder_sections),
                    "documents": len(set(s.get("document", "") for s in folder_sections)),
                    "words": sum(s.get("word_count", 0) for s in folder_sections),
                    "selected": sum(1 for s in folder_sections if s.get("selected", False))
                }
        
        # Статистика по форматам
        format_stats = {}
        for section in self.db.sections:
            ext = section.get("document_extension", ".txt").lower()
            format_stats[ext] = format_stats.get(ext, 0) + 1
        stats["by_format"] = format_stats
        
        # Последние обновления (первые 10)
        if self.db.sections:
            sorted_sections = sorted(
                self.db.sections, 
                key=lambda x: x.get("scan_date", ""), 
                reverse=True
            )[:10]
            
            for section in sorted_sections:
                if section.get("scan_date"):
                    try:
                        date_str = section["scan_date"][:10]
                        stats["recent_updates"].append({
                            "document": section.get("document_title", section.get("document", "")),
                            "section": section.get("title", ""),
                            "date": date_str,
                            "folder": section.get("folder", "")
                        })
                    except:
                        pass
        
        return stats

# ==============================================
# ВЕБ-ИНТЕРФЕЙС ДЛЯ ЭКСПЕРТА (Streamlit)
# ==============================================

# Стили для компактного интерфейса
st.markdown("""
<style>
/* Компактные разделы */
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

/* Стили для темной темы */
[data-theme="dark"] .section-item {
    background-color: #2d2d2d;
    border-color: #555;
}
[data-theme="dark"] .section-header {
    color: #ffffff !important;
}
[data-theme="dark"] .section-meta {
    color: #cccccc !important;
}
[data-theme="dark"] .section-title {
    color: #f0f0f0 !important;
}
[data-theme="dark"] .selected-section {
    background-color: #1e3a1e;
    border-color: #4CAF50;
}

/* Уменьшаем отступы */
div.stContainer {
    padding-top: 1px !important;
    padding-bottom: 1px !important;
}
</style>
""", unsafe_allow_html=True)

# Инициализация базы данных и менеджеров
@st.cache_resource
def init_database():
    return SimpleSectionDatabase()

@st.cache_resource
def init_session_manager():
    return SessionManager()

@st.cache_resource
def init_database_admin():
    return DatabaseAdmin(init_database())

# Инициализация сессии
if 'db' not in st.session_state:
    st.session_state.db = init_database()
    st.session_state.session_manager = init_session_manager()
    st.session_state.db_admin = init_database_admin()
    st.session_state.current_session = None
    st.session_state.has_unsaved_changes = False

db = st.session_state.db
session_manager = st.session_state.session_manager
db_admin = st.session_state.db_admin

# Настройка страницы
st.set_page_config(
    page_title="Экспертная система: Выбор разделов",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Главный заголовок
st.title("📚 ЭКСПЕРТНАЯ СИСТЕМА: ВЫБОР РАЗДЕЛОВ")
st.markdown("---")

# Проверка конфигурации
if not CONFIG.get("admin_enabled", True):
    st.warning("🚫 Администрирование отключено в конфигурации")

# Используем вкладки
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Выбор разделов",
    "📁 Рабочие сессии", 
    "⚙️ Настройки",
    "🛠️ Администрирование" if CONFIG.get("admin_enabled", True) else "🚫 Администрирование"
])

# ==============================================
# ВКЛАДКА 1: ВЫБОР РАЗДЕЛОВ
# ==============================================

with tab1:
    st.subheader("📋 ВЫБОР РАЗДЕЛОВ ДЛЯ ЭКСПЕРТНОГО ОТВЕТА")
    
    # Получаем данные для отображения
    display_data = db.get_sections_for_display()
    
    if not display_data:
        st.info("База пуста. Нажмите 'Сканировать папки' в боковой панели.")
    else:
        # Поиск и фильтры
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
        
        # Фильтрация данных
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
        
        # Статистика
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
        
        # ОТОБРАЖЕНИЕ РАЗДЕЛОВ
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
            
            # Обновляем флаг изменений
            if changes_made:
                st.session_state.has_unsaved_changes = True
            
            # Панель управления
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

# ==============================================
# ВКЛАДКА 2: РАБОЧИЕ СЕССИИ
# ==============================================

with tab2:
    st.subheader("📁 УПРАВЛЕНИЕ РАБОЧИМИ СЕССИЯМИ")
    
    # Функция для генерации имени сессии
    def generate_session_name():
        """Генерирует автоматическое имя сессии с временной меткой"""
        return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # ==============================================
    # БЛОК 1: СОЗДАНИЕ НОВОЙ СЕССИИ
    # ==============================================
    st.markdown("### 📝 СОЗДАНИЕ НОВОЙ СЕССИИ")
    
    col_create1, col_create2 = st.columns([3, 1])
    
    with col_create1:
        new_session_name = st.text_input(
            "Имя сессии (оставьте пустым для автоимени):",
            placeholder="session_жалоба",
            key="new_session_name"
        )
    
    with col_create2:
        if st.button("📁 Создать", type="primary", use_container_width=True):
            # Получаем выбранный шаблон
            templates_data = load_templates()
            selected_template = get_selected_template(templates_data)
            template_prompt = selected_template.get("prompt", "") if selected_template else ""
            
            # Создаем сессию с промтом из шаблона
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
    
    # ==============================================
    # БЛОК 2: СПИСОК СУЩЕСТВУЮЩИХ СЕССИЙ
    # ==============================================
    
    # Получаем список всех сессий
    sessions = session_manager.list_sessions()
    
    if not sessions:
        st.info("📭 Нет созданных сессий")
    else:
        st.markdown(f"### 📂 ВСЕГО СЕССИЙ: {len(sessions)}")
        
        # Простой поиск
        search_term = st.text_input("🔍 Поиск сессии:", 
                                  placeholder="Введите часть имени...")
        
        # Фильтруем сессии по поисковому запросу
        if search_term:
            filtered_sessions = [s for s in sessions if search_term.lower() in s['session_name'].lower()]
        else:
            filtered_sessions = sessions
        
        # Отображаем сессии
        for session_info in filtered_sessions:
            with st.expander(f"📁 {session_info['session_name']}", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    # Основная информация о сессии
                    created_date = session_info['created'][:10]
                    st.caption(f"Создана: {created_date}")
                    
                    # Статус
                    status_parts = []
                    if session_info['has_materials']:
                        status_parts.append(f"📚 {session_info['materials_count']} разд.")
                    if session_info['has_prompt']:
                        status_parts.append("🎯 Промт")
                    if session_info['has_attachments']:
                        status_parts.append(f"📎 {len(session_info['attachments_list'])} файл.")
                    if session_info['has_response']:
                        status_parts.append("🤖 Ответ")
                    
                    if status_parts:
                        st.caption(" • ".join(status_parts))
                    else:
                        st.caption("📭 Пустая сессия")
                
                with col2:
                    # Кнопка выбора сессии
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
                
                # Действия с сессией
                col_act1, col_act2, col_act3 = st.columns(3)
                
                with col_act1:
                    # Экспорт материалов в сессию
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
                    # Просмотр содержимого
                    if st.button("👁️ Просмотр", 
                               key=f"view_{session_info['session_name']}",
                               use_container_width=True):
                        st.info(f"**Содержимое сессии:** {session_info['session_name']}")
                        
                        if session_info['has_prompt']:
                            prompt_files = session_info['prompt_files']
                            if prompt_files:
                                st.write("**Файлы промтов:**")
                                for pf in prompt_files[:2]:
                                    icon = "📝" if pf['extension'] == '.md' else "📄"
                                    st.caption(f"{icon} {pf['name']}")
                        
                        if session_info['has_materials']:
                            st.write(f"**Материалы:** {session_info['materials_count']} разделов")
                        
                        if session_info['has_attachments']:
                            st.write(f"**Вложения:** {len(session_info['attachments_list'])} файлов")
                
                with col_act3:
                    # ПРОСТАЯ КНОПКА УДАЛЕНИЯ (БЕЗ ПОДТВЕРЖДЕНИЯ)
                    if st.button("🗑️ Удалить", 
                               key=f"delete_{session_info['session_name']}",
                               type="secondary",
                               use_container_width=True):
                        session_path = Path(session_info['session_path'])
                        
                        try:
                            # Проверяем существование
                            if session_path.exists() and session_path.is_dir():
                                # Удаляем сразу
                                shutil.rmtree(session_path)
                                
                                # Если это активная сессия - сбрасываем
                                if st.session_state.current_session == str(session_path):
                                    st.session_state.current_session = None
                                
                                # Сообщение об успехе
                                st.success(f"✅ Сессия '{session_info['session_name']}' удалена")
                                
                                # Обновляем страницу
                                st.rerun()
                            else:
                                st.error("❌ Сессия не найдена")
                                st.rerun()
                                
                        except Exception as e:
                            st.error(f"❌ Ошибка при удалении: {e}")
    
    # ==============================================
    # БЛОК 3: ИНФОРМАЦИЯ ОБ АКТИВНОЙ СЕССИИ
    # ==============================================
    
    st.markdown("---")
    
    if st.session_state.current_session:
        current_path = Path(st.session_state.current_session)
        
        if current_path.exists():
            st.markdown(f"### ✅ АКТИВНАЯ СЕССИЯ: **{current_path.name}**")
            
            # Получаем информацию о сессии
            try:
                files_info = session_manager.get_session_files(current_path)
                
                # Статус
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                
                with col_stat1:
                    if files_info['has_prompt']:
                        prompt_files = files_info['prompt_files']
                        if prompt_files:
                            st.success("🎯 Есть промт")
                    else:
                        st.warning("📭 Нет промта")
                
                with col_stat2:
                    if files_info['has_materials']:
                        st.success(f"📚 {files_info['materials_count']} материалов")
                    else:
                        st.warning("📭 Нет материалов")
                
                with col_stat3:
                    if files_info['has_attachments']:
                        st.success(f"📎 {len(files_info['attachments_list'])} вложений")
                    else:
                        st.info("📎 Нет вложений")
                
                # Кнопка быстрого экспорта
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
                
                # Инструкция
                with st.expander("📋 ИНСТРУКЦИЯ", expanded=False):
                    st.markdown(f"""
                    1. 📝 **Редактируйте промт** в папке: `{current_path}`
                    2. 📎 **Добавляйте файлы** в `{current_path}/attachments/`
                    3. 🤖 **Используйте с ИИ** (DeepSeek/ChatGPT)
                    4. 💾 **Сохраняйте ответ** как `{current_path}/response.md`
                    """)
                    
            except Exception as e:
                st.error(f"❌ Ошибка загрузки информации о сессии: {e}")
        else:
            st.error("❌ Активная сессия не найдена")
            st.session_state.current_session = None
    else:
        st.info("📭 Нет активной сессии. Выберите или создайте сессию.")

# ==============================================
# ВКЛАДКА 3: НАСТРОЙКИ
# ==============================================

with tab3:
    st.subheader("⚙️ НАСТРОЙКИ СИСТЕМЫ")
    
    # Информация о системе
    col_info1, col_info2 = st.columns(2)
    
    with col_info1:
        st.metric("Всего разделов в базе", db.metadata.get("total_sections", 0))
    
    with col_info2:
        st.metric("Выбрано разделов", sum(1 for section in db.sections if section.get("selected", False)))
    
    st.markdown("---")
    
    # Управление базой данных
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
    
    # ВЫБОР ШАБЛОНА ВОПРОСА
    st.markdown("---")
    st.markdown("### 🎯 ВЫБОР ШАБЛОНА ВОПРОСА")
    
    # Загружаем шаблоны
    templates_data = load_templates()
    selected_template = get_selected_template(templates_data)
    
    # Отображаем текущий выбранный шаблон
    if selected_template:
        st.info(f"**Текущий шаблон:** {selected_template['name']}")
        st.caption(f"{selected_template['description']}")
    else:
        st.warning("⚠️ Нет доступных шаблонов")
    
    # Выбор шаблона
    if templates_data:
        template_options = {t["id"]: t["name"] for t in templates_data}
        selected_id = st.radio(
            "Выберите шаблон для новых сессий:",
            options=list(template_options.keys()),
            format_func=lambda x: template_options[x],
            index=list(template_options.keys()).index(selected_template["id"]) if selected_template else 0,
            key="template_selector"
        )
        
        # Кнопка сохранения выбора шаблона
        col_template1, col_template2 = st.columns([1, 2])
        
        with col_template1:
            if st.button("💾 Сохранить выбор шаблона", type="primary", use_container_width=True):
                updated_templates = update_selected_template(templates_data, selected_id)
                if save_templates(updated_templates):
                    st.success(f"✅ Шаблон сохранен: {template_options[selected_id]}")
                    st.rerun()
        
        with col_template2:
            # Просмотр промта выбранного шаблона
            selected_prompt = next((t["prompt"] for t in templates_data if t["id"] == selected_id), "")
            
            if st.button("👁️ Просмотр промта шаблона", use_container_width=True):
                with st.expander("📝 Промт шаблона", expanded=True):
                    st.text_area("", value=selected_prompt, height=300, disabled=True, key="template_preview")
    else:
        st.info("📭 Нет доступных шаблонов")
    
    # Просмотр конфигурации
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
    
    # Просмотр шаблонов
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

# ==============================================
# ВКЛАДКА 4: АДМИНИСТРИРОВАНИЕ
# ==============================================

with tab4:
    if not CONFIG.get("admin_enabled", True):
        st.warning("🚫 Администрирование отключено в настройках")
        st.info("Для включения установите `admin_enabled: true` в config.json")
    else:
        st.subheader("🛠️ АДМИНИСТРИРОВАНИЕ БАЗЫ ДАННЫХ")
        
        # Две колонки для разделения функционала
        col_admin1, col_admin2 = st.columns(2)
        
        # ==============================================
        # ЛЕВАЯ КОЛОНКА: ОСНОВНЫЕ ОПЕРАЦИИ
        # ==============================================
        with col_admin1:
            st.markdown("### 🔧 ОСНОВНЫЕ ОПЕРАЦИИ")
            
            # 1. Ручное сканирование папок
            st.markdown("#### 🔍 СКАНИРОВАНИЕ ПАПОК")
            
            if st.button("🔄 Сканировать все папки", type="primary", use_container_width=True):
                with st.spinner("Сканирую папки с документами..."):
                    sections = db.scan_and_build_database()
                    
                    if sections:
                        st.success(f"✅ Отсканировано {len(sections)} разделов")
                        
                        # Показываем детальную статистику
                        with st.expander("📊 Детальная статистика", expanded=True):
                            stats = db_admin.get_detailed_stats()
                            
                            col_stat1, col_stat2 = st.columns(2)
                            with col_stat1:
                                st.metric("Разделов", stats["total"]["sections"])
                                st.metric("Документов", stats["total"]["documents"])
                            with col_stat2:
                                st.metric("Всего слов", stats["total"]["words"])
                                st.metric("Выбрано", stats["total"]["selected"])
                            
                            # Статистика по папкам
                            st.markdown("**По папкам:**")
                            for folder, data in stats["by_folder"].items():
                                folder_name = {
                                    "normative": "📖 Нормативные",
                                    "methodology": "📚 Методические",
                                    "structured": "🗂️ Структурированные",
                                    "expertise": "👨‍⚖️ Экспертные"
                                }.get(folder, folder)
                                
                                st.caption(f"{folder_name}: {data['sections']} разд., {data['documents']} док., {data['words']} слов")
                    else:
                        st.error("❌ Ошибка при сканировании")
            
            # 2. Проверка целостности
            st.markdown("---")
            st.markdown("#### 🔍 ПРОВЕРКА ЦЕЛОСТНОСТИ")
            
            if st.button("✅ Проверить целостность базы", type="secondary", use_container_width=True):
                validation = db_admin.validate_database()
                
                if validation["is_valid"]:
                    st.success("✅ База данных в порядке!")
                else:
                    st.error("❌ Найдены проблемы:")
                    for issue in validation["issues"]:
                        st.error(f"  • {issue}")
                
                if validation["warnings"]:
                    st.warning("⚠️ Предупреждения:")
                    for warning in validation["warnings"]:
                        st.warning(f"  • {warning}")
                
                st.info(f"📊 Статистика: {validation['sections_count']} разделов, {validation['metadata_sections_count']} в метаданных")
            
            # 3. Очистка выборов
            st.markdown("---")
            st.markdown("#### 🗑️ ОЧИСТКА ВЫБОРОВ")
            
            selected_count = sum(1 for section in db.sections if section.get("selected", False))
            
            if selected_count > 0:
                if st.button(f"❌ Очистить все выборы ({selected_count})", type="secondary", use_container_width=True):
                    cleared = db.clear_selections()
                    if cleared > 0:
                        st.success(f"✅ Очищено {cleared} выборов")
                        st.session_state.has_unsaved_changes = False
                        st.rerun()
            else:
                st.info("ℹ️ Нет выбранных разделов для очистки")
        
        # ==============================================
        # ПРАВАЯ КОЛОНКА: ИМПОРТ/ЭКСПОРТ
        # ==============================================
        with col_admin2:
            st.markdown("### 📤 ИМПОРТ/ЭКСПОРТ")
            
            # 1. Экспорт полной базы
            st.markdown("#### 📤 ЭКСПОРТ ПОЛНОЙ БАЗЫ")
            
            if CONFIG.get("allow_database_export", True):
                if st.button("💾 Экспортировать всю базу", type="primary", use_container_width=True):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    export_filename = f"full_database_export_{timestamp}.json"
                    export_path = Path(CONFIG["sessions_path"]) / export_filename
                    
                    success = db_admin.export_full_database(export_path)
                    
                    if success:
                        st.success(f"✅ База экспортирована в {export_filename}")
                        
                        # Предлагаем скачать
                        with open(export_path, 'r', encoding='utf-8') as f:
                            export_data = f.read()
                        
                        st.download_button(
                            label=f"⬇️ Скачать {export_filename}",
                            data=export_data,
                            file_name=export_filename,
                            mime="application/json",
                            use_container_width=True
                        )
                        
                        # Показываем информацию об экспорте
                        with st.expander("📋 Информация об экспорте"):
                            stats = db_admin.get_detailed_stats()
                            st.info(f"**Разделов:** {stats['total']['sections']}")
                            st.info(f"**Документов:** {stats['total']['documents']}")
                            st.info(f"**Выбрано:** {stats['total']['selected']}")
                            st.info(f"**Всего слов:** {stats['total']['words']}")
                            
                            if stats['by_folder']:
                                st.markdown("**Распределение по папкам:**")
                                for folder, data in stats['by_folder'].items():
                                    folder_name = {
                                        "normative": "Нормативные",
                                        "methodology": "Методические",
                                        "structured": "Структурированные",
                                        "expertise": "Экспертные"
                                    }.get(folder, folder)
                                    st.caption(f"  - {folder_name}: {data['sections']} разд.")
                    else:
                        st.error("❌ Ошибка экспорта")
            else:
                st.warning("🚫 Экспорт базы отключен в настройках")
            
            # 2. Импорт базы
            st.markdown("---")
            st.markdown("#### 📥 ИМПОРТ БАЗЫ")
            
            if CONFIG.get("allow_database_import", True):
                uploaded_file = st.file_uploader(
                    "Выберите файл базы данных (JSON):",
                    type=['json'],
                    key="admin_import_uploader",
                    help="Загрузите JSON файл с экспортированной базой данных"
                )
                
                if uploaded_file is not None:
                    # Сохраняем временный файл
                    temp_dir = Path(tempfile.gettempdir())
                    temp_file = temp_dir / uploaded_file.name
                    
                    with open(temp_file, 'wb') as f:
                        f.write(uploaded_file.getvalue())
                    
                    # Показываем информацию о файле
                    st.info(f"📄 Загружен файл: {uploaded_file.name}")
                    st.info(f"📊 Размер: {uploaded_file.size // 1024} KB")
                    
                    # Предпросмотр структуры
                    try:
                        with open(temp_file, 'r', encoding='utf-8') as f:
                            preview_data = json.load(f)
                        
                        sections_count = len(preview_data.get("sections", []))
                        st.info(f"📋 Разделов в файле: {sections_count}")
                        
                        # Показываем предпросмотр структуры
                        with st.expander("👁️ Предпросмотр структуры", expanded=False):
                            if sections_count > 0:
                                sample_section = preview_data["sections"][0]
                                st.json({
                                    "metadata_keys": list(preview_data.get("metadata", {}).keys()),
                                    "section_sample": {
                                        "folder": sample_section.get("folder"),
                                        "document": sample_section.get("document"),
                                        "title": sample_section.get("title", "")[:50] + "...",
                                        "word_count": sample_section.get("word_count", 0)
                                    }
                                })
                    except:
                        st.warning("⚠️ Не удалось прочитать структуру файла")
                    
                    # Кнопка импорта
                    st.markdown("---")
                    
                    if st.button("📥 Импортировать базу данных", type="secondary", use_container_width=True):
                        st.warning("⚠️ **ВНИМАНИЕ:** Текущая база будет заменена!")
                        
                        # Дополнительное подтверждение
                        col_confirm1, col_confirm2 = st.columns(2)
                        with col_confirm1:
                            confirm_import = st.checkbox("Я понимаю, что текущая база будет заменена", 
                                                       key="confirm_import_checkbox")
                        with col_confirm2:
                            if confirm_import and st.button("✅ Подтвердить импорт", type="primary", 
                                                          key="confirm_import_btn"):
                                with st.spinner("Импортирую базу данных..."):
                                    result = db_admin.import_database(temp_file)
                                    
                                    if result["success"]:
                                        st.success(f"✅ {result['message']}")
                                        
                                        # Показываем статистику после импорта
                                        with st.expander("📊 Статистика после импорта", expanded=True):
                                            stats = db_admin.get_detailed_stats()
                                            
                                            col_imp1, col_imp2 = st.columns(2)
                                            with col_imp1:
                                                st.metric("Разделов", stats["total"]["sections"])
                                                st.metric("Документов", stats["total"]["documents"])
                                            with col_imp2:
                                                st.metric("Всего слов", stats["total"]["words"])
                                                st.metric("Выбрано", stats["total"]["selected"])
                                        
                                        st.info("🔄 Обновите страницу для применения изменений")
                                        st.rerun()
                                        
                                    else:
                                        st.error(f"❌ Ошибка импорта: {result.get('error', 'Неизвестная ошибка')}")
            else:
                st.warning("🚫 Импорт базы отключен в настройках")
            
            # 3. Экспорт выбранных разделов
            st.markdown("---")
            st.markdown("#### 📤 ЭКСПОРТ ВЫБРАННЫХ РАЗДЕЛОВ")
            
            selected_count = sum(1 for section in db.sections if section.get("selected", False))
            
            if selected_count > 0:
                if st.button(f"📋 Экспорт выбранных ({selected_count})", type="secondary", use_container_width=True):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    export_filename = f"selected_sections_{timestamp}.json"
                    export_path = Path(CONFIG["sessions_path"]) / export_filename
                    
                    success = db.export_selected_to_json(export_path)
                    
                    if success:
                        st.success(f"✅ Экспортировано {selected_count} разделов")
                        
                        # Предлагаем скачать
                        with open(export_path, 'r', encoding='utf-8') as f:
                            export_data = f.read()
                        
                        st.download_button(
                            label=f"⬇️ Скачать {export_filename}",
                            data=export_data,
                            file_name=export_filename,
                            mime="application/json",
                            use_container_width=True
                        )
                    else:
                        st.error("❌ Ошибка экспорта")
            else:
                st.info("ℹ️ Нет выбранных разделов для экспорта")
        
        # ==============================================
        # ДЕТАЛЬНАЯ СТАТИСТИКА (полная ширина)
        # ==============================================
        st.markdown("---")
        st.markdown("### 📊 ДЕТАЛЬНАЯ СТАТИСТИКА БАЗЫ")
        
        if st.button("🔄 Обновить статистику", type="secondary", key="refresh_stats"):
            st.rerun()
        
        stats = db_admin.get_detailed_stats()
        
        # Общая статистика
        col_total1, col_total2, col_total3, col_total4 = st.columns(4)
        with col_total1:
            st.metric("Всего разделов", stats["total"]["sections"])
        with col_total2:
            st.metric("Всего документов", stats["total"]["documents"])
        with col_total3:
            st.metric("Всего слов", stats["total"]["words"])
        with col_total4:
            st.metric("Выбрано разделов", stats["total"]["selected"])
        
        # Статистика по папкам
        st.markdown("#### 📁 РАСПРЕДЕЛЕНИЕ ПО ПАПКАМ")
        
        if stats["by_folder"]:
            folders_data = []
            for folder, data in stats["by_folder"].items():
                folder_name = {
                    "normative": "📖 Нормативные",
                    "methodology": "📚 Методические",
                    "structured": "🗂️ Структурированные",
                    "expertise": "👨‍⚖️ Экспертные"
                }.get(folder, folder)
                
                folders_data.append({
                    "Папка": folder_name,
                    "Разделы": data["sections"],
                    "Документы": data["documents"],
                    "Слова": data["words"],
                    "Выбрано": data["selected"],
                    "% от общего": round((data["sections"] / stats["total"]["sections"] * 100), 1) if stats["total"]["sections"] > 0 else 0
                })
            
            # Сортируем по количеству разделов
            folders_data.sort(key=lambda x: x["Разделы"], reverse=True)
            
            # Отображаем таблицу
            df_folders = pd.DataFrame(folders_data)
            st.dataframe(
                df_folders,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Папка": st.column_config.TextColumn(width="medium"),
                    "Разделы": st.column_config.NumberColumn(format="%d"),
                    "Документы": st.column_config.NumberColumn(format="%d"),
                    "Слова": st.column_config.NumberColumn(format="%d"),
                    "Выбрано": st.column_config.NumberColumn(format="%d"),
                    "% от общего": st.column_config.NumberColumn(format="%.1f %%")
                }
            )
        
        # Статистика по форматам
        st.markdown("#### 📄 ФОРМАТЫ ДОКУМЕНТОВ")
        
        if stats["by_format"]:
            formats_data = []
            total_files = sum(stats["by_format"].values())
            
            for ext, count in stats["by_format"].items():
                format_name = {
                    ".md": "Markdown",
                    ".txt": "Текстовый файл",
                    ".pdf": "PDF документ",
                    ".docx": "Word документ"
                }.get(ext, ext)
                
                formats_data.append({
                    "Формат": format_name,
                    "Расширение": ext,
                    "Количество": count,
                    "% от общего": round((count / total_files * 100), 1)
                })
            
            # Сортируем по количеству
            formats_data.sort(key=lambda x: x["Количество"], reverse=True)
            
            # Отображаем таблицу
            df_formats = pd.DataFrame(formats_data)
            st.dataframe(
                df_formats,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Формат": st.column_config.TextColumn(width="medium"),
                    "Расширение": st.column_config.TextColumn(width="small"),
                    "Количество": st.column_config.NumberColumn(format="%d"),
                    "% от общего": st.column_config.NumberColumn(format="%.1f %%")
                }
            )
        
        # Последние обновления
        st.markdown("#### 🕐 ПОСЛЕДНИЕ ОБНОВЛЕНИЯ")
        
        if stats["recent_updates"]:
            for update in stats["recent_updates"][:5]:
                folder_icon = {
                    "normative": "📖",
                    "methodology": "📚",
                    "structured": "🗂️",
                    "expertise": "👨‍⚖️"
                }.get(update["folder"], "📄")
                
                st.caption(f"{folder_icon} **{update['document']}** - {update['section'][:50]}... ({update['date']})")
            
            if len(stats["recent_updates"]) > 5:
                st.caption(f"... и еще {len(stats['recent_updates']) - 5} обновлений")
        else:
            st.info("ℹ️ Нет информации о последних обновлениях")
        
        # Информация о системе
        st.markdown("---")
        st.markdown("#### ℹ️ ИНФОРМАЦИЯ О СИСТЕМЕ")
        
        col_sys1, col_sys2 = st.columns(2)
        
        with col_sys1:
            st.info(f"**Версия базы:** {db.metadata.get('version', '1.0')}")
            st.info(f"**Создана:** {db.metadata.get('created_at', 'Неизвестно')[:10]}")
        
        with col_sys2:
            st.info(f"**Обновлена:** {db.metadata.get('last_updated', 'Неизвестно')[:19]}")
            st.info(f"**Поддержка форматов:** {', '.join(CONFIG.get('supported_extensions', ['.md', '.txt']))}")

# ==============================================
# САЙДБАР
# ==============================================

with st.sidebar:
    st.header("📊 СТАТИСТИКА")
    
    # Основная статистика
    stats = db.get_database_stats()
    
    st.metric("Всего разделов", stats["total_sections"])
    st.metric("Всего документов", db.metadata.get("total_documents", 0))
    
    selected_count = stats["selected_sections"]
    st.metric("Выбрано разделов", selected_count)
    
    # Статистика по папкам
    st.markdown("---")
    st.header("📁 ПО ПАПКАМ")
    
    for folder, data in stats["folders_summary"].items():
        folder_name = {
            "normative": "📖 Нормативные",
            "methodology": "📚 Методические",
            "structured": "🗂️ Структурированные",
            "expertise": "👨‍⚖️ Экспертные"
        }.get(folder, folder)
        
        st.caption(f"{folder_name}")
        st.caption(f"  {data['sections']} разд. ({data['selected']} выбрано)")
    
    # Информация о шаблоне
    st.markdown("---")
    st.header("🎯 ШАБЛОН ВОПРОСА")
    
    templates_data = load_templates()
    selected_template = get_selected_template(templates_data)
    if selected_template:
        st.caption(f"{selected_template['name']}")
        st.caption(f"{selected_template['description'][:60]}...")
    else:
        st.caption("📭 Нет шаблона")
    
    # Быстрые действия
    st.markdown("---")
    st.header("⚡ БЫСТРЫЕ ДЕЙСТВИЯ")
    
    # Кнопка сохранения
    if st.session_state.has_unsaved_changes:
        if st.button("💾 Сохранить выбор", type="primary", use_container_width=True):
            db.save_database()
            st.success("Сохранено!")
            st.session_state.has_unsaved_changes = False
            st.rerun()
    
    # Экспорт в активную сессию
    if st.session_state.current_session and selected_count > 0:
        if st.button("📤 Экспорт в активную сессию", type="secondary", use_container_width=True):
            session_path = Path(st.session_state.current_session)
            success = session_manager.export_to_session(session_path, db)
            
            if success:
                st.success(f"✅ Экспортировано {selected_count} разделов")
                st.rerun()
    
    # Создание сессии с текущим шаблоном
    if st.button("📁 Создать новую сессию", type="secondary", use_container_width=True):
        # Получаем выбранный шаблон
        templates_data = load_templates()
        selected_template = get_selected_template(templates_data)
        template_prompt = selected_template.get("prompt", "") if selected_template else ""
        
        # Создаем сессию
        session_path = session_manager.create_session(template_prompt=template_prompt)
        if session_path:
            st.session_state.current_session = str(session_path)
            st.success(f"Создана сессия с шаблоном: {selected_template['name'] if selected_template else 'Без шаблона'}")
            st.rerun()
    
    # Административные действия
    if CONFIG.get("admin_enabled", True):
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
        
        # Кнопка перехода к настройкам шаблона
        if st.button("🎯 Изменить шаблон", use_container_width=True):
            # Переключаем на вкладку Настройки
            st.session_state.active_tab = "tab3"
            st.rerun()
    
    # Активная сессия
    st.markdown("---")
    
    if st.session_state.current_session:
        session_path = Path(st.session_state.current_session)
        if session_path.exists():
            st.header("✅ АКТИВНАЯ СЕССИЯ")
            st.markdown(f"**{session_path.name}**")
            
            # Проверка файлов в сессии
            files_info = session_manager.get_session_files(session_path)
            
            # Показываем информацию о промтах
            if files_info["has_prompt"]:
                prompt_files = files_info["prompt_files"]
                if prompt_files:
                    main_prompt = prompt_files[0]
                    st.caption(f"🎯 {main_prompt['name']}")
                    
                    if len(prompt_files) > 1:
                        st.caption(f"📚 (+{len(prompt_files)-1} других)")
            else:
                st.caption("📭 Нет промта")
            
            if files_info["has_materials"]:
                st.caption(f"📚 {files_info['materials_count']} разд.")
            
            if files_info["has_attachments"]:
                st.caption(f"📎 {len(files_info['attachments_list'])} файлов")
            
            if files_info["has_response"]:
                st.caption("🤖 Ответ готов")
            
            # Кнопка открытия
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