import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime

from FunPayAPI import Account, Runner, types, enums

logger = logging.getLogger(__name__)

class FunpayManager:
    def __init__(self, golden_key: str):
        self.golden_key = golden_key
        self.account = None
        self.runner = None
        self.is_running = False
        self.message_handlers = []
        self.order_handlers = []
        
    def init(self) -> bool:
        """Инициализация аккаунта Funpay"""
        try:
            self.account = Account(self.golden_key).get()
            self.runner = Runner(self.account)
            logger.info(f"✅ Авторизован на Funpay как {self.account.username} (ID: {self.account.id})")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка авторизации Funpay: {e}")
            return False
    
    def search_users(self, query: str) -> List[Dict]:
        """Поиск пользователей на Funpay"""
        try:
            # Поиск через runner или прямые запросы
            results = []
            
            # Получаем список чатов
            chats = self.account.get_chats()
            
            for chat in chats:
                if query.lower() in chat.name.lower():
                    results.append({
                        'id': chat.id,
                        'name': chat.name,
                        'username': chat.name,
                        'last_message': chat.last_message.text if chat.last_message else None,
                        'url': f"https://funpay.com/ru/chat/{chat.id}/"
                    })
            
            return results[:20]  # Ограничиваем 20 результатами
        except Exception as e:
            logger.error(f"Ошибка поиска пользователей: {e}")
            return []
    
    def search_chats_by_keyword(self, keyword: str) -> List[Dict]:
        """Поиск чатов по ключевому слову в сообщениях"""
        try:
            results = []
            chats = self.account.get_chats()
            
            for chat in chats:
                # Получаем историю сообщений
                history = self.account.get_chat_history(chat.id)
                
                for msg in history:
                    if keyword.lower() in msg.text.lower():
                        results.append({
                            'chat_id': chat.id,
                            'user_name': chat.name,
                            'found_message': msg.text[:100],
                            'message_date': msg.date
                        })
                        break
            
            return results[:10]
        except Exception as e:
            logger.error(f"Ошибка поиска по чатам: {e}")
            return []
    
    def get_chat_by_username(self, username: str) -> Optional[Dict]:
        """Получение чата по имени пользователя"""
        try:
            chat = self.account.get_chat_by_name(username, True)
            if chat:
                return {
                    'id': chat.id,
                    'name': chat.name,
                    'messages': [
                        {'author': msg.author, 'text': msg.text, 'date': msg.date}
                        for msg in chat.messages[-10:]  # Последние 10 сообщений
                    ]
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка получения чата: {e}")
            return None
    
    def send_message(self, chat_id: int, message: str) -> bool:
        """Отправка сообщения в чат"""
        try:
            self.account.send_message(chat_id, message)
            logger.info(f"Сообщение отправлено в чат {chat_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
            return False
    
    def get_new_orders(self) -> List[Dict]:
        """Получение новых заказов"""
        try:
            orders = self.account.get_new_orders()
            result = []
            
            for order in orders:
                result.append({
                    'id': order.id,
                    'description': order.description,
                    'price': order.price,
                    'buyer_username': order.buyer_username,
                    'buyer_id': order.buyer_id,
                    'status': order.status,
                    'created_at': order.created_at
                })
            
            return result
        except Exception as e:
            logger.error(f"Ошибка получения заказов: {e}")
            return []
    
    def send_product_delivery(self, order_id: str, delivery_text: str) -> bool:
        """Отправка товара по заказу"""
        try:
            # Получаем информацию о заказе
            order = self.account.get_order(order_id)
            if order:
                # Отправляем данные для доступа
                chat_id = order.chat_id
                self.account.send_message(
                    chat_id,
                    f"✅ **Ваш заказ #{order_id}**\n\n"
                    f"📦 Данные для доступа:\n{delivery_text}\n\n"
                    f"Спасибо за покупку! 🎉"
                )
                
                # Отмечаем заказ как выполненный
                self.account.complete_order(order_id)
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка выдачи товара: {e}")
            return False
    
    def get_chats_list(self) -> List[Dict]:
        """Получение списка всех чатов"""
        try:
            chats = self.account.get_chats()
            result = []
            
            for chat in chats:
                result.append({
                    'id': chat.id,
                    'name': chat.name,
                    'last_message': chat.last_message.text[:50] if chat.last_message else 'Нет сообщений',
                    'unread': chat.unread_count if hasattr(chat, 'unread_count') else 0,
                    'url': f"https://funpay.com/ru/chat/{chat.id}/"
                })
            
            return result
        except Exception as e:
            logger.error(f"Ошибка получения списка чатов: {e}")
            return []
    
    def start_listener(self, on_new_message=None, on_new_order=None):
        """Запуск прослушивателя событий"""
        if not self.runner:
            return
        
        self.is_running = True
        
        async def listen():
            for event in self.runner.listen(requests_delay=4):
                if not self.is_running:
                    break
                
                # Новое сообщение
                if event.type is enums.EventTypes.NEW_MESSAGE:
                    if event.message.author_id != self.account.id and on_new_message:
                        asyncio.create_task(on_new_message(event.message))
                
                # Новый заказ
                elif event.type is enums.EventTypes.NEW_ORDER:
                    if on_new_order:
                        asyncio.create_task(on_new_order(event.order))
                
                # Новый отзыв
                elif event.type is enums.EventTypes.NEW_FEEDBACK:
                    logger.info(f"Новый отзыв от {event.feedback.author}")
        
        asyncio.create_task(listen())
    
    def stop_listener(self):
        """Остановка прослушивателя"""
        self.is_running = False

# Глобальный экземпляр
funpay_manager = None