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

# Добавляем библиотеку для работы с RTF
try:
    import striprtf.striprtf as rtf
    RTF_SUPPORT = True
    print("✅ Поддержка RTF доступна")
except ImportError:
    RTF_SUPPORT = False
    print("⚠ Библиотека для RTF не установлена. Файлы .rtf будут игнорироваться.")

# ==============================================
# КОНФИГУРАЦИЯ ПАПОК И ТИПОВ ДОКУМЕНТОВ
# ==============================================

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
                
                # Проверяем обязательные ключи
                required_keys = ["folders", "database_path", "templates_path"]
                for key in required_keys:
                    if key not in config:
                        print(f"⚠ В конфигурации отсутствует ключ: {key}")
                
                return config
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка в формате JSON (строка {e.lineno}, позиция {e.pos}): {e.msg}")
        except Exception as e:
            print(f"❌ Ошибка загрузки конфигурации: {e}")
    
    # Конфигурация по умолчанию если файл не найден или поврежден
    print("⚠ Файл config.json не найден или поврежден. Используются значения по умолчанию.")
    
    # Создаем папку проекта
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
        "templates_path": str(project_dir / "templates.json"),
        "expert_sessions_path": str(project_dir / "expert_sessions"),
        "supported_extensions": [".md", ".txt", ".rtf"]
    }

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

# Загружаем конфигурацию
CONFIG = load_config()

# Получаем список поддерживаемых расширений
SUPPORTED_EXTENSIONS = CONFIG.get("supported_extensions", [".md", ".txt", ".rtf"])

# Создаем необходимые папки по умолчанию (если используются пути по умолчанию)
if not Path(CONFIG["folders"]["normative"]).exists():
    created = create_default_folders(CONFIG["folders"])
    if created:
        print(f"📁 Созданы папки по умолчанию:")
        for folder_type, path in created:
            print(f"   - {folder_type}: {path}")

# Проверяем доступность папок
folder_status = validate_folders(CONFIG["folders"])
if not folder_status["all_exist"]:
    print("⚠ Предупреждение: некоторые папки недоступны:")
    for folder_type, path in folder_status["missing"]:
        print(f"   - {folder_type}: {path}")
    print("ℹ️ Проверьте пути в файле config.json")

# Создаем папку для сессий эксперта
expert_sessions_path = Path(CONFIG.get("expert_sessions_path", "./expert_sessions"))
expert_sessions_path.mkdir(exist_ok=True, parents=True)

# ==============================================
# КЛАСС ДЛЯ РАБОТЫ С РАЗНЫМИ ФОРМАТАМИ ФАЙЛОВ
# ==============================================

class FileFormatReader:
    """Класс для чтения файлов разных форматов"""
    
    @staticmethod
    def read_file(file_path: Path) -> Optional[str]:
        """
        Читает файл любого поддерживаемого формата.
        Возвращает текст или None в случае ошибки.
        """
        if not file_path.exists():
            return None
        
        extension = file_path.suffix.lower()
        
        try:
            if extension == '.rtf':
                return FileFormatReader._read_rtf(file_path)
            elif extension in ['.md', '.txt']:
                return FileFormatReader._read_text(file_path)
            else:
                print(f"⚠ Неподдерживаемый формат файла: {extension}")
                return None
        except Exception as e:
            print(f"❌ Ошибка чтения файла {file_path}: {e}")
            return None
    
    @staticmethod
    def _read_rtf(file_path: Path) -> Optional[str]:
        """Читает RTF файл и конвертирует в обычный текст"""
        if not RTF_SUPPORT:
            print(f"⚠ RTF поддержка не установлена для файла {file_path}")
            return None
        
        try:
            # Читаем как бинарный файл
            with open(file_path, 'rb') as f:
                raw_data = f.read()
            
            if not raw_data:
                return ""
            
            # Пробуем определить кодировку
            encoding_result = chardet.detect(raw_data)
            encoding = encoding_result['encoding']
            
            # Пробуем разные кодировки
            encodings_to_try = ['utf-8', 'cp1251', 'cp1252', 'iso-8859-1', 'windows-1251']
            if encoding and encoding not in encodings_to_try:
                encodings_to_try.insert(0, encoding)
            
            rtf_content = None
            for enc in encodings_to_try:
                try:
                    rtf_content = raw_data.decode(enc, errors='strict')
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            
            if rtf_content is None:
                # Последняя попытка с игнорированием ошибок
                try:
                    rtf_content = raw_data.decode('utf-8', errors='ignore')
                except:
                    rtf_content = raw_data.decode('latin-1', errors='ignore')
            
            # Конвертируем RTF в обычный текст
            try:
                plain_text = rtf.rtf_to_text(rtf_content)
                return plain_text
            except Exception as rtf_error:
                print(f"⚠ Ошибка конвертации RTF {file_path}: {rtf_error}")
                # Если не удалось сконвертировать, возвращаем как есть
                return rtf_content
        
        except Exception as e:
            print(f"❌ Ошибка чтения RTF файла {file_path}: {e}")
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
# СИСТЕМА УПРАВЛЕНИЯ ШАБЛОНАМИ ВОПРОСОВ
# ==============================================

