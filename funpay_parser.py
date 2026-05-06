import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from typing import List, Dict
import logging
import json
import time

logger = logging.getLogger(__name__)

class FunpayParser:
    def __init__(self, golden_key: str = None):
        self.session = requests.Session()
        self.ua = UserAgent()
        self.golden_key = golden_key
        
        # Если есть Golden Key, добавляем его в заголовки
        if golden_key:
            self.session.headers.update({'Cookie': f'golden_key={golden_key}'})
    
    def _get_headers(self) -> Dict:
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Referer': 'https://funpay.com/',
        }
    
    def get_active_sales(self, category_id: int = None) -> List[Dict]:
        """Получение активных продаж (публичные данные)"""
        try:
            if category_id:
                url = f"https://funpay.com/ru/chats/{category_id}/"
            else:
                url = "https://funpay.com/ru/sell/"
            
            response = self.session.get(url, headers=self._get_headers(), timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            sales = []
            items = soup.find_all('div', class_='tc-item')[:self.max_items]
            
            for item in items:
                try:
                    title_elem = item.find('div', class_='tc-title')
                    price_elem = item.find('div', class_='tc-price')
                    seller_elem = item.find('div', class_='tc-seller')
                    
                    if title_elem and price_elem:
                        sale = {
                            'title': title_elem.get_text(strip=True),
                            'price': price_elem.get_text(strip=True),
                            'seller': seller_elem.get_text(strip=True) if seller_elem else 'Неизвестен',
                            'url': url
                        }
                        sales.append(sale)
                except Exception:
                    continue
            
            return sales
        except Exception as e:
            logger.error(f"Ошибка получения продаж: {e}")
            return []
    
    def search_products(self, query: str) -> List[Dict]:
        """Поиск товаров"""
        try:
            search_url = f"https://funpay.com/ru/search/?query={query}"
            response = self.session.get(search_url, headers=self._get_headers(), timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            products = []
            items = soup.find_all('div', class_='product-item')[:10]
            
            for item in items:
                try:
                    name_elem = item.find('div', class_='product-name')
                    price_elem = item.find('div', class_='product-price')
                    
                    if name_elem and price_elem:
                        product = {
                            'name': name_elem.get_text(strip=True),
                            'price': price_elem.get_text(strip=True),
                        }
                        products.append(product)
                except Exception:
                    continue
            
            return products
        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
            return []

    max_items = 10