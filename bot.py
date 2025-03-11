import pandas as pd
import re
import asyncio  # Для отслеживания времени
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Загрузка данных из Excel
try:
    data = pd.read_excel("result_with_ids.xlsx")
except FileNotFoundError:
    print("Ошибка: Файл result_with_ids.xlsx не найден. Убедитесь, что он находится в той же папке, что и код.")
    data = pd.DataFrame()  # Заглушка, чтобы бот продолжал работать

# Переменные для хранения языка пользователя
user_languages = {}  # Словарь для хранения языка пользователей (по chat_id)

# Словарь для отслеживания времени последней активности пользователей
user_last_activity = {}

# Локализованные сообщения
messages = {
    "start": {
        "ru": "Сәлеметсіз бе! Выберите опцию ниже:",
        "kz": "Сәлеметсіз бе! Опцияны таңдаңыз:"
    },
    "help": {
        "ru": "Если у вас есть вопросы или нужна помощь, напишите нам на WhatsApp: 📞 +7 777 777 65 00.",
        "kz": "Егер сұрақтарыңыз болса немесе көмек қажет болса, бізге WhatsApp-қа жазыңыз: 📞 +7 777 777 65 00."
    },
    "unknown_request": {
        "ru": "Извините, я не совсем понимаю ваш запрос. Попробуйте использовать кнопки ниже или введите ваш ВУ номер.",
        "kz": "Кешіріңіз, мен сіздің сұрағыңызды түсінбедім. Төмендегі батырмаларды пайдаланыңыз немесе ВУ нөміріңізді енгізіңіз."
    },
    "enter_vu": {
        "ru": "Введите ваш ВУ номер, чтобы узнать информацию о купонах.",
        "kz": "Купон туралы ақпаратты алу үшін ВУ нөміріңізді енгізіңіз."
    }
}

# Функция для поиска данных по ВУ номеру
def find_data_by_vu(vu_number):
    user_data = data[data["ВУ номер"] == vu_number]
    if not user_data.empty:
        result = user_data.to_dict(orient="records")[0]
        return {
            "Имя": result['Имя'],
            "Город": result['Город'],
            "Количество заказов": result['Количество заказов'],
            "Количество купонов": result['Количество купонов'],
            "Номера купонов": result['Номер купона'],
        }
    else:
        return None

# Генерация персонального сообщения для найденного ВУ с учётом языка
def generate_message(user_data, language):
    if language == "ru":
        return (f"Здравствуйте, уважаемый {user_data['Имя']}!🤝\n\n"
                f"🕋 Мы проводим розыгрыш путёвки в УМРУ!\n"
                f"🏆 Для участия в розыгрыше необходимо выполнять заказы.\n"
                f"🎟 За каждые 100 выполненных заказов = 1 купон.\n\n"
                f"📅 Заказы нужно было выполнять в следующие периоды:\n"
                f"21.02.2025 - 28.02.2025\n"
                f"01.03.2025 - 07.03.2025\n\n"
                f"У вас выполнено {user_data['Количество заказов']} заказов, поэтому у вас есть {user_data['Количество купонов']} купонов.\n"
                f"Номера ваших купонов: {user_data['Номера купонов']}.\n\n"
                f"Купоны будут отправлены только через WhatsApp 👍\n"
                f"Если у вас есть вопросы или нужна помощь, свяжитесь с нами:\n"
                f"📞 +7 777 777 65 00\n\n"
                f"С уважением, таксопарк \"Автопартнёр\"!")
    elif language == "kz":
        return (f"Сәлеметсіз бе, Құрметті {user_data['Имя']}!🤝\n\n"
                f"🕋 Біз УМРАҒА жолдама ұтыс ойынын өткіземіз!\n"
                f"🏆 Ұтысқа қатысу үшін тапсырыстар орындау қажет.\n"
                f"🎟 Әрбір 100 орындалған тапсырысқа = 1 купон.\n\n"
                f"📅 Мына кезеңдерде тапсырыстарды орындау қажет болды:\n"
                f"21.02.2025 - 28.02.2025\n"
                f"01.03.2025 - 07.03.2025\n\n"
                f"Сізде {user_data['Количество заказов']} тапсырыс орындалғандықтан, сізде {user_data['Количество купонов']} купон бар.\n"
                f"Сіздің купон сандарыңыз: {user_data['Номера купонов']}.\n\n"
                f"Купондар тек ватсап желісіне ғана жіберіледі 👍\n"
                f"Егер сұрақтарыңыз болса немесе көмек қажет болса, бізге хабарласыңыз:\n"
                f"📞 +7 777 777 65 00\n\n"
                f"Құрметпен, \"Автопартнер\" таксопаркі!")