class TemplateManager:
    """Управление шаблонами вопросов для ИИ"""
    
    def __init__(self):
        self.templates_path = Path(CONFIG["templates_path"])
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict:
        """Загружаем шаблоны из файла"""
        # Если файл существует, пытаемся его прочитать
        if self.templates_path.exists():
            try:
                with open(self.templates_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:  # Проверяем, что файл не пустой
                        templates = json.loads(content)
                        
                        # ⭐ ДОБАВЛЕНА ПРОВЕРКА СТРУКТУРЫ ⭐
                        if not isinstance(templates, dict):
                            print(f"❌ Неверный формат: templates должен быть словарем, а не {type(templates).__name__}")
                            raise ValueError("Неправильный формат данных")
                        
                        if "templates" not in templates:
                            print(f"❌ Неверная структура: отсутствует ключ 'templates'")
                            raise ValueError("Отсутствует ключ 'templates'")
                        
                        if not isinstance(templates["templates"], list):
                            print(f"❌ Неверная структура: 'templates' должен быть списком")
                            raise ValueError("'templates' должен быть списком")
                        
                        print(f"✅ Шаблоны загружены из файла: {self.templates_path}")
                        print(f"✅ Загружено {len(templates['templates'])} шаблонов")
                        return templates
                    
            except json.JSONDecodeError as e:
                print(f"❌ Ошибка JSON в файле шаблонов: {e}")
                print(f"❌ Строка с ошибкой: {e.doc}")
                print(f"❌ Позиция ошибки: {e.pos}")
                
            except ValueError as e:
                print(f"❌ Ошибка структуры файла: {e}")
                
            except Exception as e:
                print(f"❌ Ошибка загрузки шаблонов: {e}")
                import traceback
                traceback.print_exc()
        
        # Создаем стандартные шаблоны только если файла нет или он пустой/битый
        print("📝 Создаю дефолтные шаблоны...")
        default_templates = self._get_default_templates()
        
        # Сохраняем дефолтные шаблоны ТОЛЬКО если файла не существует
        if not self.templates_path.exists():
            self._save_templates(default_templates)
        
        return default_templates
    
    def _get_default_templates(self) -> Dict:
        """Возвращает дефолтные шаблоны"""
        return {
            "templates": [
                {
                    "id": "analytical_report",
                    "name": "📊 Аналитический отчет",
                    "description": "Аналитический отчет с детальным анализом нормативной базы и практическими рекомендациями",
                    "prompt": "Ты — старший эксперт-аналитик в области землепользования, кадастра и градостроительного регулирования.\n\nОСНОВНОЕ ПРАВИЛО: Используй информацию ТОЛЬКО из предоставленных материалов.\n\nВАЖНО:\n- Каждое утверждение должно подтверждаться предоставленными материалами\n- Если информации недостаточно — прямо указывай на это\n- Если в материалах отсутствуют нужные сведения, укажи КАКИЕ ИМЕННО дополнительные материалы необходимы\n- Не используй внешние знания\n\nСТРУКТУРА ОТВЕТА:\n1. КРАТКИЙ ОТВЕТ: Основной вывод в 2-3 предложениях\n2. НОРМАТИВНАЯ БАЗА: Ключевые документы из материалов\n3. АНАЛИЗ: Связь норм с вопросом на основе материалов\n4. ВЫВОДЫ: Пронумерованные выводы из материалов\n5. РЕКОМЕНДАЦИИ: Конкретные действия, обоснованные материалами\n6. НЕДОСТАЮЩИЕ МАТЕРИАЛЫ (если требуется): Какие именно документы или сведения отсутствуют\n\nОТВЕТ ЭКСПЕРТА-АНАЛИТИКА:"
                },
                {
                    "id": "brief_qa",
                    "name": "⚡ Краткий ответ с рекомендациями",
                    "description": "Краткий формат: вопрос своими словами, прямой ответ и конкретные рекомендации",
                    "prompt": "Ты — эксперт в области землепользования и кадастра.\n\nИспользуй информацию ТОЛЬКО из предоставленных материалов.\n\nВАЖНО:\n- Все выводы должны быть основаны ТОЛЬКО на предоставленных материалах\n- Если информации недостаточно — укажи это явно\n- Если нужные сведения отсутствуют, перечисли КАКИЕ ИМЕННО материалы требуются\n\nПодготовь краткий ответ по структуре:\n1. ВОПРОС (СВОИМИ СЛОВАМИ): Переформулировка на основе материалов\n2. ПРЯМОЙ ОТВЕТ: Краткий ответ с обоснованием из материалов\n3. РЕКОМЕНДАЦИИ: конкретные рекомендации, обоснованные материалами\n4. НЕДОСТАЮЩАЯ ИНФОРМАЦИЯ (если есть): Что именно отсутствует в материалах\n\nОТВЕТ ЭКСПЕРТА:"
                },
                {
                    "id": "standard",
                    "name": "📝 Стандартный ответ",
                    "description": "Развернутый профессиональный ответ с анализом",
                    "prompt": "Ты — эксперт в области землепользования и кадастра.\n\nНа основе предоставленных материалов подготовь развернутый профессиональный ответ.\n\nИНСТРУКЦИЯ:\n1. Проанализируй все предоставленные материалы\n2. Используй информацию ТОЛЬКО из предоставленных материалов\n3. Если информации недостаточно — укажи это явно\n4. Если отсутствуют нужные сведения, перечисли КАКИЕ ИМЕННО документы или данные необходимы\n5. Не используй внешние знания или предположения\n\nСТРУКТУРА ОТВЕТА:\n1. ПОВТОРЕНИЕ ВОПРОСА: Сформулируй исходный вопрос своими словами, показывая правильное понимание и задавая рамки анализа\n2. Краткий ответ: 2-3 предложения с дословным ответом\n3. Детальный ответ с анализом (только на основе материалов)\n4. Практические рекомендации (обоснованные материалами)\n5. Выводы\n6. НЕДОСТАЮЩИЕ СВЕДЕНИЯ (при необходимости): Конкретный перечень того, чего не хватает в материалах\n\nОТВЕТ ЭКСПЕРТА:"
                },
                {
                    "id": "detailed_with_gaps",
                    "name": "🔍 Детальный анализ с выявлением пробелов",
                    "description": "Детальный анализ с выявлением недостающих сведений и рекомендациями по их получению",
                    "prompt": "Ты — старший эксперт-аналитик в области землепользования и кадастра.\n\nОСНОВНОЕ ПРАВИЛО: Используй информацию ТОЛЬКО из предоставленных материалов.\n\nКРИТИЧЕСКИ ВАЖНО:\n1. Все выводы должны быть подтверждены материалами\n2. Если информация отсутствует или недостаточна — укажи это ЧЕТКО\n3. Перечисли КОНКРЕТНО какие документы/данные нужны\n4. Никаких предположений и внешних знаний\n\nСТРУКТУРА ОТВЕТА:\n1. КРАТКАЯ СВОДКА: Суть вопроса и общий вывод\n2. ИМЕЮЩИЕСЯ МАТЕРИАЛЫ: Что есть в документах\n3. АНАЛИЗ НА ОСНОВЕ МАТЕРИАЛОВ: Что можно сказать на основе имеющегося\n4. ПРОБЕЛЫ И НЕДОСТАТКИ: Чего не хватает для полного ответа\n5. КОНКРЕТНЫЕ НЕДОСТАЮЩИЕ МАТЕРИАЛЫ: Список необходимых документов/данных\n6. ВЫВОДЫ И РЕКОМЕНДАЦИИ (на основе имеющегося)\n\nОТВЕТ ЭКСПЕРТА:"
                }
            ],
            "default_template": "standard",
            "last_updated": datetime.now().isoformat()
        }
    
    def _save_templates(self, templates: Dict):
        """Сохраняем шаблоны в файл"""
        try:
            self.templates_path.parent.mkdir(exist_ok=True, parents=True)
            with open(self.templates_path, 'w', encoding='utf-8') as f:
                json.dump(templates, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения шаблонов: {e}")
    
    def get_templates_list(self) -> List[Dict]:
        """Возвращает список доступных шаблонов"""
        return self.templates.get("templates", [])
    
    def get_template_by_id(self, template_id: str) -> Optional[Dict]:
        """Возвращает шаблон по ID"""
        for template in self.templates.get("templates", []):
            if template.get("id") == template_id:
                return template
        return None
    
    def get_default_template(self) -> Dict:
        """Возвращает шаблон по умолчанию"""
        default_id = self.templates.get("default_template", "standard")
        template = self.get_template_by_id(default_id)
        if template:
            return template
        else:
            # Если шаблон по умолчанию не найден, берем первый из списка
            templates_list = self.get_templates_list()
            if templates_list:
                return templates_list[0]
            # Если вообще нет шаблонов, возвращаем пустой
            return {"id": "empty", "name": "Пустой", "description": "", "prompt": ""}
    
    def update_templates(self, new_templates: Dict):
        """Обновляет шаблоны и сохраняет в файл"""
        self.templates = new_templates
        self._save_templates(new_templates)
    
    def reload_templates(self):
        """Перезагружает шаблоны из файла"""
        self.templates = self._load_templates()

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
            except Exception as e:
                print(f"❌ Ошибка загрузки базы разделов: {e}")
                return []
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
            except Exception as e:
                print(f"❌ Ошибка загрузки метаданных: {e}")
                return {}
        print("📁 Метаданные базы не найдены, создаются новые")
        return {
            "created_at": "",
            "last_updated": "",
            "total_sections": 0,
            "total_documents": 0,
            "by_folder": {},
            "supported_extensions": SUPPORTED_EXTENSIONS
        }
    
    def _clean_text_from_comments(self, text: str) -> str:
        """Очищает текст от различных комментариев и служебной информации"""
        if not text:
            return text
        
        # Паттерны для удаления - ТОЛЬКО конкретные комментарии
        patterns_to_remove = [
            r'\(в ред\. [^)]*\)',
            r'\(введена [^)]*\)',
            r'\(п\. \d+ в ред\. [^)]*\)',
            r'\[[^\]]*Консультант[^\]]*\]',
            r'КонсультантПлюс: примечание\..*?(?=\n\n|\Z)',
            r'Федеральн(?:ого|ым) законом от \d{2}\.\d{2}\.\d{4} [№N]\d+-\S+',
            r'см\. [^.]*\.',
            r'ред\. \d{2}\.\d{2}\.\d{4}',
            r'©.*',
            r'\(п\. \d+\.\d введен Федеральным законом от \d{2}\.\d{2}\.\d{4} N \d+-\S+\)',
            r'\(в ред\. Федерального закона от \d{2}\.\d{2}\.\d{4} N \d+-\S+\)'
        ]
        
        cleaned_text = text
        
        # Очищаем каждый паттерн отдельно
        for pattern in patterns_to_remove:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE|re.DOTALL)
        
        return cleaned_text
    
    def _clean_special_characters(self, text: str) -> str:
        """Очищает текст от специальных символов и форматирования, убирает лишние пустые строки"""
        if not text:
            return text
        
        # Удаляем множественные пробелы и табуляции
        cleaned = re.sub(r'[ \t]+', ' ', text)
        
        # Удаляем символы мягких переносов и другие специальные символы
        cleaned = cleaned.replace('\xad', '')  # мягкий перенос
        cleaned = cleaned.replace('\xa0', ' ')  # неразрывный пробел
        
        # Удаляем скрытые символы форматирования
        cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', cleaned)
        
        # Удаляем множественные переносы строк (оставляем максимум 2 подряд)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        
        # Удаляем пустые строки в начале и конце
        cleaned = cleaned.strip()
        
        # Заменяем множественные пробелы на один
        cleaned = re.sub(r' +', ' ', cleaned)
        
        # Удаляем пробелы в начале и конце каждой строки
        lines = cleaned.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line:  # добавляем только непустые строки
                cleaned_lines.append(line)
        
        # Собираем обратно с нормальными переносами строк
        cleaned = '\n'.join(cleaned_lines)
        
        return cleaned
    
    def _extract_yaml_metadata(self, content: str) -> Dict:
        """Извлекает метаданные из YAML заголовка в начале документа"""
        metadata = {}
        
        try:
            content_stripped = content.strip()
            if content_stripped.startswith('---'):
                parts = content_stripped.split('---', 2)
                if len(parts) >= 3:
                    yaml_content = parts[1].strip()
                    if yaml_content:
                        metadata = yaml.safe_load(yaml_content) or {}
        except (yaml.YAMLError, AttributeError) as e:
            print(f"  ⚠ Не удалось прочитать YAML: {e}")
        
        if not isinstance(metadata, dict):
            metadata = {}
        
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
        except Exception as e:
            print(f"❌ Ошибка сохранения базы данных: {e}")
    
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
            
            # Ищем файлы ВСЕХ поддерживаемых форматов
            files = []
            for ext in SUPPORTED_EXTENSIONS:
                files.extend(list(folder.rglob(f"*{ext}")))
            
            folder_sections = 0
            folder_documents = len(files)
            
            for file_path in files:
                print(f"  📄 {file_path.name} ({file_path.suffix})...", end="")
                
                try:
                    # Используем универсальный ридер файлов
                    content = self.file_reader.read_file(file_path)
                    
                    if content is None:
                        print(f" ❌ Не удалось прочитать файл")
                        continue
                    
                    # Извлекаем метаданные из YAML заголовка
                    metadata = self._extract_yaml_metadata(content)
                    
                    # Получаем название документа из метаданных или имени файла
                    document_title = metadata.get('title', file_path.stem)
                    
                    # ОЧИЩАЕМ ТЕКСТ ОТ СЛУЖЕБНЫХ СИМВОЛОВ
                    cleaned_content = self._clean_special_characters(content)
                    
                    # РАЗБИВАЕМ ДОКУМЕНТ НА РАЗДЕЛЫ В ЗАВИСИМОСТИ ОТ ТИПА ПАПКИ
                    sections = self._split_document_by_type(
                        cleaned_content,
                        file_path, 
                        folder_name, 
                        document_title
                    )
                    
                    print(f" → {len(sections)} разделов")
                    folder_sections += len(sections)
                    
                    # Добавляем разделы в общий список
                    for i, section in enumerate(sections):
                        # ОЧИЩАЕМ КОНТЕНТ КАЖДОГО РАЗДЕЛА ОТ КОММЕНТАРИЕВ
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
                            "selected": False
                        })
                        
                except Exception as e:
                    print(f" ❌ Ошибка: {e}")
                    import traceback
                    traceback.print_exc()
            
            folder_stats[folder_name] = {
                "documents": folder_documents,
                "sections": folder_sections
            }
        
        # Обновляем базу
        self.sections = all_sections
        
        # Обновляем метаданные
        self.metadata = {
            "created_at": self.metadata.get("created_at", datetime.now().isoformat()),
            "last_updated": datetime.now().isoformat(),
            "total_sections": len(all_sections),
            "total_documents": sum(stats["documents"] for stats in folder_stats.values()),
            "by_folder": folder_stats,
            "supported_extensions": SUPPORTED_EXTENSIONS
        }
        
        # Сохраняем
        self.save_database()
        
        print(f"\n✅ База создана!")
        print(f"   Всего документов: {self.metadata['total_documents']}")
        print(f"   Всего разделов: {self.metadata['total_sections']}")
        
        # Статистика по форматам
        format_stats = {}
        for section in all_sections:
            ext = section.get("document_extension", ".txt").lower()
            format_stats[ext] = format_stats.get(ext, 0) + 1
        
        print(f"   Форматы документов:")
        for ext, count in format_stats.items():
            print(f"     {ext}: {count} документов")
        
        for folder_name, stats in folder_stats.items():
            print(f"   📁 {folder_name}: {stats['documents']} док. → {stats['sections']} разд.")
        
        return all_sections
    
    def _split_document_by_type(self, content: str, file_path: Path, folder_type: str, doc_title: str) -> List[Dict]:
        """Разбиваем документ на разделы в зависимости от типа папки"""
        
        if folder_type == "normative":
            return self._split_normative_document(content, file_path, doc_title)
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
    
    def _split_normative_document(self, content: str, file_path: Path, doc_title: str) -> List[Dict]:
        """Разделение нормативных документов по 'ГЛАВА' или 'Глава' с номером"""
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
        
        # Паттерны для поиска глав (ТОЛЬКО ГЛАВА, без Статей)
        patterns = [
            (r'^ГЛАВА\s+[IVXLCDM\d]+[\s\.\-:].*$', "chapter"),
            (r'^Глава\s+[IVXLCDM\d]+[\s\.\-:].*$', "chapter"),
            (r'^ГЛАВА\s+[0-9]+[\s\.\-:].*$', "chapter"),
            (r'^Глава\s+[0-9]+[\s\.\-:].*$', "chapter"),
        ]
        
        for line in lines:
            is_header = False
            for pattern, section_type in patterns:
                match = re.match(pattern, line.strip())
                if match:
                    if current_section:
                        sections.append({
                            "title": current_title,
                            "content": "\n".join(current_section).strip(),
                            "type": current_type
                        })
                    
                    current_title = line.strip()
                    current_type = section_type
                    current_section = []
                    is_header = True
                    break
            
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
    
    def _split_methodology_document(self, content: str, file_path: Path, doc_title: str) -> List[Dict]:
        """Разделение методических документов на заголовки 1 и 2 уровня markdown"""
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
        
        patterns = [
            (r'^#\s+(.+)$', "h1"),
            (r'^##\s+(.+)$', "h2"),
        ]
        
        for line in lines:
            is_header = False
            for pattern, section_type in patterns:
                match = re.match(pattern, line.strip())
                if match:
                    if current_section:
                        sections.append({
                            "title": current_title,
                            "content": "\n".join(current_section).strip(),
                            "type": current_type
                        })
                    
                    current_title = match.group(1)
                    current_type = section_type
                    current_section = []
                    is_header = True
                    break
            
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
    
    def _split_structured_document(self, content: str, file_path: Path, doc_title: str) -> List[Dict]:
        """Разделение структурированных документов по квадратным скобкам"""
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
        
        # Паттерн для поиска заголовков в квадратных скобках
        bracket_pattern = r'^\[([^\[\]]+)\]$'
        
        for line in lines:
            line_stripped = line.strip()
            is_header = False
            
            # Проверяем, является ли строка заголовком в квадратных скобках
            match = re.match(bracket_pattern, line_stripped)
            if match:
                header_content = match.group(1).strip()
                
                # Дополнительная проверка: заголовок должен быть не слишком длинным
                # и содержать осмысленный текст (не только цифры или служебные символы)
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
        """Экспертные документы сохраняем полностью без разделения"""
        
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
        """Возвращает разделы для отображения с удобной структуряой"""
        display_data = []
        
        for section in self.sections:
            section_id = section.get("id", str(uuid.uuid4()))
            folder = section.get("folder", "unknown")
            doc_file = section.get("document", "")
            doc_ext = section.get("document_extension", ".txt")
            doc_title = section.get("document_title", doc_file)
            section_title = section.get("title", doc_title)
            section_type = section.get("section_type", "text")
            content = section.get("content", "")
            word_count = section.get("word_count", 0)
            selected = section.get("selected", False)
            
            # Сокращаем заголовок для отображения
            short_doc_title = doc_title[:40] + "..." if len(doc_title) > 40 else doc_title
            short_section_title = section_title[:60] + "..." if len(section_title) > 60 else section_title
            
            # Добавляем квадратные скобки для структурированных документов
            if folder == "structured" and not section_title.startswith("["):
                short_section_title = f"[{short_section_title}]"
                section_title = f"[{section_title}]"
            
            # Добавляем иконку формата
            format_icon = {
                ".md": "📝",
                ".txt": "📄",
                ".rtf": "📋"
            }.get(doc_ext.lower(), "📎")
            
            display_data.append({
                "id": section_id,
                "folder": folder,
                "document": f"{format_icon} {short_doc_title}",
                "document_full": doc_title,
                "file": doc_file,
                "extension": doc_ext,
                "section": short_section_title,
                "section_full": section_title,
                "type": section_type,
                "words": word_count,
                "selected": selected,
                "content_full": content
            })
        
        return display_data
    
    def update_selections(self, selected_ids: List[str]):
        """Обновляет выбор эксперта"""
        for section in self.sections:
            section_id = section.get("id", "")
            section["selected"] = section_id in selected_ids
        
        self.save_database()
    
    def get_selected_sections(self) -> List[Dict]:
        """Возвращает выбранные экспертом разделы"""
        return [s for s in self.sections if s.get("selected", False)]
    
    def clear_selections(self):
        """Очищает все выборы"""
        for section in self.sections:
            section["selected"] = False
        
        self.save_database()

