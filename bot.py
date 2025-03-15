import os
import logging
import httpx
import speech_recognition as sr
from pydub import AudioSegment
import aiomysql
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Константы для CRM SuiteCRM
SUITECRM_URL = "http://crm.aramax.kz:8080"  # URL сервера CRM
SUITECRM_AUTH_ENDPOINT = f"{SUITECRM_URL}/legacy/Api/access_token"  # Эндпоинт авторизации
SUITECRM_TASKS_ENDPOINT = f"{SUITECRM_URL}/legacy/Api/V8/module"  # Эндпоинт создания задач
CLIENT_ID = "edafaa02-5599-f449-4348-67695b4ffad8"  # OAuth2 client_id
CLIENT_SECRET = "VtpZM*GY5mLQ3A60"  # OAuth2 client_secret

# Параметры подключения к базе данных
DB_CONFIG = {
    "host": "crm.aramax.kz",
    "port": 3306,
    "user": "bn_suitecrm",
    "password": "bitnami123",
    "db": "aramax",
}

def normalize_phone(phone: str) -> str:
    """
    Нормализует номер телефона (удаляет пробелы, скобки и другие символы, но оставляет +).
    """
    return phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

async def get_db_connection():
    """
    Устанавливает соединение с базой данных.
    """
    try:
        pool = await aiomysql.create_pool(**DB_CONFIG)
        logger.info("Подключение к базе данных успешно установлено.")
        return pool
    except Exception as e:
        logger.error(f"Ошибка при подключении к базе данных: {e}")
        raise

async def check_phone_in_db(phone: str) -> bool:
    """
    Проверяет, есть ли номер телефона в базе данных.
    """
    normalized_phone = normalize_phone(phone)
    logger.info(f"Нормализованный номер телефона: {normalized_phone}")
    pool = await get_db_connection()
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "SELECT id FROM u_bot WHERE u_number = %s"
                logger.info(f"Выполняется запрос: {query} с параметром {normalized_phone}")
                await cursor.execute(query, (normalized_phone,))
                result = await cursor.fetchone()
                if result:
                    logger.info(f"Запись для номера {normalized_phone} найдена: {result}")
                    return True
                else:
                    logger.warning(f"Запись для номера {normalized_phone} не найдена.")
                    return False
    except Exception as e:
        logger.error(f"Ошибка при проверке номера в базе данных: {e}")
        return False
    finally:
        pool.close()
        await pool.wait_closed()

async def get_assigned_user_id_from_db(phone: str) -> str:
    """
    Получает ID исполнителя из базы данных на основе номера телефона.
    Если исполнитель не найден, возвращает дефолтного исполнителя.
    """
    normalized_phone = normalize_phone(phone)
    pool = await get_db_connection()
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "SELECT u_id_crm FROM u_bot WHERE u_number = %s"  # Исправлено название столбца
                logger.info(f"Выполняется запрос: {query} с параметром {normalized_phone}")
                await cursor.execute(query, (normalized_phone,))
                result = await cursor.fetchone()
                if result:
                    logger.info(f"ID исполнителя для номера {normalized_phone}: {result[0]}")
                    return result[0]
                else:
                    logger.warning(f"Запись для номера {normalized_phone} не найдена в таблице u_bot. Используем дефолтного исполнителя.")
                    return "859aa2b9-3486-0bdd-c971-66e58f21cd76"  # Дефолтный исполнитель
    except Exception as e:
        logger.error(f"Ошибка при получении ID исполнителя: {e}")
        return "859aa2b9-3486-0bdd-c971-66e58f21cd76"  # Дефолтный исполнитель в случае ошибки
    finally:
        pool.close()
        await pool.wait_closed()

