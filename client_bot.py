import csv
import io
import requests
import telebot
from telebot import types

# ================= НАСТРОЙКИ =====================================

BOT_TOKEN = "8279904310:AAHgVpA4iaby1_iOoVZkcWNxibQaLddG5mw"
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQQR1h0G831R-XZBKSDylUcJ5jiHdb4OTRHL1hCeRCOIzF6uT_l9GlcAhkNBcL4kYuNYcWtb4BSnMEq/pub?gid=0&single=true&output=csv"

MANAGER_CONTACT = "@incmanagerrrr"

MAX_RESULTS = 1000  # сколько максимум позиций показывать за раз

# ================================================================

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

# user_id -> состояние (например 'searching')
user_states = {}


# ---------- ЗАГРУЗКА ДАННЫХ ИЗ ТАБЛИЦЫ --------------------------

def load_items():
    """
    Загружает позиции из Google-таблицы (CSV_URL).
    Ожидаются столбцы: id, category, line, description, price, image.
    Возвращает список словарей.
    """
    if not CSV_URL:
        raise ValueError("CSV_URL не задан")

    resp = requests.get(CSV_URL)
    resp.raise_for_status()

    text = resp.content.decode("utf-8")

    f = io.StringIO(text)
    reader = csv.DictReader(f)

    items = []
    for idx, row in enumerate(reader, start=1):
        try:
            line_name = (row.get("line") or "").strip()
            if not line_name:
                continue

            category = (row.get("category") or "").strip()
            description = (row.get("description") or "").strip()
            price = (row.get("price") or "").strip()
            image = (row.get("image") or "").strip()
            line_id = (row.get("id") or "").strip() or str(idx)

            items.append({
                "id": line_id,
                "category": category,
                "line": line_name,
                "description": description,
                "price": price,
                "image": image,
                "raw": row
            })
        except Exception as e:
            print("Ошибка в строке CSV:", e, row)
            continue

    return items


# ---------- ОТПРАВКА КАРТОЧКИ ТОВАРА ----------------------------

def button_text_for_category(cat: str) -> str:
    """Возвращает текст кнопки в зависимости от категории."""
    c = (cat or "").lower()
    if "под" in c:
        return "Цвета"
    # Жидкости, Одноразки, Снюсы
    return "Вкусы"


def send_item_card(chat_id, item):
    """
    Отправляет карточку:
    – фото (если есть),
    – подпись: линейка + категория + цена,
    – под фото кнопка: Вкусы/Цвета (в зависимости от категории).
    Описание (вкусы/цвета) показываем при нажатии кнопки.
    """
    caption = f"*{item['line']}*\n"

    if item["category"]:
        caption += f"Категория: {item['category']}\n"

    if item["price"]:
        caption += f"Цена: {item['price']}\n"

    kb = types.InlineKeyboardMarkup()
    btn_text = button_text_for_category(item["category"])
    kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"info_{item['id']}"))

    img = item["image"]
    sent = False

    if img and (img.startswith("http://") or img.startswith("https://")):
        try:
            # короткая подпись в caption + кнопка
            bot.send_photo(chat_id, img, caption=caption, reply_markup=kb)
            sent = True
        except Exception as e:
            print("Ошибка отправки фото:", e)

    if not sent:
        # если фото не отправилось — просто текст + кнопка
        bot.send_message(chat_id, caption, reply_markup=kb)


# ---------- КЛАВИАТУРЫ -------------------------------------------

def main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📂 Категории", "🔍 Поиск")
    kb.row("ℹ️ Помощь", "👨‍💼 Менеджер")
    return kb


def category_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Жидкости", callback_data="cat_Жидкости"))
    kb.add(types.InlineKeyboardButton("Под-системы", callback_data="cat_Под-системы"))
    kb.add(types.InlineKeyboardButton("Одноразки", callback_data="cat_Одноразки"))
    kb.add(types.InlineKeyboardButton("Снюсы", callback_data="cat_Снюсы"))
    return kb


# ---------- ОБРАБОТЧИКИ КОМАНД -----------------------------------

@bot.message_handler(commands=['start'])
def cmd_start(message):
    bot.send_message(
        message.chat.id,
        "Привет! Это бот для удобного просмотра ассортимента.\n\n"
        "• «📂 Категории» — выбрать категорию (жидкости, поды, одноразки, снюсы).\n"
        "• «🔍 Поиск» — поиск по названию линейки или описанию.\n\n"
        "Бот только показывает ассортимент, без корзины и заказов.",
        reply_markup=main_keyboard()
    )


@bot.message_handler(commands=['help'])
def cmd_help(message):
    bot.send_message(
        message.chat.id,
        "Бот-витрина:\n\n"
        "📂 Категории — фильтр по типу товара.\n"
        "🔍 Поиск — по названию линейки и тексту описания.\n"
        "Ассортимент берётся из Google-таблицы (id, category, line, description, price, image).",
        reply_markup=main_keyboard()
    )


