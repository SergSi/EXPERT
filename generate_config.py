#!/usr/bin/env python3
"""
generate_config_json.py - создание extract_config.json
"""

import json
import re
from pathlib import Path

def generate_json_config(normative_dir: str, output_file: str = "extract_config.json"):
    """Генерирует конфигурацию в JSON формате"""
    
    norm_path = Path(normative_dir)
    
    if not norm_path.exists():
        print(f"❌ Папка {normative_dir} не найдена")
        return
    
    txt_files = list(norm_path.glob("*.txt"))
    
    config = {"laws": {}}
    
    for file_path in txt_files:
        law_name = file_path.stem
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Убираем YAML заголовок если есть
        if content.startswith('---'):
            parts = content.split('---', 2)
            content = parts[2] if len(parts) >= 3 else content
        
        # Ищем все статьи
        pattern = re.compile(r'^Статья\s+(\d+(?:\.\d+)?(?:-[\d\.]+)?)\.', re.MULTILINE)
        articles = list(set(pattern.findall(content)))
        
        # Сортируем
        def sort_key(x):
            try:
                return float(x.split('-')[0])
            except:
                return 0
        
        articles.sort(key=sort_key)
        
        config["laws"][law_name] = {
            "title": f"Федеральный закон {law_name}",
            "split_by": "articles",
            "extract": articles
        }
        
        print(f"✅ {law_name}: {len(articles)} статей")
    
    output_path = norm_path / output_file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Сохранено в {output_path}")

if __name__ == "__main__":
    generate_json_config("NORMATIVE")