async def get_access_token() -> str:
    """
    Получает access_token для авторизации в CRM SuiteCRM через OAuth2 client_credentials.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SUITECRM_AUTH_ENDPOINT,
                data={
                    "grant_type": "client_credentials",
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                },
            )
            logger.info(f"Статус ответа: {response.status_code}")
            logger.info(f"Тело ответа: {response.text}")
            if response.status_code == 200:
                return response.json().get("access_token")
            else:
                logger.error(f"Ошибка авторизации в CRM: {response.text}")
                raise Exception("Не удалось получить access_token.")
    except Exception as e:
        logger.error(f"Ошибка при получении access_token: {e}")
        raise

async def create_task_in_crm(phone: str, task_text: str, assigned_user_id: str) -> bool:
    """
    Создаёт задачу в CRM SuiteCRM.
    """
    try:
        # Получаем access_token
        access_token = await get_access_token()

        # Формируем заголовки
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Формируем тело запроса
        payload = {
            "data": {
                "type": "Task",  # Обратите внимание: "Task" (не "Tasks")
                "attributes": {
                    "name": task_text,
                    "assigned_user_id": assigned_user_id,
                    "date_start": datetime.now().strftime("%Y-%m-%d"),
                    "priority": "Medium",
                    "status": "Not Started",  # Добавляем статус задачи
                    "date_due_flag": "0",     # Флаг даты завершения (0 = нет)
                    "date_start_flag": "0",   # Флаг даты начала (0 = нет)
                },
            }
        }

        # Отправляем POST-запрос
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SUITECRM_TASKS_ENDPOINT,  # Правильный эндпоинт
                headers=headers,
                json=payload,
            )

            # Логируем статус и тело ответа
            logger.info(f"Статус ответа: {response.status_code}")
            logger.info(f"Тело ответа: {response.text}")

            # Проверяем успешность запроса
            if response.status_code == 201:
                logger.info(f"Задача успешно создана в CRM: {task_text}")
                return True
            else:
                logger.error(f"Ошибка при создании задачи в CRM: {response.text}")
                return False
    except Exception as e:
        logger.error(f"Ошибка при создании задачи в CRM: {e}")
        return False

def convert_voice_to_text(ogg_path: str) -> str:
    """
    Преобразует голосовое сообщение в текст.
    """
    wav_path = ogg_path.replace(".ogg", ".wav")
    AudioSegment.from_file(ogg_path).export(wav_path, format="wav")
    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_path) as source:
        audio_data = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio_data, language="ru-RU")
    except sr.UnknownValueError:
        text = ""
    except sr.RequestError:
        text = ""
    os.remove(wav_path)
    return text

async def send_inline_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отправляет inline-меню с кнопками.
    """
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Создать задачу голосом", callback_data="voice_task")],
            [InlineKeyboardButton("Создать задачу текстом", callback_data="text_task")]
        ]
    )

    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=keyboard,
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает команду /start.
    """
    await update.message.reply_text("Привет! Введите, пожалуйста, свой номер телефона.")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает текстовые сообщения.
    """
    text = update.message.text.strip()

    # Если пользователь выбрал "Создать задачу текстом"
    if context.user_data.get("task_mode") == "text":
        phone = context.user_data.get("phone", "")
        if not phone:
            await update.message.reply_text("Сначала введите номер телефона командой /start.")
            return

        if not text:
            await update.message.reply_text("Текст задачи не может быть пустым. Попробуйте ещё раз.")
            return

        # Получаем ID исполнителя из базы данных
        assigned_user_id = await get_assigned_user_id_from_db(phone)
        if not assigned_user_id:
            await update.message.reply_text("Не удалось найти исполнителя для вашего номера.")
            return

        created = await create_task_in_crm(phone, text, assigned_user_id)
        if created:
            await update.message.reply_text(f"Задача - \"{text}\" успешно добавлена в CRM.")
            await send_inline_menu(update, context)  # Отправляем меню после добавления задачи
        else:
            await update.message.reply_text("Ошибка при создании задачи. Попробуйте позже.")

        context.user_data["task_mode"] = None
        return

    # Проверяем, является ли текст номером телефона
    normalized_phone = normalize_phone(text)
    logger.info(f"Нормализованный номер телефона: {normalized_phone}")

    if normalized_phone.replace("+", "").isdigit() and len(normalized_phone.replace("+", "")) >= 10:
        if await check_phone_in_db(normalized_phone):
            context.user_data["phone"] = normalized_phone  # Сохраняем номер телефона в контексте
            logger.info(f"Номер телефона {normalized_phone} зарегистрирован в базе данных.")

            # Отправляем inline-меню после проверки номера
            await send_inline_menu(update, context)
        else:
            await update.message.reply_text("Ваш номер телефона не зарегистрирован.")
    else:
        await update.message.reply_text(
            "Пожалуйста, введите корректный номер телефона (не меньше 10 цифр)."
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает нажатия на inline-кнопки.
    """
    query = update.callback_query
    await query.answer()

    if query.data == "voice_task":
        context.user_data["task_mode"] = "voice"
        await query.edit_message_text("Отправьте голосовое сообщение.")
    elif query.data == "text_task":
        context.user_data["task_mode"] = "text"
        await query.edit_message_text("Введите текст задачи.")

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает голосовые сообщения.
    """
    if update.message.voice:
        if context.user_data.get("task_mode") != "voice":
            await update.message.reply_text("Сначала выберите «Создать задачу голосом».")
            return

        phone = context.user_data.get("phone", "")
        if not phone:
            await update.message.reply_text("Сначала введите номер телефона.")
            return

        file = await context.bot.get_file(update.message.voice.file_id)
        local_ogg = f"voice_{update.message.from_user.id}.ogg"
        await file.download_to_drive(custom_path=local_ogg)

        recognized_text = convert_voice_to_text(local_ogg)
        os.remove(local_ogg)

        if not recognized_text:
            await update.message.reply_text("Не удалось распознать голос. Попробуйте ещё раз.")
            return

        # Получаем ID исполнителя из базы данных
        assigned_user_id = await get_assigned_user_id_from_db(phone)
        if not assigned_user_id:
            await update.message.reply_text("Не удалось найти исполнителя для вашего номера.")
            return

        created = await create_task_in_crm(phone, recognized_text, assigned_user_id)
        if created:
            await update.message.reply_text(
                f"Задача - \"{recognized_text}\" успешно добавлена в CRM."
            )
            await send_inline_menu(update, context)  # Отправляем меню после добавления задачи
        else:
            await update.message.reply_text("Ошибка при создании записи. Попробуйте позже.")

        context.user_data["task_mode"] = None

def main():
    """
    Запуск бота.
    """
    application = (
        ApplicationBuilder()
        .token("7776142722:AAEK-CUbI8Zh4SYswRWLZ4XAMBDOQRYjmRU")  # Замените на ваш токен
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))  # Обработчик inline-кнопок
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(MessageHandler(filters.VOICE, voice_handler))

    application.run_polling()

if __name__ == "__main__":
    main()