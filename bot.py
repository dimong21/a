import asyncio
import logging
import json
import os
from datetime import datetime
from typing import Dict, List

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from config import BOT_TOKEN, ADMIN_ID, PARSE_INTERVAL, MAX_ITEMS, GOLDEN_KEY, LAST_SALES_FILE
from funpay_parser import FunpayParser
from autodelivery_manager import AutoDeliveryManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
parser = FunpayParser(golden_key=GOLDEN_KEY if GOLDEN_KEY else None)
delivery_manager = AutoDeliveryManager()

# Состояния для FSM
class AddItemState(StatesGroup):
    waiting_for_title = State()
    waiting_for_price = State()
    waiting_for_stock = State()
    waiting_for_delivery = State()

class RemoveItemState(StatesGroup):
    waiting_for_id = State()

# Хранилище последних продаж
last_sales = {}

def load_last_sales():
    """Загрузка последних продаж"""
    if os.path.exists(LAST_SALES_FILE):
        try:
            with open(LAST_SALES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_last_sales(sales):
    """Сохранение последних продаж"""
    try:
        with open(LAST_SALES_FILE, 'w', encoding='utf-8') as f:
            json.dump(sales, f, ensure_ascii=False, indent=2)
    except:
        pass

def is_admin(user_id: int) -> bool:
    """Проверка администратора"""
    return user_id == ADMIN_ID

async def check_new_sales():
    """Проверка новых продаж"""
    try:
        current_sales = parser.get_active_sales()
        last_sales_data = load_last_sales()
        
        # Сравниваем с предыдущей проверкой
        last_titles = set(last_sales_data.get('titles', []))
        current_titles = set([sale.get('title', '') for sale in current_sales])
        
        new_sales_titles = current_titles - last_titles
        
        if new_sales_titles:
            new_sales = [sale for sale in current_sales if sale.get('title', '') in new_sales_titles]
            
            for sale in new_sales[:5]:
                message = f"""
🆕 **НОВАЯ ПРОДАЖА НА FUNPAY!**

📦 Товар: {sale.get('title', 'Неизвестно')}
💰 Цена: {sale.get('price', 'Уточняется')}
👤 Продавец: {sale.get('seller', 'Неизвестно')}

🔗 Ссылка: https://funpay.com/ru/sell/
                """
                await bot.send_message(ADMIN_ID, message, parse_mode="Markdown")
            
            # Сохраняем новые продажи
            save_last_sales({'titles': list(current_titles), 'updated_at': datetime.now().isoformat()})
            logger.info(f"Отправлено {len(new_sales)} уведомлений о новых продажах")
        
    except Exception as e:
        logger.error(f"Ошибка проверки продаж: {e}")

async def periodic_check():
    """Периодическая проверка"""
    while True:
        await check_new_sales()
        await asyncio.sleep(PARSE_INTERVAL)

# ============ КОМАНДЫ БОТА ============

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Команда /start"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен. Этот бот только для администратора.")
        return
    
    mode = "🔓 Полный (с Golden Key)" if GOLDEN_KEY else "🔒 Ограниченный (только парсинг)"
    
    welcome_text = f"""
🤖 **Funpay Helper Bot V2.0**

✅ Бот успешно запущен!
🎯 Режим: {mode}
👤 Администратор: {message.from_user.first_name}

**📋 Доступные команды:**
/help - Показать все команды
/check - Проверить новые продажи сейчас
/search [товар] - Поиск на Funpay
/sales - Последние активные продажи
/stats - Статистика бота
/autodelivery - Управление автовыдачей
/listitems - Список товаров
/additem - Добавить товар (пошагово)
/removeitem - Удалить товар

🔄 Автоматические уведомления: КАЖДЫЕ {PARSE_INTERVAL} СЕКУНД
    """
    await message.answer(welcome_text, parse_mode="Markdown")
    
    # Отправляем тестовое сообщение
    await message.answer("✅ Бот работает! Уведомления будут приходить автоматически.")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Команда /help"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    help_text = """
📚 **Все команды бота:**

**📊 Основные:**
/start - Запуск бота
/help - Эта справка
/stats - Статистика работы

**🔍 Парсинг:**
/check - Проверить продажи сейчас
/search [запрос] - Поиск товаров
/sales - Показать активные продажи

**📦 Автовыдача:**
/autodelivery - Меню автовыдачи
/listitems - Список всех товаров
/additem - Добавить товар (интерактивно)
/removeitem - Удалить товар

**⚙️ Настройки:**
/status - Статус бота
/test - Проверить соединение

