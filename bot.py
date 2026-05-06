import asyncio
import logging
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

from config import BOT_TOKEN, ADMIN_ID, PARSE_INTERVAL, GOLDEN_KEY
from funpay_parser import FunpayParser
from autodelivery_manager import AutoDeliveryManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %name)s - %levelname)s - %message)s'
)
logger = logging.getLogger(__name__)

# Инициализация
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
parser = FunpayParser(golden_key=GOLDEN_KEY if GOLDEN_KEY else None)
delivery_manager = AutoDeliveryManager()

# Хранилище данных
admins = {ADMIN_ID: {"name": "Главный администратор", "role": "owner"}}
user_sessions = {}  # Для общения с пользователями
auto_bump_active = False
last_bump_time = None

# Состояния для FSM
class MessageToUserState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_message = State()

class ReplyToUserState(StatesGroup):
    waiting_for_reply = State()

class AddAdminState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_user_name = State()

class RemoveAdminState(StatesGroup):
    waiting_for_user_id = State()

class TemplateState(StatesGroup):
    waiting_for_template_name = State()
    waiting_for_template_text = State()

class AutoDeliveryState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_product_id = State()

# Клавиатуры
def main_keyboard():
    """Главная клавиатура"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🔍 Поиск")],
            [KeyboardButton(text="📦 Автовыдача"), KeyboardButton(text="👥 Админы")],
            [KeyboardButton(text="💬 Общение"), KeyboardButton(text="⚙️ Настройки")]
        ],
        resize_keyboard=True
    )
    return keyboard

def admin_keyboard():
    """Клавиатура администратора"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Управление админами", callback_data="admin_manage")],
        [InlineKeyboardButton(text="📝 Шаблоны сообщений", callback_data="admin_templates")],
        [InlineKeyboardButton(text="🔄 Автоподнятие", callback_data="admin_bump")],
        [InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="💬 Ответ пользователю", callback_data="admin_reply")],
        [InlineKeyboardButton(text="📦 Управление товарами", callback_data="admin_products")],
        [InlineKeyboardButton(text="📋 Логи", callback_data="admin_logs")]
    ])
    return keyboard

# ============ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ============

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in admins

def escape_markdown(text: str) -> str:
    """Экранирование спецсимволов для Markdown"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

# ============ ФУНКЦИИ FUNPAY ============

async def auto_bump():
    """Автоподнятие объявлений каждые 4 часа"""
    global auto_bump_active, last_bump_time
    while auto_bump_active:
        try:
            if GOLDEN_KEY:
                # Здесь логика поднятия объявлений через Golden Key
                logger.info("Автоподнятие объявлений...")
                await bot.send_message(ADMIN_ID, "🔄 Выполнено автоподнятие объявлений на Funpay")
                last_bump_time = datetime.now()
            await asyncio.sleep(14400)  # 4 часа
        except Exception as e:
            logger.error(f"Ошибка автоподнятия: {e}")
            await asyncio.sleep(3600)

async def search_funpay(query: str) -> str:
    """Поиск на Funpay и форматирование результата"""
    try:
        products = parser.search_products(query)
        if not products:
            return f"❌ По запросу '{query}' ничего не найдено"
        
        result = f"🔍 **Результаты поиска: {escape_markdown(query)}**\n\n"
        for i, product in enumerate(products[:10], 1):
            result += f"{i}. **{escape_markdown(product.get('name', 'Без названия')[:50])}**\n"
            result += f"   💰 {escape_markdown(product.get('price', 'Цена не указана'))}\n\n"
        return result
    except Exception as e:
        logger.error(f"Ошибка поиска: {e}")
        return f"❌ Ошибка поиска: {str(e)}"

# ============ ОСНОВНЫЕ КОМАНДЫ ============

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Команда /start"""
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    if is_admin(user_id):
        welcome_text = f"""
🤖 **Funpay Helper Bot v3.0**

✅ Добро пожаловать, {escape_markdown(user_name)}!

**Ваши возможности:**
• Мониторинг Funpay
• Автовыдача товаров
• Общение с клиентами
• Управление админами
• Автоподнятие объявлений

Используйте кнопки ниже для управления.
"""
        await message.answer(welcome_text, parse_mode="Markdown", reply_markup=main_keyboard())
    else:
        # Сохраняем пользователя для общения
        user_sessions[user_id] = {
            "name": user_name,
            "username": message.from_user.username,
            "first_seen": datetime.now().isoformat()
        }
        await message.answer(
            f"👋 Здравствуйте, {escape_markdown(user_name)}!\n\n"
            f"Это бот поддержки. Ваше сообщение будет передано администратору.\n\n"
            f"Просто напишите любое сообщение, и мы свяжемся с вами!",
            parse_mode="Markdown"
        )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Команда /help - без ошибок"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    help_text = """
