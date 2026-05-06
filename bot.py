# Добавьте в начало файла после импортов
from funpay_manager import FunpayManager, funpay_manager

# Инициализация Funpay менеджера (при наличии Golden Key)
if GOLDEN_KEY:
    funpay_manager = FunpayManager(GOLDEN_KEY)
    if funpay_manager.init():
        logger.info("✅ Funpay менеджер инициализирован")
        
        # Запускаем слушатель событий
        funpay_manager.start_listener(
            on_new_message=handle_funpay_message,
            on_new_order=handle_funpay_order
        )
    else:
        logger.error("❌ Не удалось инициализировать Funpay менеджер")
        funpay_manager = None

# ============ ОБРАБОТЧИКИ СОБЫТИЙ FUNPAY ============

async def handle_funpay_message(message):
    """Обработка нового сообщения на Funpay"""
    try:
        # Получаем информацию о чате
        chat_info = f"👤 {message.author_name}\n🆔 ID: {message.author_id}"
        
        # Отправляем уведомление админам
        admin_text = f"""
💬 **НОВОЕ СООБЩЕНИЕ НА FUNPAY!**

{chat_info}

📝 **Текст сообщения:**
{message.text[:300]}

🔗 [Ответить в чат](https://funpay.com/ru/chat/{message.chat_id}/)
        """
        
        for admin_id in admin_manager.get_all_admins().keys():
            try:
                await bot.send_message(int(admin_id), admin_text, parse_mode="Markdown")
            except:
                pass
                
        # Автоответ (если настроен)
        auto_reply = get_auto_reply(message.text)
        if auto_reply and funpay_manager:
            funpay_manager.send_message(message.chat_id, auto_reply)
            logger.info(f"Автоответ отправлен в чат {message.chat_id}")
            
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")

async def handle_funpay_order(order):
    """Обработка нового заказа на Funpay"""
    try:
        # Ищем товар по описанию заказа
        delivery_items = delivery_manager.get_all_items()
        delivered = False
        
        for item in delivery_items:
            if item['title'].lower() in order.description.lower():
                # Автоматическая выдача товара
                success = funpay_manager.send_product_delivery(
                    order.id, 
                    item['delivery_text']
                )
                
                if success:
                    delivered = True
                    
                    # Уменьшаем количество товара
                    new_stock = item.get('stock', 0) - 1
                    if new_stock >= 0:
                        delivery_manager.update_stock(item['id'], new_stock)
                    
                    # Уведомляем админов
                    admin_text = f"""
🎉 **НОВЫЙ ЗАКАЗ АВТОМАТИЧЕСКИ ВЫДАН!**

📦 Товар: {item['title']}
👤 Покупатель: {order.buyer_username}
💰 Сумма: {order.price} ₽
📦 Осталось: {new_stock}

✅ Товар выдан автоматически!
                    """
                    
                    for admin_id in admin_manager.get_all_admins().keys():
                        try:
                            await bot.send_message(int(admin_id), admin_text, parse_mode="Markdown")
                        except:
                            pass
                    break
        
        if not delivered:
            # Уведомляем админов о новом заказе без автовыдачи
            admin_text = f"""
⚠️ **НОВЫЙ ЗАКАЗ (НЕТ АВТОВЫДАЧИ)!**

📝 Описание: {order.description[:100]}
👤 Покупатель: {order.buyer_username}
💰 Сумма: {order.price} ₽

❗ Требуется ручная выдача!

💬 Ответьте покупателю через Funpay
            """
            
            for admin_id in admin_manager.get_all_admins().keys():
                try:
                    await bot.send_message(int(admin_id), admin_text, parse_mode="Markdown")
                except:
                    pass
                    
    except Exception as e:
        logger.error(f"Ошибка обработки заказа: {e}")

# ============ НОВЫЕ ФУНКЦИИ ДЛЯ ПОИСКА И ОБЩЕНИЯ ============