🔄 **Автоматические уведомления** приходят каждые {PARSE_INTERVAL} секунд
    """
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("test"))
async def cmd_test(message: types.Message):
    """Тестовая команда для проверки работы"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    await message.answer("✅ Бот работает исправно!")
    await message.answer(f"🕐 Время сервера: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    await message.answer(f"📦 Товаров в базе: {len(delivery_manager.get_all_items())}")
    await message.answer(f"🔑 Golden Key: {'✅ Есть' if GOLDEN_KEY else '❌ Нет'}")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    """Статус бота"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    items_count = len(delivery_manager.get_all_items())
    last_check = load_last_sales().get('updated_at', 'Никогда')
    
    status_text = f"""
📊 **СТАТУС БОТА**

✅ Состояние: Работает
🕐 Время: {datetime.now().strftime('%H:%M:%S')}
📅 Дата: {datetime.now().strftime('%Y-%m-%d')}

📦 Товаров в базе: {items_count}
⏱ Интервал проверки: {PARSE_INTERVAL} сек
🔄 Последняя проверка: {last_check}

🔑 Golden Key: {'Активен' if GOLDEN_KEY else 'Не используется'}
🏠 Хостинг: Bothost
    """
    await message.answer(status_text, parse_mode="Markdown")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Статистика"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    items_count = len(delivery_manager.get_all_items())
    last_check = load_last_sales().get('updated_at', 'Никогда')
    
    stats_text = f"""
📈 **СТАТИСТИКА БОТА**

📦 Товаров в автовыдаче: {items_count}
⏱ Интервал проверки: {PARSE_INTERVAL} сек
🔄 Последний парсинг: {last_check}
✅ Успешных проверок: Работает стабильно
📨 Уведомлений отправлено: Автоматически
    """
    await message.answer(stats_text, parse_mode="Markdown")

@dp.message(Command("check"))
async def cmd_check(message: types.Message):
    """Ручная проверка продаж"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    status_msg = await message.answer("🔍 Проверяю новые продажи...")
    
    try:
        sales = parser.get_active_sales()
        
        if not sales:
            await status_msg.edit_text("✅ Новых продаж не найдено")
            return
        
        response = "🆕 **Активные продажи:**\n\n"
        for i, sale in enumerate(sales[:MAX_ITEMS], 1):
            response += f"{i}. *{sale.get('title', 'Без названия')[:50]}*\n"
            response += f"   💰 {sale.get('price', 'Цена не указана')}\n"
            response += f"   👤 {sale.get('seller', 'Неизвестен')}\n\n"
        
        await status_msg.edit_text(response, parse_mode="Markdown")
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {str(e)}")
        logger.error(f"Ошибка при проверке: {e}")

@dp.message(Command("sales"))
async def cmd_sales(message: types.Message):
    """Показать активные продажи"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    await message.answer("🔍 Загружаю активные продажи...")
    
    sales = parser.get_active_sales()
    
    if not sales:
        await message.answer("❌ Продажи не найдены")
        return
    
    response = "📊 **Текущие активные продажи:**\n\n"
    for i, sale in enumerate(sales[:MAX_ITEMS], 1):
        response += f"{i}. *{sale.get('title', 'Без названия')[:50]}*\n"
        response += f"   💰 {sale.get('price', 'Цена не указана')}\n\n"
    
    await message.answer(response, parse_mode="Markdown")

@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    """Поиск товаров"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    query = message.text.replace("/search", "").strip()
    
    if not query:
        await message.answer("❌ Укажите товар для поиска\nПример: `/search World of Warcraft`", parse_mode="Markdown")
        return
    
    status_msg = await message.answer(f"🔍 Ищу: *{query}*...", parse_mode="Markdown")
    
    products = parser.search_products(query)
    
    if not products:
        await status_msg.edit_text(f"❌ По запросу *{query}* ничего не найдено", parse_mode="Markdown")
        return
    
    response = f"📦 **Результаты поиска:** *{query}*\n\n"
    for i, product in enumerate(products[:5], 1):
        response += f"{i}. *{product.get('name', 'Без названия')[:40]}*\n"
        response += f"   💰 {product.get('price', 'Цена не указана')}\n\n"
    
    await status_msg.edit_text(response, parse_mode="Markdown")

@dp.message(Command("autodelivery"))
async def cmd_autodelivery(message: types.Message):
    """Меню автовыдачи"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список товаров", callback_data="list_items")],
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="add_item_btn")],
        [InlineKeyboardButton(text="❌ Удалить товар", callback_data="remove_item_btn")],
        [InlineKeyboardButton(text="📤 Экспорт JSON", callback_data="export_json")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats_btn")]
    ])
    
    await message.answer("📦 **Управление автовыдачей**\nВыберите действие:", reply_markup=keyboard, parse_mode="Markdown")

@dp.message(Command("listitems"))
async def cmd_listitems(message: types.Message):
    """Список товаров"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    items = delivery_manager.get_all_items()
    
    if not items:
        await message.answer("📭 Список товаров пуст. Используйте /additem чтобы добавить")
        return
    
    response = "📋 **Список товаров в автовыдаче:**\n\n"
    for item in items:
        response += f"🆔 ID: `{item.get('id')}`\n"
        response += f"📦 *{item.get('title')}*\n"
        response += f"💰 {item.get('price')} ₽\n"
        response += f"📦 В наличии: {item.get('stock')}\n"
        response += f"✏️ {item.get('delivery_text', '')[:50]}...\n"
        response += "─" * 30 + "\n\n"
    
    await message.answer(response, parse_mode="Markdown")

@dp.message(Command("additem"))
async def cmd_additem(message: types.Message, state: FSMContext):
    """Добавление товара (пошагово)"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    await message.answer("📝 **Добавление нового товара**\n\nВведите название товара:")
    await state.set_state(AddItemState.waiting_for_title)

@dp.message(AddItemState.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("💰 Введите цену товара (только число):")
    await state.set_state(AddItemState.waiting_for_price)

@dp.message(AddItemState.waiting_for_price)
async def process_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price=price)
        await message.answer("📦 Введите количество товара в наличии (число):")
        await state.set_state(AddItemState.waiting_for_stock)
    except:
        await message.answer("❌ Ошибка! Введите число (например: 100.50)")

@dp.message(AddItemState.waiting_for_stock)
async def process_stock(message: types.Message, state: FSMContext):
    try:
        stock = int(message.text)
        await state.update_data(stock=stock)
        await message.answer("✏️ Введите текст для автовыдачи (логин/пароль или ключи):")
        await state.set_state(AddItemState.waiting_for_delivery)
    except:
        await message.answer("❌ Ошибка! Введите целое число (например: 10)")

@dp.message(AddItemState.waiting_for_delivery)
async def process_delivery(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    success = delivery_manager.add_item(
        title=data['title'],
        price=data['price'],
        stock=data['stock'],
        delivery_text=message.text
    )
    
    if success:
        await message.answer(f"✅ Товар *{data['title']}* успешно добавлен!", parse_mode="Markdown")
    else:
        await message.answer("❌ Ошибка при добавлении товара")
    
    await state.clear()

@dp.message(Command("removeitem"))
async def cmd_removeitem(message: types.Message, state: FSMContext):
    """Удаление товара"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    items = delivery_manager.get_all_items()
    if not items:
        await message.answer("📭 Список товаров пуст")
        return
    
    response = "🗑 **Удаление товара**\n\nВведите ID товара для удаления:\n\n"
    for item in items:
        response += f"ID: {item['id']} - {item['title']}\n"
    
    await message.answer(response)
    await state.set_state(RemoveItemState.waiting_for_id)

@dp.message(RemoveItemState.waiting_for_id)
async def process_remove(message: types.Message, state: FSMContext):
    try:
        item_id = int(message.text)
        success = delivery_manager.remove_item(item_id)
        
        if success:
            await message.answer(f"✅ Товар с ID {item_id} удален")
        else:
            await message.answer(f"❌ Товар с ID {item_id} не найден")
    except:
        await message.answer("❌ Ошибка! Введите число (ID товара)")
    
    await state.clear()

# ============ CALLBACK HANDLERS ============

@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    if callback.data == "list_items":
        items = delivery_manager.get_all_items()
        if not items:
            await callback.message.answer("📭 Список товаров пуст")
        else:
            response = "📋 **Список товаров:**\n\n"
            for item in items:
                response += f"🆔 ID: {item.get('id')} - {item.get('title')} ({item.get('price')}₽) [x{item.get('stock')}]\n"
            await callback.message.answer(response)
    
    elif callback.data == "add_item_btn":
        await callback.message.answer("Используйте команду /additem для добавления товара")
    
    elif callback.data == "remove_item_btn":
        await callback.message.answer("Используйте команду /removeitem для удаления товара")
    
    elif callback.data == "export_json":
        if os.path.exists("autodelivery_items.json"):
            with open("autodelivery_items.json", 'rb') as f:
                await callback.message.answer_document(f, caption="📄 Файл автовыдачи")
        else:
            await callback.message.answer("❌ Файл не найден")
    
    elif callback.data == "stats_btn":
        items_count = len(delivery_manager.get_all_items())
        await callback.message.answer(f"📊 Статистика:\nТоваров: {items_count}\nИнтервал: {PARSE_INTERVAL} сек")
    
    await callback.answer()

# ============ ЗАПУСК БОТА ============

async def health_check(request):
    """Эндпоинт для health check Bothost"""
    return web.Response(text="OK")

async def main():
    """Запуск бота"""
    # Запускаем периодическую проверку
    asyncio.create_task(periodic_check())
    
    # Запускаем веб-сервер для health check (нужно для Bothost)
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    
    logger.info("=" * 50)
    logger.info("🤖 БОТ УСПЕШНО ЗАПУЩЕН НА BOTHOST!")
    logger.info(f"📊 Администратор: {ADMIN_ID}")
    logger.info(f"⏱ Интервал проверки: {PARSE_INTERVAL} сек")
    logger.info(f"🔑 Golden Key: {'✅ Есть' if GOLDEN_KEY else '❌ Нет'}")
    logger.info("=" * 50)
    
    # Отправляем приветствие администратору
    try:
        await bot.send_message(ADMIN_ID, "✅ **БОТ ЗАПУЩЕН НА BOTHOST!**\n\nВсе системы работают.\nУведомления будут приходить автоматически.", parse_mode="Markdown")
    except:
        pass
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())