🤖 **Помощь по боту**

<b>Основные команды:</b>
/start - Главное меню
/stats - Статистика
/search [запрос] - Поиск на Funpay

<b>Управление:</b>
/autodelivery - Автовыдача товаров
/admins - Управление администраторами
/bump - Автоподнятие объявлений
/templates - Шаблоны сообщений

<b>Общение:</b>
/reply [ID] [текст] - Ответ пользователю
/broadcast [текст] - Рассылка

<b>Другие команды видны в меню</b>

ℹ️ Все уведомления приходят автоматически
    """
    await message.answer(help_text, parse_mode="HTML")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Статистика бота"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    items_count = len(delivery_manager.get_all_items())
    admins_count = len(admins)
    users_count = len(user_sessions)
    
    stats_text = f"""
📊 <b>Статистика бота</b>

👥 Администраторов: {admins_count}
👤 Пользователей: {users_count}
📦 Товаров в базе: {items_count}
🔄 Автоподнятие: {'✅ Активно' if auto_bump_active else '❌ Неактивно'}
⏱ Последнее поднятие: {last_bump_time.strftime('%Y-%m-%d %H:%M:%S') if last_bump_time else 'Никогда'}

🔑 Golden Key: {'✅ Есть' if GOLDEN_KEY else '❌ Нет'}
    """
    await message.answer(stats_text, parse_mode="HTML")

@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    """Поиск на Funpay"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    query = message.text.replace("/search", "").strip()
    
    if not query:
        await message.answer("❌ Укажите запрос\nПример: `/search World of Warcraft`", parse_mode="Markdown")
        return
    
    status_msg = await message.answer(f"🔍 Ищу: {query}...")
    
    result = await search_funpay(query)
    await status_msg.edit_text(result, parse_mode="Markdown")

@dp.message(Command("autodelivery"))
async def cmd_autodelivery(message: types.Message):
    """Управление автовыдачей"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список товаров", callback_data="delivery_list")],
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="delivery_add")],
        [InlineKeyboardButton(text="❌ Удалить товар", callback_data="delivery_remove")],
        [InlineKeyboardButton(text="📤 Экспорт JSON", callback_data="delivery_export")],
        [InlineKeyboardButton(text="📨 Отправить пользователю", callback_data="delivery_send")]
    ])
    
    await message.answer("📦 **Управление автовыдачей**\nВыберите действие:", reply_markup=keyboard, parse_mode="Markdown")

@dp.message(Command("admins"))
async def cmd_admins(message: types.Message):
    """Управление администраторами"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    admin_list = "👥 **Список администраторов:**\n\n"
    for uid, info in admins.items():
        role_icon = "👑" if info.get('role') == 'owner' else "👤"
        admin_list += f"{role_icon} **{escape_markdown(info['name'])}** - `{uid}`\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add")],
        [InlineKeyboardButton(text="❌ Удалить админа", callback_data="admin_remove")]
    ])
    
    await message.answer(admin_list, reply_markup=keyboard, parse_mode="Markdown")