# ==============================================
# ГЕНЕРАТОР ФАЙЛОВ ДЛЯ ЭКСПЕРТА
# ==============================================

class ExpertFileGenerator:
    """Генерирует файлы для работы эксперта с DeepSeek"""
    
    @staticmethod
    def _clean_content_for_output(content: str) -> str:
        """Дополнительная очистка контента для вывода в файлы - удаляет лишние пробелы и пустые строки"""
        if not content:
            return content
        
        # Удаляем множественные переносы строк (оставляем максимум 2 подряд)
        cleaned = re.sub(r'\n{3,}', '\n\n', content)
        
        # Удаляем пустые строки в начале и конце
        cleaned = cleaned.strip()
        
        # Удаляем пробелы в начале и конце каждой строки
        lines = cleaned.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:  # добавляем только непустые строки
                # Удаляем множественные пробелы внутри строки
                line = re.sub(r' +', ' ', line)
                cleaned_lines.append(line)
        
        # Собираем обратно, оставляя по одной пустой строки между абзацами
        if not cleaned_lines:
            return ""
        
        result = []
        for i, line in enumerate(cleaned_lines):
            result.append(line)
            # Добавляем пустую строку только если следующая строка не пустая
            # и если это не последняя строка
            if i < len(cleaned_lines) - 1 and cleaned_lines[i+1]:
                result.append('')
        
        return '\n'.join(result)
    
    @staticmethod
    def create_prompt_file(selected_sections: List[Dict], output_dir: Path, 
                         template_manager: TemplateManager, selected_template_id: str) -> Optional[Path]:
        """Создает файл с промтом для DeepSeek и возвращает путь к папке сессии"""
        if not selected_sections:
            return None
        
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = output_dir / session_id
        session_dir.mkdir(exist_ok=True, parents=True)
        
        # Получаем выбранный шаблон
        selected_template = template_manager.get_template_by_id(selected_template_id)
        if not selected_template:
            selected_template = template_manager.get_default_template()
        
        # 1. Создаем файл all_sections.md
        all_sections_file = session_dir / "all_sections.md"
        try:
            with open(all_sections_file, 'w', encoding='utf-8') as f:
                f.write("# ВЫБРАННЫЕ РАЗДЕЛЫ ДЛЯ ОТВЕТА\n\n")
                f.write(f"**Используемый шаблон:** {selected_template.get('name', 'Стандартный')}\n\n")
                
                by_folder = {}
                for section in selected_sections:
                    folder = section.get("folder", "unknown")
                    if folder not in by_folder:
                        by_folder[folder] = []
                    by_folder[folder].append(section)
                
                folder_names = {
                    "normative": "📖 НОРМАТИВНЫЕ АКТЫ",
                    "methodology": "📚 МЕТОДИЧЕСКИЕ МАТЕРИАЛЫ",
                    "structured": "🗂️ СТРУКТУРИРОВАННЫЕ ДОКУМЕНТЫ",
                    "expertise": "👨‍⚖️ ЭКСПЕРТНЫЕ ЗАКЛЮЧЕНИЯ"
                }
                
                for folder, sections in by_folder.items():
                    folder_name = folder_names.get(folder, folder)
                    
                    f.write(f"\n## {folder_name}\n\n")
                    
                    for section in sections:
                        # Для структурированных документов добавляем скобки в заголовок
                        section_title = section.get('title', 'Без названия')
                        if folder == "structured" and not section_title.startswith("["):
                            section_title = f"[{section_title}]"
                        
                        f.write(f"### {section_title}\n")
                        f.write(f"*Название документа:* {section.get('document_title', section.get('document', 'Без названия'))}\n")
                        f.write(f"*Файл:* {section.get('document', '')}\n")
                        f.write(f"*Формат:* {section.get('document_extension', '.txt')}\n")
                        f.write(f"*Тип раздела:* {section.get('section_type', 'text')}\n")
                        f.write(f"*Количество слов:* {section.get('word_count', 0)}\n")
                        
                        metadata = section.get('metadata', {})
                        if metadata and isinstance(metadata, dict):
                            if metadata.get('title'):
                                f.write(f"*Название:* {metadata['title']}\n")
                            if metadata.get('author'):
                                f.write(f"*Автор:* {metadata['author']}\n")
                            if metadata.get('date'):
                                f.write(f"*Дата:* {metadata['date']}\n")
                        
                        # Очищаем контент перед записью
                        cleaned_content = ExpertFileGenerator._clean_content_for_output(section.get('content', ''))
                        f.write(f"\n{cleaned_content}\n\n")
                        f.write("---\n\n")
        except Exception as e:
            print(f"Ошибка при создании all_sections.md: {e}")
            return None
        
        # 2. Создаем файл deepseek_prompt.txt
        prompt_file = session_dir / "deepseek_prompt.txt"
        try:
            with open(prompt_file, 'w', encoding='utf-8') as f:
                prompt_content = ExpertFileGenerator._generate_prompt(
                    selected_sections, 
                    selected_template.get('prompt', '')
                )
                f.write(prompt_content)
        except Exception as e:
            print(f"Ошибка при создании deepseek_prompt.txt: {e}")
            return None
        
        # 3. Создаем файл report.txt
        report_file = session_dir / "report.txt"
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                report_content = ExpertFileGenerator._generate_report(
                    selected_sections, 
                    session_id, 
                    selected_template
                )
                f.write(report_content)
        except Exception as e:
            print(f"Ошибка при создании report.txt: {e}")
            return None
        
        # 4. Создаем файл sections_data.json
        json_file = session_dir / "sections_data.json"
        try:
            with open(json_file, 'w', encoding='utf-8') as f:
                # Упрощаем данные для JSON
                simplified_sections = []
                for section in selected_sections:
                    # Для структурированных документов добавляем скобки в заголовок
                    title = section.get("title", "")
                    if section.get("folder") == "structured" and not title.startswith("["):
                        title = f"[{title}]"
                    
                    simplified = {
                        "id": section.get("id"),
                        "folder": section.get("folder"),
                        "document": section.get("document"),
                        "document_extension": section.get("document_extension"),
                        "document_title": section.get("document_title"),
                        "title": title,
                        "content": section.get("content"),
                        "section_type": section.get("section_type"),
                        "word_count": section.get("word_count"),
                        "metadata": section.get("metadata", {})
                    }
                    simplified_sections.append(simplified)
                
                json.dump(simplified_sections, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка при создании sections_data.json: {e}")
            return None
        
        # 5. Сохраняем информацию о шаблоне
        template_file = session_dir / "template_info.json"
        try:
            with open(template_file, 'w', encoding='utf-8') as f:
                template_info = {
                    "template_id": selected_template.get("id"),
                    "template_name": selected_template.get("name"),
                    "template_description": selected_template.get("description"),
                    "created_at": datetime.now().isoformat()
                }
                json.dump(template_info, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка при создании template_info.json: {e}")
            return None
        
        print(f"\n✅ Файлы созданы в папке: {session_dir}")
        print(f"📄 1. all_sections.md - все выбранные разделы")
        print(f"🤖 2. deepseek_prompt.txt - готовый промт для DeepSeek")
        print(f"📊 3. report.txt - отчет по сессии")
        print(f"📁 4. sections_data.json - данные в формате JSON")
        print(f"🎯 5. template_info.json - информация о шаблоне")
        
        return session_dir
    
    @staticmethod
    def _generate_prompt(sections: List[Dict], template_prompt: str) -> str:
        """Генерирует промт для DeepSeek (вопрос ПЕРЕД материалами)"""
        prompt = ""
        
        # 1. Сначала добавляем вопрос (шаблон)
        prompt += template_prompt
        prompt += "\n\n"
        
        # 2. Затем добавляем материалы
        prompt += "МАТЕРИАЛЫ ДЛЯ ОТВЕТА:\n"
        prompt += "=" * 60 + "\n\n"
        
        for i, section in enumerate(sections, 1):
            folder = section.get("folder", "unknown")
            folder_name = {
                "normative": "Нормативный акт",
                "methodology": "Методический материал",
                "structured": "Структурированный документ",
                "expertise": "Экспертное заключение"
            }.get(folder, "Материал")
            
            section_title = section.get("title", "Без названия")
            # Для структурированных документов добавляем скобки в заголовок
            if folder == "structured" and not section_title.startswith("["):
                section_title = f"[{section_title}]"
                
            doc_title = section.get("document_title", section.get("document", "Без названия"))
            doc_file = section.get("document", "")
            doc_ext = section.get("document_extension", ".txt")
            section_type = section.get("section_type", "text")
            
            prompt += f"\n{'='*60}\n"
            prompt += f"МАТЕРИАЛ {i}: {section_title}\n"
            prompt += f"Тип: {folder_name} | Документ: {doc_title}\n"
            prompt += f"Файл: {doc_file} | Формат: {doc_ext} | Тип раздела: {section_type}\n"
            
            metadata = section.get('metadata', {})
            if metadata and isinstance(metadata, dict):
                if metadata.get('author'):
                    prompt += f"Автор: {metadata['author']} | "
                if metadata.get('date'):
                    prompt += f"Дата: {metadata['date']}"
                prompt += f"\n"
            
            prompt += f"{'-'*40}\n\n"
            
            # Очищаем контент перед добавлением
            cleaned_content = ExpertFileGenerator._clean_content_for_output(section.get('content', ''))
            prompt += f"{cleaned_content}\n"
        
        prompt += f"\n{'='*60}\n\n"
        
        return prompt
    
    @staticmethod
    def _generate_report(sections: List[Dict], session_id: str, template: Dict) -> str:
        """Генерирует отчет по сессии"""
        by_folder = {}
        total_words = 0
        
        for section in sections:
            folder = section.get("folder", "unknown")
            if folder not in by_folder:
                by_folder[folder] = []
            by_folder[folder].append(section)
            total_words += section.get("word_count", 0)
        
        folder_names = {
            "normative": "Нормативные акты",
            "methodology": "Методические материалы",
            "structured": "Структурированные документы",
            "expertise": "Экспертные заключения"
        }
        
        report = f"ОТЧЕТ ПО СЕССИИ ЭКСПЕРТА\n"
        report += f"========================\n\n"
        report += f"ID сессии: {session_id}\n"
        report += f"Дата создания: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        report += f"ВЫБРАННЫЙ ШАБЛОН:\n"
        report += f"• Название: {template.get('name', 'Стандартный')}\n"
        report += f"• Описание: {template.get('description', '')}\n"
        report += f"• ID: {template.get('id', 'standard')}\n\n"
        
        report += f"СТАТИСТИКА:\n"
        report += f"• Всего выбрано разделов: {len(sections)}\n"
        report += f"• Общий объем: {total_words} слов\n\n"
        
        if by_folder:
            report += f"РАСПРЕДЕЛЕНИЕ ПО ТИПАМ МАТЕРИАЛОВ:\n"
            for folder, folder_sections in by_folder.items():
                name = folder_names.get(folder, folder)
                words = sum(s.get("word_count", 0) for s in folder_sections)
                report += f"• {name}: {len(folder_sections)} разделов ({words} слов)\n"
        
        # Статистика по форматам
        format_stats = {}
        for section in sections:
            ext = section.get("document_extension", ".txt").lower()
            format_stats[ext] = format_stats.get(ext, 0) + 1
        
        if format_stats:
            report += f"\nРАСПРЕДЕЛЕНИЕ ПО ФОРМАТАМ:\n"
            for ext, count in format_stats.items():
                format_name = {
                    ".md": "Markdown",
                    ".txt": "Текстовый",
                    ".rtf": "RTF"
                }.get(ext, ext)
                report += f"• {format_name}: {count} документов\n"
        
        report += f"\nСПИСОК ВЫБРАННЫХ РАЗДЕЛОВ:\n"
        for i, section in enumerate(sections, 1):
            folder = section.get("folder", "unknown")
            folder_icon = {
                "normative": "📖",
                "methodology": "📚",
                "structured": "🗂️",
                "expertise": "👨‍⚖️"
            }.get(folder, "📄")
            
            # Иконка формата
            doc_ext = section.get("document_extension", ".txt")
            format_icon = {
                ".md": "📝",
                ".txt": "📄",
                ".rtf": "📋"
            }.get(doc_ext.lower(), "📎")
            
            section_title = section.get("title", "Без названия")
            # Для структурированных документов добавляем скобки в заголовок
            if folder == "structured" and not section_title.startswith("["):
                section_title = f"[{section_title}]"
                
            doc_title = section.get("document_title", section.get("document", "Без названия"))
            word_count = section.get("word_count", 0)
            
            report += f"{i}. {folder_icon}{format_icon} {section_title} ({word_count} слов)\n"
            report += f"   Документ: {doc_title} ({doc_ext})\n"
        
        report += f"\nФАЙЛЫ СЕССИИ:\n"
        report += f"1. all_sections.md - все выбранные разделы\n"
        report += f"2. deepseek_prompt.txt - промт для DeepSeek\n"
        report += f"3. report.txt - этот отчет\n"
        report += f"4. sections_data.json - данные в JSON\n"
        report += f"5. template_info.json - информация о шаблоне\n"
        
        return report

# ==============================================
# ВЕБ-ИНТЕРФЕЙС ДЛЯ ЭКСПЕРТА (Streamlit)
# ==============================================

# Адаптивный дизайн для мобильных устройств
hide_streamlit_style = """
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

/* Убираем все лишние отступы и разделители */
div.stCheckbox > div > div {
    margin: 0 !important;
    padding: 0 !important;
}
div[data-testid="stVerticalBlock"] > div {
    margin-bottom: 0 !important;
}
/* Уменьшаем отступы между элементами */
div.stContainer {
    padding-top: 1px !important;
    padding-bottom: 1px !important;
}
/* Компактные чекбоксы */
.stCheckbox label {
    padding: 1px 0 !important;
    min-height: auto !important;
}

/* Убираем толстые линии в темной теме */
[data-theme="dark"] hr {
    border-color: #444 !important;
    margin: 2px 0 !important;
}

/* Стили для выбора шаблона */
.template-card {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: all 0.2s;
}
.template-card:hover {
    border-color: #4CAF50;
    background-color: #f8fff8;
}
.template-card.selected {
    border-color: #4CAF50;
    background-color: #e8f5e8;
    border-width: 2px;
}
.template-name {
    font-weight: 600;
    font-size: 1rem;
    margin-bottom: 4px;
}
.template-description {
    font-size: 0.85rem;
    color: #666;
    margin-bottom: 0;
}
[data-theme="dark"] .template-card {
    border-color: #555;
    background-color: #2d2d2d;
}
[data-theme="dark"] .template-card:hover {
    border-color: #4CAF50;
    background-color: #1e3a1e;
}
[data-theme="dark"] .template-card.selected {
    border-color: #4CAF50;
    background-color: #1e3a1e;
}
[data-theme="dark"] .template-description {
    color: #aaa;
}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Инициализация базы данных и менеджера шаблонов
@st.cache_resource
def init_database():
    return SimpleSectionDatabase()

@st.cache_resource
def init_template_manager():
    return TemplateManager()

# Инициализация сессии
if 'db' not in st.session_state:
    st.session_state.db = init_database()
    st.session_state.template_manager = init_template_manager()
    st.session_state.notifications = []
    st.session_state.last_update_time = datetime.now()
    st.session_state.current_filter_hash = ""
    st.session_state.has_unsaved_changes = False
    st.session_state.session_dir = None
    st.session_state.files_created = False
    st.session_state.selected_template = st.session_state.template_manager.get_default_template()["id"]

db = st.session_state.db
template_manager = st.session_state.template_manager

# Функция для добавления уведомлений
def add_notification(message, type="info"):
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []
    
    st.session_state.notifications.append({
        "message": message,
        "type": type,
        "time": datetime.now().strftime("%H:%M:%S")
    })
    
    if len(st.session_state.notifications) > 10:
        st.session_state.notifications.pop(0)

# Настройка страницы
st.set_page_config(
    page_title="База разделов документов",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Главный заголовок
st.title("📚 БАЗА РАЗДЕЛОВ ДОКУМЕНТОВ")
st.markdown("---")

# Используем вкладки
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Выбор разделов",
    "🎯 Выбор шаблона", 
    "⚙️ Настройки",
    "🛠️ Администрирование"
])

# ==============================================
# ВКЛАДКА 1: ВЫБОР РАЗДЕЛОВ (компактный интерфейс)
# ==============================================

with tab1:
    st.subheader("📋 ВЫБОР РАЗДЕЛОВ ДЛЯ ЭКСПЕРТНОГО ОТВЕТА")
    
    # Получаем данные для отображения
    display_data = db.get_sections_for_display()
    
    if not display_data:
        st.info("База пуста. Нажмите 'Сканировать папки' в боковой панели.")
    else:
        # Компактная панель фильтров
        with st.container():
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Фильтр по папке
                folder_options = list(set(item["folder"] for item in display_data))
                folder_filter = st.multiselect(
                    "Папка:",
                    options=folder_options,
                    default=folder_options,
                    format_func=lambda x: {
                        "normative": "📖 Нормативные",
                        "methodology": "📚 Методические",
                        "structured": "🗂️ Структурированные",
                        "expertise": "👨‍⚖️ Экспертные"
                    }.get(x, x)
                )
            
            with col2:
                # Фильтр по типу
                type_options = list(set(item["type"] for item in display_data))
                type_filter = st.multiselect(
                    "Тип раздела:",
                    options=type_options,
                    default=type_options
                )
            
            with col3:
                # Поиск по тексту
                search_text = st.text_input("Поиск:", placeholder="По документу или разделу...")
        
        # Фильтрация данных
        filtered_data = display_data.copy()
        
        if folder_filter:
            filtered_data = [item for item in filtered_data if item["folder"] in folder_filter]
        
        if type_filter:
            filtered_data = [item for item in filtered_data if item["type"] in type_filter]
        
        if search_text:
            search_lower = search_text.lower()
            filtered_data = [
                item for item in filtered_data
                if (search_lower in item["document_full"].lower() or
                    search_lower in item["section_full"].lower())
            ]
        
        # Создаем хэш текущих фильтров
        current_filter_hash = f"{folder_filter}_{type_filter}_{search_text}"
        
        # Обновляем хэш фильтров
        if st.session_state.current_filter_hash != current_filter_hash:
            st.session_state.current_filter_hash = current_filter_hash
        
        # Компактная статистика и действия
        with st.container():
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            
            with col_stat1:
                st.metric("Найдено", len(filtered_data), delta=f"из {len(display_data)}")
            
            with col_stat2:
                selected_count = sum(1 for item in filtered_data if item["selected"])
                total_selected = sum(1 for item in display_data if item["selected"])
                st.metric("Выбрано", selected_count)
            
            with col_stat3:
                if st.button("✅ Выбрать все", use_container_width=True):
                    for item in filtered_data:
                        for section in db.sections:
                            if section.get("id") == item["id"]:
                                section["selected"] = True
                    st.session_state.has_unsaved_changes = True
                    st.success(f"Выбрано {len(filtered_data)}")
                    st.rerun()
            
            with col_stat4:
                if st.button("❌ Снять все", use_container_width=True):
                    for item in filtered_data:
                        for section in db.sections:
                            if section.get("id") == item["id"]:
                                section["selected"] = False
                    st.session_state.has_unsaved_changes = True
                    st.info(f"Снято {len(filtered_data)}")
                    st.rerun()
        
        # ОТОБРАЖЕНИЕ РАЗДЕЛОВ В КОМПАКТНОМ ФОРМАТЕ
        if filtered_data:
            changes_made = False
            
            # Компактный контейнер для разделов
            with st.container():
                for idx, item in enumerate(filtered_data):
                    # Определяем CSS классы
                    css_class = "section-item"
                    if item["selected"]:
                        css_class += " selected-section"
                    
                    # Создаем компактный раздел
                    col_check, col_content = st.columns([0.4, 11.6])
                    
                    with col_check:
                        # Чекбокс для выбора (компактный)
                        current_selected = item["selected"]
                        new_selected = st.checkbox(
                            "",
                            value=current_selected,
                            key=f"select_{item['id']}_{current_filter_hash}",
                            label_visibility="collapsed"
                        )
                        
                        # Обновляем если изменилось
                        if new_selected != current_selected:
                            for section in db.sections:
                                if section.get("id") == item["id"]:
                                    section["selected"] = new_selected
                                    changes_made = True
                                    break
                    
                    with col_content:
                        # Компактное отображение информации
                        st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
                        
                        # Документ (жирный шрифт с хорошей видимостью в темной теме)
                        folder_icon = {
                            "normative": "📖",
                            "methodology": "📚",
                            "structured": "🗂️",
                            "expertise": "👨‍⚖️"
                        }.get(item["folder"], "📄")
                        
                        # Используем span с важными стилями для темной темы
                        st.markdown(
                            f'<div class="section-header">'
                            f'<span style="font-weight: 600; color: inherit;">{folder_icon} {item["document"]}</span>'
                            f'</div>', 
                            unsafe_allow_html=True
                        )
                        
                        # Метаданные в одной строке
                        meta_info = []
                        meta_info.append(f"Тип: {item['type']}")
                        meta_info.append(f"Формат: {item.get('extension', '.txt')}")
                        meta_info.append(f"Слов: {item['words']}")
                        if item["selected"]:
                            meta_info.append("✅ Выбрано")
                        
                        st.markdown(f'<div class="section-meta">{" • ".join(meta_info)}</div>', 
                                unsafe_allow_html=True)
                        
                        # Название раздела с хорошей видимостью
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
            
            # Компактная панель управления
            st.markdown("---")
            
            with st.container():
                col_manage1, col_manage2, col_manage3 = st.columns(3)
                
                with col_manage1:
                    # Кнопка сохранения
                    save_disabled = not st.session_state.has_unsaved_changes
                    
                    if st.button("💾 Сохранить выбор", type="primary", 
                               disabled=save_disabled, use_container_width=True):
                        db.save_database()
                        st.success("✅ Выбор сохранен!")
                        add_notification("Выбор разделов сохранен", "success")
                        st.session_state.has_unsaved_changes = False
                        st.rerun()
                
                with col_manage2:
                    # Кнопка создания файлов для DeepSeek
                    total_selected = sum(1 for item in display_data if item["selected"])
                    create_disabled = total_selected == 0
                    
                    if st.button("🤖 Создать файлы", type="secondary",
                               disabled=create_disabled, use_container_width=True):
                        selected_sections = db.get_selected_sections()
                        
                        with st.spinner("Создаю файлы..."):
                            output_dir = Path(CONFIG.get("expert_sessions_path", "./expert_sessions"))
                            output_dir.mkdir(exist_ok=True, parents=True)
                            
                            session_dir = ExpertFileGenerator.create_prompt_file(
                                selected_sections, 
                                output_dir,
                                template_manager,
                                st.session_state.selected_template
                            )
                            
                            if session_dir:
                                st.session_state.session_dir = session_dir
                                st.session_state.files_created = True
                                
                                st.success(f"✅ Файлы созданы!")
                                add_notification("Файлы сессии созданы", "success")
                                st.rerun()
                
                with col_manage3:
                    # Статус
                    if st.session_state.has_unsaved_changes:
                        st.warning("⚠️ Не сохранено")
                    else:
                        st.info("💾 Все сохранено")
        
        else:
            st.info("Нет разделов, соответствующих выбранным фильтрам.")

# ==============================================
# ВКЛАДКА 2: ВЫБОР ШАБЛОНА
# ==============================================

with tab2:
    st.subheader("🎯 ВЫБОР ШАБЛОНА ДЛЯ ИИ")
    
    templates = template_manager.get_templates_list()
    
    if not templates:
        st.info("Нет доступных шаблонов. Создайте первый шаблон.")
    else:
        # Отображаем текущий выбранный шаблон
        current_template = template_manager.get_template_by_id(st.session_state.selected_template)
        if current_template:
            st.markdown(f"### 📌 ТЕКУЩИЙ ШАБЛОН: **{current_template.get('name', 'Неизвестно')}**")
            st.markdown(f"*{current_template.get('description', '')}*")
            st.markdown("---")
        
        # Выбор шаблона
        st.markdown("### 📋 ВЫБЕРИТЕ ШАБЛОН ОТВЕТА:")
        
        for template in templates:
            is_selected = template["id"] == st.session_state.selected_template
            
            # Создаем карточку шаблона
            css_class = "template-card"
            if is_selected:
                css_class += " selected"
            
            with st.container():
                col1, col2 = st.columns([0.1, 0.9])
                
                with col1:
                    # Радио-кнопка для выбора
                    if st.button("✓", key=f"select_template_{template['id']}", 
                               disabled=is_selected, use_container_width=True):
                        st.session_state.selected_template = template["id"]
                        st.success(f"Выбран шаблон: {template['name']}")
                        add_notification(f"Выбран шаблон: {template['name']}", "info")
                        st.rerun()
                
                with col2:
                    st.markdown(f'<div class="{css_class}" onclick="document.getElementById(\'template_{template["id"]}\').click()">', 
                              unsafe_allow_html=True)
                    st.markdown(f'<div class="template-name">{template.get("name", "Без названия")}</div>', 
                              unsafe_allow_html=True)
                    st.markdown(f'<div class="template-description">{template.get("description", "")}</div>', 
                              unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
        
        # Предпросмотр выбранного шаблона
        st.markdown("---")
        st.markdown("### 👁️ ПРЕДПРОСМОТР ШАБЛОНА")
        
        if current_template:
            with st.expander("📝 Показать текст шаблона"):
                st.text_area("Текст шаблона:", 
                           value=current_template.get("prompt", ""),
                           height=300,
                           disabled=True,
                           key=f"preview_{current_template['id']}")
        
        # Отображение кнопок для скачивания файлов
        if st.session_state.files_created and st.session_state.session_dir:
            st.markdown("---")
            st.markdown("##### 📥 СКАЧАТЬ ФАЙЛЫ СЕССИИ")
            
            session_dir = st.session_state.session_dir
            
            # Компактное отображение кнопок скачивания
            col_download1, col_download2, col_download3, col_download4, col_download5 = st.columns(5)
            
            # Файл all_sections.md
            all_sections_path = session_dir / "all_sections.md"
            if all_sections_path.exists():
                with col_download1:
                    with open(all_sections_path, 'r', encoding='utf-8') as f:
                        all_sections_content = f.read()
                    
                    st.download_button(
                        label="📄 Разделы",
                        data=all_sections_content,
                        file_name=f"all_sections.md",
                        mime="text/markdown",
                        use_container_width=True,
                        help="Все выбранные разделы"
                    )
            
            # Файл deepseek_prompt.txt
            prompt_path = session_dir / "deepseek_prompt.txt"
            if prompt_path.exists():
                with col_download2:
                    with open(prompt_path, 'r', encoding='utf-8') as f:
                        prompt_content = f.read()
                    
                    st.download_button(
                        label="🤖 Промт",
                        data=prompt_content,
                        file_name=f"deepseek_prompt.txt",
                        mime="text/plain",
                        use_container_width=True,
                        help="Промт для DeepSeek"
                    )
            
            # Файл report.txt
            report_path = session_dir / "report.txt"
            if report_path.exists():
                with col_download3:
                    with open(report_path, 'r', encoding='utf-8') as f:
                        report_content = f.read()
                    
                    st.download_button(
                        label="📊 Отчет",
                        data=report_content,
                        file_name=f"report.txt",
                        mime="text/plain",
                        use_container_width=True,
                        help="Отчет по сессии"
                    )
            
            # Файл sections_data.json
            json_path = session_dir / "sections_data.json"
            if json_path.exists():
                with col_download4:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        json_content = f.read()
                    
                    st.download_button(
                        label="📁 JSON",
                        data=json_content,
                        file_name=f"sections_data.json",
                        mime="application/json",
                        use_container_width=True,
                        help="Данные в JSON"
                    )
            
            # Файл template_info.json
            template_path = session_dir / "template_info.json"
            if template_path.exists():
                with col_download5:
                    with open(template_path, 'r', encoding='utf-8') as f:
                        template_content = f.read()
                    
                    st.download_button(
                        label="🎯 Шаблон",
                        data=template_content,
                        file_name=f"template_info.json",
                        mime="application/json",
                        use_container_width=True,
                        help="Информация о шаблоне"
                    )

# ==============================================
# ВКЛАДКА 3: НАСТРОЙКИ
# ==============================================

with tab3:
    st.subheader("⚙️ НАСТРОЙКИ")
    
    st.markdown("### 📂 КОНФИГУРАЦИЯ ПУТЕЙ")
    
    # Отображаем текущую конфигурацию
    for folder_name, folder_path in CONFIG["folders"].items():
        display_name = {
            "normative": "📖 Нормативные акты",
            "methodology": "📚 Методические материалы",
            "structured": "🗂️ Структурированные документы",
            "expertise": "👨‍⚖️ Экспертные заключения"
        }.get(folder_name, folder_name)
        
        st.text_input(
            f"{display_name}:",
            value=folder_path,
            key=f"config_path_{folder_name}",
            disabled=True
        )
    
    st.markdown("---")
    
    # Проверка доступности папок
    if st.button("🔍 Проверить доступность папок", type="secondary"):
        status = validate_folders(CONFIG["folders"])
        
        if status["all_exist"]:
            st.success("✅ Все папки доступны!")
        else:
            st.error("❌ Некоторые папки недоступны:")
            for folder_type, path in status["missing"]:
                st.error(f"   - {folder_type}: {path}")
            
            st.info("ℹ️ Отредактируйте файл `config.json` и перезапустите приложение")
    
    st.markdown("---")
    st.markdown("### 📝 РЕДАКТИРОВАНИЕ КОНФИГУРАЦИИ")
    
    # Показываем текущий config.json
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_content = f.read()
            
            st.download_button(
                label="⬇️ Скачать текущий config.json",
                data=config_content,
                file_name="config.json",
                mime="application/json",
                use_container_width=True,
                help="Скачайте, отредактируйте и перезапустите приложение"
            )
            
            with st.expander("👁️ Показать текущий config.json"):
                st.code(config_content, language="json")
        
        except Exception as e:
            st.error(f"Ошибка чтения файла конфигурации: {e}")
    else:
        st.info("Файл config.json не найден. Используются настройки по умолчанию.")
        
        # Кнопка для создания config.json с текущими настройками
        if st.button("📄 Создать config.json", type="primary"):
            if save_config(CONFIG):
                st.success("Файл config.json создан! Перезапустите приложение.")
                add_notification("Файл конфигурации создан", "success")
            else:
                st.error("Не удалось создать файл конфигурации")

# ==============================================
# ВКЛАДКА 4: АДМИНИСТРИРОВАНИЕ
# ==============================================

with tab4:
    st.subheader("🛠️ АДМИНИСТРИРОВАНИЕ")
    
    col_admin1, col_admin2 = st.columns(2)
    
    with col_admin1:
        # Блок операций с базой
        st.markdown("### 🗑️ ОПЕРАЦИИ С БАЗОЙ")
        
        # Кнопка сканирования
        if st.button("🔍 Сканировать папки", type="primary", use_container_width=True):
            with st.spinner("Сканирую папки..."):
                db.scan_and_build_database()
                st.success("✅ База данных обновлена!")
                add_notification("База данных отсканирована и обновлена", "success")
                st.session_state.has_unsaved_changes = False
                st.rerun()
        
        # Кнопка очистки базы
        if st.button("🗑️ Очистить базу", type="secondary", use_container_width=True):
            st.warning("Это действие очистит всю базу данных!")
            if st.checkbox("Я понимаю последствия"):
                db.sections = []
                db.metadata = {
                    "created_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "total_sections": 0,
                    "total_documents": 0,
                    "by_folder": {},
                    "supported_extensions": SUPPORTED_EXTENSIONS
                }
                db.save_database()
                st.success("База очищена!")
                st.session_state.has_unsaved_changes = False
                st.rerun()
    
    with col_admin2:
        # Блок импорта/экспорта
        st.markdown("### 📤 ИМПОРТ/ЭКСПОРТ")
        
        # Импорт
        uploaded_file = st.file_uploader(
            "Выберите файл базы (JSON):",
            type=['json'],
            key="import_uploader"
        )
        
        if uploaded_file is not None:
            try:
                import_data = json.load(uploaded_file)
                if st.button("📥 Импортировать данные", type="primary"):
                    if 'sections' in import_data and 'metadata' in import_data:
                        db.sections = import_data['sections']
                        db.metadata = import_data['metadata']
                        db.save_database()
                        st.success("База успешно импортирована!")
                        add_notification(f"База импортирована из {uploaded_file.name}", "success")
                        st.session_state.has_unsaved_changes = False
                        st.rerun()
                    else:
                        st.error("Неверный формат файла базы")
            except Exception as e:
                st.error(f"Ошибка при чтении файла: {e}")
        
        # Экспорт
        if st.button("📤 Экспортировать базу", type="secondary", use_container_width=True):
            export_data = {
                "sections": db.sections,
                "metadata": db.metadata
            }
            
            export_json = json.dumps(export_data, ensure_ascii=False, indent=2)
            
            st.download_button(
                label="⬇️ Скачать базу (JSON)",
                data=export_json,
                file_name=f"database_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
    
    # Управление шаблонами
    st.markdown("---")
    st.markdown("### 🎯 УПРАВЛЕНИЕ ШАБЛОНАМИ")
    
    col_template1, col_template2 = st.columns(2)
    
    with col_template1:
        # Просмотр и редактирование шаблонов
        st.markdown("##### 📝 РЕДАКТИРОВАТЬ ШАБЛОНЫ")
        
        templates = template_manager.get_templates_list()
        
        for template in templates:
            with st.expander(f"✏️ {template.get('name', 'Без названия')}", expanded=False):
                new_name = st.text_input("Название:", 
                                       value=template.get('name', ''),
                                       key=f"name_{template['id']}")
                
                new_description = st.text_area("Описание:",
                                             value=template.get('description', ''),
                                             key=f"desc_{template['id']}")
                
                new_prompt = st.text_area("Текст шаблона:",
                                        value=template.get('prompt', ''),
                                        height=200,
                                        key=f"prompt_{template['id']}")
                
                if st.button("💾 Сохранить изменения", key=f"save_{template['id']}"):
                    # Обновляем шаблон
                    template['name'] = new_name
                    template['description'] = new_description
                    template['prompt'] = new_prompt
                    
                    # Сохраняем изменения
                    template_manager.update_templates(template_manager.templates)
                    st.success(f"Шаблон '{new_name}' обновлен!")
                    add_notification(f"Шаблон '{new_name}' обновлен", "success")
                    st.rerun()
    
    with col_template2:
        # Создание нового шаблона
        st.markdown("##### ➕ СОЗДАТЬ НОВЫЙ ШАБЛОН")
        
        with st.form("new_template_form"):
            new_template_name = st.text_input("Название нового шаблона:", 
                                            placeholder="Например: Технический анализ")
            
            new_template_desc = st.text_area("Описание шаблона:",
                                           placeholder="Краткое описание цели шаблона")
            
            new_template_prompt = st.text_area("Текст шаблона:",
                                             placeholder="Введите текст промта для ИИ...",
                                             height=250)
            
            submit_btn = st.form_submit_button("➕ Создать шаблон", type="primary")
        
        # Обработка формы вынесена ВНЕ формы
        if submit_btn:
            if new_template_name and new_template_prompt:
                # Создаем новый шаблон
                new_template = {
                    "id": f"template_{uuid.uuid4().hex[:8]}",
                    "name": new_template_name,
                    "description": new_template_desc,
                    "prompt": new_template_prompt
                }
                
                # Добавляем в список шаблонов
                templates = template_manager.get_templates_list()
                templates.append(new_template)
                
                # Обновляем шаблоны
                template_manager.templates["templates"] = templates
                template_manager.update_templates(template_manager.templates)
                
                st.success(f"Шаблон '{new_template_name}' создан!")
                add_notification(f"Создан новый шаблон: {new_template_name}", "success")
                st.rerun()
            else:
                st.error("Заполните название и текст шаблона")
    
    # Перезагрузка шаблонов - ВНЕ формы, отдельный блок
    st.markdown("---")
    st.markdown("### 🔄 ПЕРЕЗАГРУЗКА ШАБЛОНОВ")
    
    if st.button("🔄 Перезагрузить шаблоны из файла", type="secondary", use_container_width=True):
        template_manager.reload_templates()
        st.success("Шаблоны перезагружены из файла!")
        add_notification("Шаблоны перезагружены из файла", "success")
        st.rerun()

# ==============================================
# САЙДБАР
# ==============================================

with st.sidebar:
    st.header("📊 СТАТИСТИКА")
    
    # Основная статистика
    st.metric("Всего разделов", db.metadata.get("total_sections", 0))
    st.metric("Всего документов", db.metadata.get("total_documents", 0))
    
    # Подсчет выбранных
    selected_count = sum(1 for section in db.sections if section.get("selected", False))
    st.metric("Выбрано разделов", selected_count)
    
    # Информация о выбранном шаблоне
    current_template = template_manager.get_template_by_id(st.session_state.selected_template)
    if current_template:
        st.markdown("---")
        st.header("🎯 ШАБЛОН")
        st.markdown(f"**{current_template.get('name', 'Неизвестно')}**")
        st.caption(current_template.get('description', ''))
    
    if db.metadata.get("last_updated"):
        st.caption(f"Обновлено: {db.metadata['last_updated'][:10]}")
    
    st.markdown("---")
    st.header("⚡ БЫСТРЫЕ ДЕЙСТВИЯ")
    
    # Кнопка сохранения если есть изменения
    if st.session_state.has_unsaved_changes:
        if st.button("💾 Сохранить выбор", type="primary", use_container_width=True):
            db.save_database()
            st.success("Сохранено!")
            st.session_state.has_unsaved_changes = False
            st.rerun()
    
    # Кнопка создания промта
    if selected_count > 0:
        if st.button("🤖 Создать файлы сессии", type="secondary", use_container_width=True):
            # Устанавливаем флаг, чтобы показать кнопки скачивания
            selected_sections = db.get_selected_sections()
            with st.spinner("Создаю файлы..."):
                output_dir = Path(CONFIG.get("expert_sessions_path", "./expert_sessions"))
                output_dir.mkdir(exist_ok=True, parents=True)
                session_dir = ExpertFileGenerator.create_prompt_file(
                    selected_sections, 
                    output_dir,
                    template_manager,
                    st.session_state.selected_template
                )
                if session_dir:
                    st.session_state.session_dir = session_dir
                    st.session_state.files_created = True
                    st.success("Файлы созданы!")
                    add_notification("Файлы сессии созданы", "success")
                    st.rerun()
    else:
        st.caption("Выберите разделы для создания файлов")
    
    st.markdown("---")
    st.header("🔔 УВЕДОМЛЕНИЯ")
    
    if 'notifications' in st.session_state and st.session_state.notifications:
        for notification in reversed(st.session_state.notifications[-3:]):
            icon = {
                "info": "ℹ️",
                "success": "✅",
                "warning": "⚠️",
                "error": "❌"
            }.get(notification["type"], "ℹ️")
            
            st.caption(f"{icon} {notification['time']}: {notification['message']}")
        
        if st.button("Очистить уведомления", use_container_width=True):
            st.session_state.notifications = []
            st.rerun()
    else:
        st.caption("Нет уведомлений")