# Функция для второго сообщения (когда ВУ номер не найден)
def generate_not_found_message(language):
    if language == "ru":
        return ("Здравствуйте, уважаемый водитель!🤝\n\n"
                "Вашего ВУ номера нет в нашей базе. Это означает, что вы ещё не выполнили 100 заказов.\n\n"
                "🕋 Мы проводим розыгрыш путёвки в УМРУ!\n"
                "🏆 За каждые 100 выполненных заказов = 1 купон.\n\n"
                "📅 Заказы нужно было выполнять в следующие периоды:\n"
                "21.02.2025 - 28.02.2025\n"
                "01.03.2025 - 07.03.2025\n\n"
                "Ещё есть время! Выполняйте заказы, и мы добавим вас в список участников! 💪\n\n"
                "Если у вас есть вопросы или нужна помощь, свяжитесь с нами:\n"
                "📞 +7 777 777 65 00 (WhatsApp)\n\n"
                "С уважением, таксопарк \"Автопартнёр\"!")
    elif language == "kz":
        return ("Сәлеметсіз бе, Құрметті жүргізуші!🤝\n\n"
                "Сіздің ВУ нөміріңіз қазіргі уақытта біздің базада жоқ. Бұл сіз әлі 100 тапсырысты орындамағаныңызды білдіреді.\n\n"
                "🕋 Біз УМРАҒА жолдама ұтыс ойынын өткіземіз!\n"
                "🏆 Ұтысқа қатысу үшін әрбір 100 орындалған тапсырыстан 1 купон беріледі.\n\n"
                "📅 Мына кезеңдерде тапсырыстарды орындау қажет болды:\n"
                "21.02.2025 - 28.02.2025\n"
                "01.03.2025 - 07.03.2025\n\n"
                "Әлі де уақыт бар! Тапсырыстарыңызды орындаңыз және біз сіздің атыңызды тізімге қосуды күтеміз! 💪\n\n"
                "Егер сұрақтарыңыз болса немесе көмек қажет болса, бізге хабарласыңыз:\n"
                "📞 +7 777 777 65 00 (WhatsApp)\n\n"
                "Құрметпен, \"Автопартнер\" таксопаркі!")

# Проверка времени активности пользователей
async def check_user_activity(context: ContextTypes.DEFAULT_TYPE) -> None:
    current_time = datetime.now()
    for chat_id, last_activity in list(user_last_activity.items()):
        if current_time - last_activity > timedelta(minutes=15):  # Если пользователь был неактивен 15 минут
            keyboard = [[InlineKeyboardButton("Начать сначала", callback_data="restart")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await context.bot.send_message(chat_id, "Вы долго не были активны. Нажмите 'Начать сначала', чтобы продолжить.", reply_markup=reply_markup)
                del user_last_activity[chat_id]  # Удаляем пользователя из словаря
            except Exception as e:
                print(f"Ошибка при отправке сообщения: {e}")

                # Обработка команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_russian")],
        [InlineKeyboardButton("🇰🇿 Қазақша", callback_data="lang_kazakh")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите язык / Тілді таңдаңыз:", reply_markup=reply_markup)

# Установка языка
async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id

    if query.data == "lang_russian":
        user_languages[chat_id] = "ru"
        await query.edit_message_text("Вы выбрали русский язык.")
        await context.bot.send_message(
            chat_id=chat_id,
            text=messages["start"]["ru"],
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Узнать о купонах", callback_data="check_coupons")],
                [InlineKeyboardButton("Наш WhatsApp", url="https://wa.me/77777776500")],
                [InlineKeyboardButton("Помощь", callback_data="help")]
            ])
        )
    elif query.data == "lang_kazakh":
        user_languages[chat_id] = "kz"
        await query.edit_message_text("Сіз қазақ тілін таңдадыңыз.")
        await context.bot.send_message(
            chat_id=chat_id,
            text=messages["start"]["kz"],
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Купондарды білу", callback_data="check_coupons")],
                [InlineKeyboardButton("Біздің WhatsApp", url="https://wa.me/77777776500")],
                [InlineKeyboardButton("Көмек", callback_data="help")]
            ])
        )

# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    user_last_activity[chat_id] = datetime.now()  # Обновляем время активности
    language = user_languages.get(chat_id, "ru")  # По умолчанию русский язык
    user_message = update.message.text.strip()

    # Проверка формата ВУ (содержит буквы и цифры)
    vu_pattern = re.compile(r'^(?=.*[A-Za-z])(?=.*\d).+$')

    if vu_pattern.match(user_message):  # Если формат сообщения соответствует номеру ВУ
        user_data = find_data_by_vu(user_message)
        if user_data:
            response = generate_message(user_data, language)
            await update.message.reply_text(response)
        else:
            response = generate_not_found_message(language)
            await update.message.reply_text(response)
    else:
        # Сообщение для текста, который не является номером ВУ
        keyboard = [
            [InlineKeyboardButton("Узнать о купонах", callback_data="check_coupons")],
            [InlineKeyboardButton("Наш WhatsApp", url="https://wa.me/77777776500")],
            [InlineKeyboardButton("Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(messages["unknown_request"][language], reply_markup=reply_markup)

# Обработка кнопок
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id
    language = user_languages.get(chat_id, "ru")  # По умолчанию русский язык

    if query.data == "check_coupons":
        await query.message.reply_text(messages["enter_vu"][language])
    elif query.data == "help":
        await query.message.reply_text(messages["help"][language])

async def check_user_activity(context: ContextTypes.DEFAULT_TYPE) -> None:
    current_time = datetime.now()
    for chat_id, last_activity in list(user_last_activity.items()):
        if current_time - last_activity > timedelta(minutes=15):
            keyboard = [[InlineKeyboardButton("Начать сначала", callback_data="restart")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await context.bot.send_message(chat_id, "Вы долго не были активны. Нажмите 'Начать сначала', чтобы продолжить.", reply_markup=reply_markup)
                del user_last_activity[chat_id]  # Удаляем пользователя из словаря
            except Exception as e:
                print(f"Ошибка при отправке сообщения для {chat_id}: {e}")


# Запуск бота
def main():
    # Создаём приложение с поддержкой JobQueue
    application = Application.builder().token("7870902950:AAHXNVhxl5x_is-jvCN1Zq6eklPFjEpjvqM").build()

    # Проверяем, что JobQueue корректно инициализирована
    if not application.job_queue:
        print("Ошибка: JobQueue не настроена!")
        return

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(set_language, pattern="lang_.*"))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запуск фоновой задачи
    application.job_queue.run_repeating(check_user_activity, interval=60)  # Добавляем задачу каждые 60 секунд

    # Запуск Polling
    application.run_polling()

if __name__ == "__main__":
    main()