@dp.message(Command("finduser"))
async def cmd_finduser(message: types.Message):
    """Поиск пользователя на Funpay"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    if not funpay_manager:
        await message.answer("❌ Golden Key не настроен! Невозможно выполнить поиск.")
        return
    
    query = message.text.replace("/finduser", "").strip()
    
    if not query:
        await message.answer("❌ Укажите имя пользователя для поиска\nПример: `/finduser JohnDoe`", parse_mode="Markdown")
        return
    
    status_msg = await message.answer(f"🔍 Ищу пользователя *{query}*...", parse_mode="Markdown")
    
    users = funpay_manager.search_users(query)
    
    if not users:
        await status_msg.edit_text(f"❌ Пользователь *{query}* не найден", parse_mode="Markdown")
        return
    
    response = f"👥 **Результаты поиска:** *{query}*\n\n"
    for i, user in enumerate(users[:10], 1):
        response += f"{i}. **{user['name']}**\n"
        response += f"   🆔 ID: `{user['id']}`\n"
        if user.get('last_message'):
            response += f"   💬 Последнее сообщение: *{user['last_message'][:50]}*\n"
        response += f"   🔗 [Открыть чат]({user['url']})\n\n"
    
    await status_msg.edit_text(response, parse_mode="Markdown")

@dp.message(Command("chats"))
async def cmd_chats(message: types.Message):
    """Список всех чатов на Funpay"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    if not funpay_manager:
        await message.answer("❌ Golden Key не настроен!")
        return
    
    status_msg = await message.answer("📋 Загружаю список чатов...")
    
    chats = funpay_manager.get_chats_list()
    
    if not chats:
        await status_msg.edit_text("❌ Нет активных чатов")
        return
    
    response = "💬 **Список чатов на Funpay:**\n\n"
    for chat in chats[:20]:
        response += f"👤 **{chat['name']}**\n"
        response += f"   🆔 ID: `{chat['id']}`\n"
        if chat.get('unread', 0) > 0:
            response += f"   🔴 Непрочитанных: {chat['unread']}\n"
        response += f"   💬 {chat['last_message'][:40]}...\n"
        response += f"   🔗 [Перейти]({chat['url']})\n\n"
    
    await status_msg.edit_text(response, parse_mode="Markdown")

@dp.message(Command("sendfp"))
async def cmd_sendfp(message: types.Message):
    """Отправка сообщения на Funpay"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    if not funpay_manager:
        await message.answer("❌ Golden Key не настроен!")
        return
    
    args = message.text.replace("/sendfp", "").strip().split(maxsplit=1)
    
    if len(args) < 2:
        await message.answer("❌ Использование: `/sendfp [user_id или username] [текст]`\n\n"
                            "Пример 1 (по ID): `/sendfp 123456789 Привет!`\n"
                            "Пример 2 (по имени): `/sendfp JohnDoe Привет!`", 
                            parse_mode="Markdown")
        return
    
    identifier = args[0]
    text = args[1]
    
    # Определяем, ID это или имя
    if identifier.isdigit():
        chat_id = int(identifier)
    else:
        # Ищем пользователя по имени
        user = funpay_manager.get_chat_by_username(identifier)
        if not user:
            await message.answer(f"❌ Пользователь *{identifier}* не найден", parse_mode="Markdown")
            return
        chat_id = user['id']
    
    # Отправляем сообщение
    success = funpay_manager.send_message(chat_id, text)
    
    if success:
        await message.answer(f"✅ Сообщение отправлено пользователю `{identifier}`", parse_mode="Markdown")
        
        # Сохраняем в историю
        log_message(message.from_user.id, identifier, text, "outgoing")
    else:
        await message.answer(f"❌ Ошибка отправки сообщения пользователю `{identifier}`", parse_mode="Markdown")

@dp.message(Command("orders"))
async def cmd_orders(message: types.Message):
    """Просмотр новых заказов"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    if not funpay_manager:
        await message.answer("❌ Golden Key не настроен!")
        return
    
    status_msg = await message.answer("📋 Загружаю новые заказы...")
    
    orders = funpay_manager.get_new_orders()
    
    if not orders:
        await status_msg.edit_text("📭 Нет новых заказов")
        return
    
    response = "🛒 **Новые заказы:**\n\n"
    for order in orders[:10]:
        response += f"🆔 **Заказ #{order['id']}**\n"
        response += f"📝 {order['description'][:100]}\n"
        response += f"👤 Покупатель: {order['buyer_username']}\n"
        response += f"💰 {order['price']} ₽\n"
        response += f"📅 {order['created_at']}\n"
        response += f"🔗 [Ответить](https://funpay.com/ru/chat/user/{order['buyer_id']}/)\n\n"
    
    await status_msg.edit_text(response, parse_mode="Markdown")

