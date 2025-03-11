import pandas as pd
import re
import asyncio
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
from telegram.error import NetworkError, RetryAfter, TimedOut
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Настройка логирования
handler = RotatingFileHandler("bot.log", maxBytes=5000000, backupCount=3)  # 5 MB на лог-файл, сохраняется 3 копии
logging.basicConfig(level=logging.INFO, handlers=[handler],
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Уведомление администратора
async def notify_admin(context: ContextTypes.DEFAULT_TYPE, message: str) -> None:
    admin_id = 8025906752  # Укажите Telegram ID администратора
    try:
        await context.bot.send_message(chat_id=admin_id, text=message)
    except Exception as e:
        logging.error(f"Не удалось отправить сообщение администратору: {e}")

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

if not BOT_TOKEN:
    logging.critical("Токен бота не найден! Проверьте файл .env.")
    exit(1)

# Загрузка данных из Excel
try:
    data = pd.read_excel("result_with_ids.xlsx")
    logging.info("Данные успешно загружены из файла result_with_ids.xlsx")
except FileNotFoundError:
    logging.error("Файл result_with_ids.xlsx не найден. Бот продолжит работать с пустой базой данных.")
    data = pd.DataFrame()

# Переменные для хранения информации о пользователях
user_languages = {}
user_last_activity = {}
user_requests = {}

# Функция для поиска данных по ВУ номеру
def find_data_by_vu(vu_number):
    try:
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
            logging.warning(f"Данные для ВУ номера {vu_number} не найдены.")
            return None
    except Exception as e:
        logging.error(f"Ошибка при поиске данных по ВУ: {e}")
        return None

# Лимит запросов от пользователей
def is_request_allowed(user_id):
    current_time = datetime.now()
    if user_id not in user_requests:
        user_requests[user_id] = current_time
        return True
    elif (current_time - user_requests[user_id]).seconds > 60:  # Лимит: 1 запрос в минуту
        user_requests[user_id] = current_time
        return True
    return False

# Генерация персонального сообщения для найденного ВУ с учётом языка
def generate_message(user_data, language):
    try:
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
                    f"Егер сұрақтарыңыз болса немесе көмек қажет болса, бізге хабарласыңыз:\n"
                    f"📞 +7 777 777 65 00\n\n"
                    f"Құрметпен, \"Автопартнер\" таксопаркі!")
    except Exception as e:
        logging.error(f"Ошибка при генерации сообщения: {e}")
        return None

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
            text="Сәлеметсіз бе! Выберите опцию ниже:",
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
            text="Сәлеметсіз бе! Опцияны таңдаңыз:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Купондарды білу", callback_data="check_coupons")],
                [InlineKeyboardButton("Біздің WhatsApp", url="https://wa.me/77777776500")],
                [InlineKeyboardButton("Көмек", callback_data="help")]
            ])
        )

# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
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
            await update.message.reply_text(
                "Извините, я не совсем понимаю ваш запрос. Попробуйте использовать кнопки ниже или введите ваш ВУ номер.",
                reply_markup=reply_markup
            )
    except Exception as e:
        logging.error(f"Ошибка в handle_message: {e}")
# Обработка кнопок
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        query = update.callback_query
        chat_id = query.message.chat_id
        language = user_languages.get(chat_id, "ru")  # По умолчанию русский язык

        if query.data == "check_coupons":
            await query.message.reply_text("Введите ваш ВУ номер, чтобы узнать информацию о купонах.")
        elif query.data == "help":
            await query.message.reply_text("Если у вас есть вопросы или нужна помощь, напишите нам на WhatsApp: 📞 +7 777 777 65 00.")
    except Exception as e:
        logging.error(f"Ошибка в button_callback: {e}")

# Проверка времени активности пользователей
async def check_user_activity(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        current_time = datetime.now()
        for chat_id, last_activity in list(user_last_activity.items()):
            if current_time - last_activity > timedelta(minutes=15):  # Если пользователь был неактивен 15 минут
                keyboard = [[InlineKeyboardButton("Начать сначала", callback_data="restart")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                try:
                    await context.bot.send_message(
                        chat_id, 
                        "Вы долго не были активны. Нажмите 'Начать сначала', чтобы продолжить.", 
                        reply_markup=reply_markup
                    )
                    del user_last_activity[chat_id]  # Удаляем пользователя из словаря
                except Exception as e:
                    logging.error(f"Ошибка при отправке уведомления об активности для {chat_id}: {e}")
    except Exception as e:
        logging.error(f"Ошибка в check_user_activity: {e}")

# Наблюдатель за обновлением файла Excel
class ExcelUpdateHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith("result_with_ids.xlsx"):
            global data
            try:
                data = pd.read_excel("result_with_ids.xlsx")
                logging.info("Файл result_with_ids.xlsx обновлён и перезагружен.")
            except Exception as e:
                logging.error(f"Ошибка при обновлении данных: {e}")

def watch_excel_file():
    observer = Observer()
    event_handler = ExcelUpdateHandler()
    observer.schedule(event_handler, path=".", recursive=False)
    observer.start()
# Основная функция запуска бота
def main():
    try:
        # Создаём приложение с токеном из окружения
        application = Application.builder().token(BOT_TOKEN).build()

        # Регистрация обработчиков
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(set_language, pattern="lang_.*"))
        application.add_handler(CallbackQueryHandler(button_callback, pattern="check_coupons|help"))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Запуск наблюдателя за файлом Excel
        watch_excel_file()
        logging.info("Наблюдение за обновлением файла Excel запущено.")

        # Запуск фоновой задачи для проверки активности пользователей
        if application.job_queue:
            application.job_queue.run_repeating(check_user_activity, interval=60)  # Задача каждые 60 секунд
            logging.info("Фоновая задача для проверки активности запущена.")
        else:
            logging.warning("JobQueue не была инициализирована, фоновые задачи не будут работать.")

        # Запуск Polling с обработкой сетевых ошибок
        while True:
            try:
                logging.info("Запуск бота...")
                application.run_polling()
            except (NetworkError, RetryAfter, TimedOut) as e:
                logging.warning(f"Проблема с подключением к Telegram: {e}. Попытка переподключения...")
                continue
            except Exception as e:
                logging.critical(f"Критическая ошибка: {e}")
                context = application.bot.create_context()
                asyncio.run(notify_admin(context, f"Критическая ошибка: {e}"))  # Уведомляем администратора
                break
    except Exception as e:
        logging.critical(f"Критическая ошибка при запуске бота: {e}")
        # Создаём контекст и отправляем уведомление админу
        context = application.bot.create_context()
        asyncio.run(notify_admin(context, f"Критическая ошибка при запуске: {e}"))
        exit(1)

if __name__ == "__main__":
    main()