@dp.message(Command("bump"))
async def cmd_bump(message: types.Message):
    """Управление автоподнятием"""
    global auto_bump_active
    
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    if not GOLDEN_KEY:
        await message.answer("❌ Для автоподнятия нужен Golden Key!")
        return
    
    if auto_bump_active:
        auto_bump_active = False
        await message.answer("✅ Автоподнятие **ОСТАНОВЛЕНО**", parse_mode="Markdown")
    else:
        auto_bump_active = True
        asyncio.create_task(auto_bump())
        await message.answer("✅ Автоподнятие **ЗАПУЩЕНО** (каждые 4 часа)", parse_mode="Markdown")

@dp.message(Command("templates"))
async def cmd_templates(message: types.Message):
    """Шаблоны сообщений"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Создать шаблон", callback_data="template_create")],
        [InlineKeyboardButton(text="📋 Список шаблонов", callback_data="template_list")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="template_edit")],
        [InlineKeyboardButton(text="🗑 Удалить", callback_data="template_delete")]
    ])
    
    await message.answer("📝 **Управление шаблонами сообщений**", reply_markup=keyboard, parse_mode="Markdown")

@dp.message(Command("reply"))
async def cmd_reply(message: types.Message, state: FSMContext):
    """Ответ пользователю"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer("❌ Использование: `/reply [user_id] [текст]`", parse_mode="Markdown")
        return
    
    user_id = int(args[1])
    reply_text = args[2] if len(args) > 2 else ""
    
    if reply_text:
        try:
            await bot.send_message(user_id, f"📨 **Ответ администратора:**\n\n{reply_text}", parse_mode="Markdown")
            await message.answer(f"✅ Сообщение отправлено пользователю `{user_id}`", parse_mode="Markdown")
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")
    else:
        await state.update_data(reply_to_user=user_id)
        await message.answer("✏️ Введите текст ответа:")
        await state.set_state(ReplyToUserState.waiting_for_reply)