@dp.message(Command("delivery"))
async def cmd_delivery(message: types.Message):
    """Ручная выдача товара по заказу"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    if not funpay_manager:
        await message.answer("❌ Golden Key не настроен!")
        return
    
    args = message.text.replace("/delivery", "").strip().split()
    
    if len(args) < 2:
        await message.answer("❌ Использование: `/delivery [order_id] [product_id]`\n\n"
                            "1. /orders - посмотреть ID заказов\n"
                            "2. /listitems - посмотреть ID товаров\n"
                            "3. /delivery 123456789 1 - выдать товар",
                            parse_mode="Markdown")
        return
    
    order_id = args[0]
    product_id = int(args[1])
    
    # Ищем товар
    product = delivery_manager.get_item_by_id(product_id)
    if not product:
        await message.answer(f"❌ Товар с ID {product_id} не найден", parse_mode="Markdown")
        return
    
    # Выдаем товар
    success = funpay_manager.send_product_delivery(order_id, product['delivery_text'])
    
    if success:
        await message.answer(f"✅ Товар *{product['title']}* выдан по заказу #{order_id}", parse_mode="Markdown")
        
        # Уменьшаем количество
        new_stock = product.get('stock', 0) - 1
        if new_stock >= 0:
            delivery_manager.update_stock(product_id, new_stock)
    else:
        await message.answer(f"❌ Ошибка выдачи товара по заказу #{order_id}", parse_mode="Markdown")

@dp.message(Command("autoreply"))
async def cmd_autoreply(message: types.Message):
    """Настройка автоответов на Funpay"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Добавить автоответ", callback_data="autoreply_add")],
        [InlineKeyboardButton(text="📋 Список автоответов", callback_data="autoreply_list")],
        [InlineKeyboardButton(text="🗑 Удалить автоответ", callback_data="autoreply_remove")],
        [InlineKeyboardButton(text="🔛 Вкл/Выкл", callback_data="autoreply_toggle")]
    ])
    
    await message.answer(
        "🤖 **Автоответы на Funpay**\n\n"
        "Бот будет автоматически отвечать на входящие сообщения\n\n"
        "Пример: если напишут 'привет' - ответит 'Здравствуйте!'",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# ============ ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ============

def get_auto_reply(message_text: str) -> Optional[str]:
    """Получение автоответа из настроек"""
    # Здесь можно загружать из файла templates.json
    auto_replies = {
        "привет, здравствуйте, сап, ку": "Здравствуйте! Чем могу помочь?",
        "цена": "Цену уточняйте в объявлении",
        "наличие": "Уточняю наличие в лоте",
        "скидка": "Скидки обсуждаются индивидуально",
        "доставка": "Выдача происходит автоматически после оплаты",
        "как купить": "Оплатите лот, товар будет ",
    }
    
    for keyword, reply in auto_replies.items():
        if keyword.lower() in message_text.lower():
            return reply
    
    return None

def log_message(admin_id: int, target: str, text: str, direction: str):
    """Логирование сообщений"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "admin": admin_id,
        "target": target,
        "text": text,
        "direction": direction
    }
    
    try:
        with open("messages_log.json", "a", encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except:
        pass

def is_admin(user_id: int) -> bool:
    """Проверка администратора"""
    return admin_manager.is_admin(user_id)