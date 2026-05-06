import json
import os
from typing import List, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AutoDeliveryManager:
    def __init__(self, json_file: str = "autodelivery_items.json"):
        self.json_file = json_file
        self.items = self.load_items()
    
    def load_items(self) -> List[Dict]:
        """Загрузка товаров из JSON"""
        if os.path.exists(self.json_file):
            try:
                with open(self.json_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Ошибка загрузки: {e}")
                return []
        return []
    
    def save_items(self):
        """Сохранение товаров в JSON"""
        try:
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(self.items, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
    
    def add_item(self, title: str, price: float, stock: int, delivery_text: str) -> bool:
        """Добавление товара"""
        new_item = {
            'id': len(self.items) + 1,
            'title': title,
            'price': price,
            'stock': stock,
            'delivery_text': delivery_text,
            'created_at': datetime.now().isoformat()
        }
        self.items.append(new_item)
        self.save_items()
        return True
    
    def remove_item(self, item_id: int) -> bool:
        """Удаление товара"""
        self.items = [item for item in self.items if item.get('id') != item_id]
        self.save_items()
        return True
    
    def update_stock(self, item_id: int, new_stock: int) -> bool:
        """Обновление количества товара"""
        for item in self.items:
            if item.get('id') == item_id:
                item['stock'] = new_stock
                self.save_items()
                return True
        return False
    
    def get_all_items(self) -> List[Dict]:
        """Получение всех товаров"""
        return self.items
    
    def get_item_by_id(self, item_id: int) -> Dict:
        """Получение товара по ID"""
        for item in self.items:
            if item.get('id') == item_id:
                return item
        return None