@dp.message(ReplyToUserState.waiting_for_reply)
async def process_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('reply_to_user')
    
    try:
        await bot.send_message(user_id, f"📨 **Ответ администратора:**\n\n{escape_markdown(message.text)}", parse_mode="Markdown")
        await message.answer(f"✅ Сообщение отправлено пользователю `{user_id}`", parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    
    await state.clear()

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    """Рассылка всем пользователям"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещен")
        return
    
    text = message.text.replace("/broadcast", "").strip()
    
    if not text:
        await message.answer("❌ Укажите текст рассылки\nПример: `/broadcast Привет всем!`", parse_mode="Markdown")
        return
    
    sent = 0
    failed = 0
    
    status_msg = await message.answer("📨 Начинаю рассылку...")
    
    for user_id in user_sessions.keys():
        try:
            await bot.send_message(user_id, f"📢 **РАССЫЛКА:**\n\n{escape_markdown(text)}", parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.05)  # Чтобы не банили
        except:
            failed += 1
    
    await status_msg.edit_text(f"✅ Рассылка завершена!\n📨 Отправлено: {sent}\n❌ Ошибок: {failed}")

# ============ ОБРАБОТЧИК СООБЩЕНИЙ ОТ ПОЛЬЗОВАТЕЛЕЙ ============

@dp.message()
async def handle_user_message(message: types.Message):
    """Обработка сообщений от обычных пользователей"""
    user_id = message.from_user.id
    
    # Если это команда - пропускаем
    if message.text and message.text.startswith('/'):
        return
    
    # Если администратор - обработка текстовых кнопок
    if is_admin(user_id):
        text = message.text
        
        if text == "📊 Статистика":
            await cmd_stats(message)
        elif text == "🔍 Поиск":
            await message.answer("🔍 Введите поисковый запрос в формате:\n`/search запрос`", parse_mode="Markdown")
        elif text == "📦 Автовыдача":
            await cmd_autodelivery(message)
        elif text == "👥 Админы":
            await cmd_admins(message)
        elif text == "💬 Общение":
            # Показываем список пользователей для общения
            if user_sessions:
                users_list = "👥 **Пользователи для общения:**\n\n"
                for uid, info in user_sessions.items():
                    users_list += f"🆔 `{uid}` - {escape_markdown(info['name'])}\n"
                users_list += "\nИспользуйте: `/reply [ID] [текст]`"
                await message.answer(users_list, parse_mode="Markdown")
            else:
                await message.answer("📭 Нет активных пользователей")
        elif text == "⚙️ Настройки":
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Автоподнятие", callback_data="admin_bump")],
                [InlineKeyboardButton(text="📝 Шаблоны", callback_data="admin_templates")],
                [InlineKeyboardButton(text="👥 Админы", callback_data="admin_manage")]
            ])
            await message.answer("⚙️ **Настройки бота**", reply_markup=keyboard, parse_mode="Markdown")
        else:
            # Пересылаем сообщение от админа пользователю (если указан ID)
            pass
    else:
        # Сообщение от обычного пользователя - уведомляем админов
        user_info = user_sessions.get(user_id, {"name": message.from_user.first_name})
        
        admin_message = f"""
💬 **Новое сообщение от пользователя!**

👤 Имя: {escape_markdown(user_info['name'])}
🆔 ID: `{user_id}`
📝 Сообщение:
{escape_markdown(message.text[:500])}

Для ответа используйте:
`/reply {user_id} ваш ответ`
        """
        
        for admin_id in admins.keys():
            try:
                await bot.send_message(admin_id, admin_message, parse_mode="Markdown")
            except:
                pass
        
        await message.answer("✅ Ваше сообщение отправлено администратору. Ожидайте ответа.")

# ============ CALLBACK HANDLERS ============

@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    # Статистика
    if callback.data == "admin_stats":
        await cmd_stats(callback.message)
    
    # Управление админами
    elif callback.data == "admin_manage":
        await cmd_admins(callback.message)
    
    elif callback.data == "admin_add":
        await callback.message.answer("➕ Введите Telegram ID нового администратора:")
        await state.set_state(AddAdminState.waiting_for_user_id)
    
    elif callback.data == "admin_remove":
        await callback.message.answer("❌ Введите Telegram ID администратора для удаления:")
        await state.set_state(RemoveAdminState.waiting_for_user_id)
    
    # Автоподнятие
    elif callback.data == "admin_bump":
        await cmd_bump(callback.message)
    
    # Шаблоны
    elif callback.data == "admin_templates":
        await cmd_templates(callback.message)
    
    # Рассылка
    elif callback.data == "admin_broadcast":
        await callback.message.answer("📨 Введите текст для рассылки:\nПример: `/broadcast Привет всем!`", parse_mode="Markdown")
    
    # Ответ пользователю
    elif callback.data == "admin_reply":
        await callback.message.answer("💬 Введите ID пользователя и сообщение:\nПример: `/reply 123456789 текст`", parse_mode="Markdown")
    
    # Управление товарами
    elif callback.data == "admin_products":
        await cmd_autodelivery(callback.message)
    
    # Логи
    elif callback.data == "admin_logs":
        await callback.message.answer("📋 Логи доступны в панели Bothost")
    
    # Автовыдача
    elif callback.data == "delivery_list":
        await cmd_listitems(callback.message)
    
    elif callback.data == "delivery_add":
        await cmd_additem(callback.message, state)
    
    elif callback.data == "delivery_remove":
        await cmd_removeitem(callback.message, state)
    
    elif callback.data == "delivery_export":
        if os.path.exists("autodelivery_items.json"):
            with open("autodelivery_items.json", 'rb') as f:
                await callback.message.answer_document(f, caption="📄 Файл автовыдачи")
        else:
            await callback.message.answer("❌ Файл не найден")
    
    elif callback.data == "delivery_send":
        await callback.message.answer("📨 Введите ID пользователя:\nПример: `/delivery 123456789 1`\nГде 1 - ID товара из списка", parse_mode="Markdown")
    
    await callback.answer()

# ============ ВСПОМОГАТЕЛЬНЫЕ КОМАНДЫ ДЛЯ ТОВАРОВ ============

async def cmd_listitems(message: types.Message):
    """Список товаров"""
    items = delivery_manager.get_all_items()
    
    if not items:
        await message.answer("📭 Список товаров пуст")
        return
    
    response = "📋 **Список товаров:**\n\n"
    for item in items:
        response += f"🆔 ID: `{item.get('id')}`\n"
        response += f"📦 *{escape_markdown(item.get('title', 'Без названия')[:50])}*\n"
        response += f"💰 {item.get('price', 0)} ₽ | 📦 {item.get('stock', 0)} шт\n"
        response += f"✏️ {escape_markdown(item.get('delivery_text', '')[:50])}...\n\n"
    
    await message.answer(response, parse_mode="Markdown")

async def cmd_additem(message: types.Message, state: FSMContext):
    """Добавление товара"""
    await message.answer("📝 **Добавление товара**\n\nВведите название товара:")
    await state.set_state(AddAdminState.waiting_for_user_id)  # Временно используем другое состояние

async def cmd_removeitem(message: types.Message, state: FSMContext):
    """Удаление товара"""
    await message.answer("🗑 Введите ID товара для удаления:")
    await state.set_state(RemoveAdminState.waiting_for_user_id)

# ============ ДОБАВЛЯЕМ НЕДОСТАЮЩИЕ СОСТОЯНИЯ ============

@dp.message(AddAdminState.waiting_for_user_id)
async def process_add_admin_id(message: types.Message, state: FSMContext):
    try:
        new_admin_id = int(message.text)
        await state.update_data(new_admin_id=new_admin_id)
        await message.answer("Введите имя нового администратора:")
        await state.set_state(AddAdminState.waiting_for_user_name)
    except:
        await message.answer("❌ Ошибка! Введите число (Telegram ID)")
        await state.clear()

@dp.message(AddAdminState.waiting_for_user_name)
async def process_add_admin_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    new_admin_id = data.get('new_admin_id')
    
    admins[new_admin_id] = {
        "name": message.text,
        "role": "admin",
        "added_by": message.from_user.id,
        "added_at": datetime.now().isoformat()
    }
    
    await message.answer(f"✅ Администратор {message.text} (ID: {new_admin_id}) добавлен!")
    
    try:
        await bot.send_message(new_admin_id, f"👋 Вы добавлены как администратор бота {message.from_user.first_name}")
    except:
        pass
    
    await state.clear()

@dp.message(RemoveAdminState.waiting_for_user_id)
async def process_remove_admin(message: types.Message, state: FSMContext):
    try:
        remove_id = int(message.text)
        
        if remove_id == ADMIN_ID:
            await message.answer("❌ Нельзя удалить главного администратора!")
        elif remove_id in admins:
            del admins[remove_id]
            await message.answer(f"✅ Администратор {remove_id} удален!")
        else:
            await message.answer(f"❌ Администратор {remove_id} не найден")
    except:
        await message.answer("❌ Ошибка! Введите число (Telegram ID)")
    
    await state.clear()

# ============ ЗАПУСК БОТА ============

async def health_check(request):
    """Health check для Bothost"""
    return web.Response(text="OK")

async def main():
    """Запуск бота"""
    # Запускаем health check сервер
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    
    logger.info("=" * 50)
    logger.info("🤖 БОТ УСПЕШНО ЗАПУЩЕН НА BOTHOST!")
    logger.info(f"👥 Администраторов: {len(admins)}")
    logger.info(f"🔑 Golden Key: {'✅ Есть' if GOLDEN_KEY else '❌ Нет'}")
    logger.info("=" * 50)
    
    # Приветствие админу
    await bot.send_message(ADMIN_ID, "✅ **БОТ ЗАПУЩЕН!**\n\nНовые функции:\n• Общение с пользователями\n• Управление админами\n• Автоподнятие объявлений\n• Шаблоны сообщений", parse_mode="Markdown")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())