@bot.message_handler(func=lambda m: m.text == "👨‍💼 Менеджер")
def handle_manager(message):
    # parse_mode=None — чтобы не ломался Markdown, если вдруг появятся подчёркивания и т.п.
    bot.send_message(
        message.chat.id,
        f"По всем вопросам пишите менеджеру: {MANAGER_CONTACT}",
        parse_mode=None
    )


# ---------- КАТЕГОРИИ --------------------------------------------

@bot.message_handler(func=lambda m: m.text == "📂 Категории")
def handle_categories(message):
    kb = category_keyboard()
    bot.send_message(
        message.chat.id,
        "Выберите категорию:",
        reply_markup=kb
    )


# ---------- ПОИСК -------------------------------------------------

@bot.message_handler(func=lambda m: m.text == "🔍 Поиск")
def handle_search_button(message):
    user_states[message.from_user.id] = "searching"
    bot.send_message(
        message.chat.id,
        "Введи часть названия линейки или текст из описания.\n\n"
        "Например: *манго*, *под-система*, *снюс*."
    )


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "searching")
def handle_search_query(message):
    user_states.pop(message.from_user.id, None)
    query = (message.text or "").strip().lower()
    if not query:
        bot.send_message(message.chat.id, "Пустой запрос. Попробуй ещё раз.")
        return

    try:
        items = load_items()
    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка при загрузке ассортимента:\n`{e}`")
        return

    found = []
    for item in items:
        text_to_search = (item["line"] + " " + (item["description"] or "")).lower()
        if query in text_to_search:
            found.append(item)

    if not found:
        bot.send_message(message.chat.id, f"Ничего не нашёл по запросу «{message.text}».")
        return

    bot.send_message(message.chat.id, f"Нашёл {len(found)} совпадений, показываю первые {MAX_RESULTS}:")
    for item in found[:MAX_RESULTS]:
        send_item_card(message.chat.id, item)


# ---------- CALLBACK (категории и кнопки под фото) ---------------

@bot.callback_query_handler(func=lambda c: True)
def handle_callback(call: types.CallbackQuery):
    data = call.data
    chat_id = call.message.chat.id

    # Выбор категории
    if data.startswith("cat_"):
        category = data.split("_", 1)[1]  # Жидкости / Под-системы / Одноразки / Снюсы
        print("CATEGORY FROM BUTTON:", repr(category))

        try:
            items = load_items()
        except Exception as e:
            bot.answer_callback_query(call.id, "Ошибка загрузки")
            print("load_items error:", e)
            return

        def norm(s: str) -> str:
            return (s or "").strip().lower()

        # ГРУБЫЙ ФИКС ДЛЯ СНЮСОВ:
        # если выбрали "Снюсы" — берём все строки, где категория НЕ Жидкости/Под-системы/Одноразки
        if norm(category).startswith("снюс"):
            known = ("жидкости", "под-системы", "одноразки")
            filtered = [
                item for item in items
                if norm(item["category"]) not in known
            ]
        else:
            filtered = [
                item for item in items
                if norm(item["category"]) == norm(category)
            ]

        bot.answer_callback_query(call.id)

        if not filtered:
            bot.send_message(chat_id, f"В категории «{category}» пока нет позиций.")
            return

        bot.send_message(chat_id, f"Категория: *{category}* (показываю до {MAX_RESULTS} позиций)")
        for item in filtered[:MAX_RESULTS]:
            send_item_card(chat_id, item)

    # Нажата кнопка "Вкусы"/"Цвета" под фото
    elif data.startswith("info_"):
        item_id = data.split("_", 1)[1]

        try:
            items = load_items()
        except Exception as e:
            bot.answer_callback_query(call.id, "Ошибка загрузки")
            print("load_items error:", e)
            return

        item = next((it for it in items if it["id"] == item_id), None)
        if not item:
            bot.answer_callback_query(call.id, "Позиция не найдена")
            return

        bot.answer_callback_query(call.id)

        # 1) Снова отправляем фото + линейку + цену (шапка)
        header = f"*{item['line']}*\n"
        if item["price"]:
            header += f"Цена: {item['price']}\n"

        img = item["image"]
        sent = False
        if img and (img.startswith("http://") or img.startswith("https://")):
            try:
                bot.send_photo(chat_id, img, caption=header)
                sent = True
            except Exception as e:
                print("Ошибка повторной отправки фото:", e)

        if not sent:
            bot.send_message(chat_id, header)

        # 2) Ниже отправляем вкусы / цвета из description
        cat = (item["category"] or "").lower()
        if "под" in cat:
            title = "Цвета"
        else:
            title = "Вкусы"

        if item["description"]:
            bot.send_message(chat_id, f"*{title}:*\n{item['description']}")
        else:
            bot.send_message(chat_id, f"{title}: нет описания.")

    else:
        bot.answer_callback_query(call.id)


# ---------- ЗАПУСК -----------------------------------------------

print("Тестовый бот-витрина запущен. Нажми Ctrl+C, чтобы остановить.")
bot.infinity_polling()