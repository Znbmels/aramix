import pytest
import pytest_asyncio 
from unittest.mock import Mock
from telegram import Update
from telegram.ext import CallbackContext, ApplicationBuilder
from bot import start, text_handler, button_handler, voice_handler  # Импортируйте ваши функции

# Фикстура для создания экземпляра бота
@pytest_asyncio.fixture
async def app():
    application = ApplicationBuilder().token("dummy_token").build()
    return application

# Тест для команды /start
@pytest.mark.asyncio
async def test_start_command(app):
    update = Update(update_id=1, message=Mock())
    update.message.reply_text = Mock()
    context = CallbackContext(application=app)

    await start(update, context)

    assert update.message.reply_text.called
    assert "Привет! Введите, пожалуйста, свой номер телефона." in update.message.reply_text.call_args[0][0]

# Тест для обработки текстового сообщения
@pytest.mark.asyncio
async def test_text_handler(app):
    update = Update(update_id=1, message=Mock())
    update.message.text = "+77089080062"
    update.message.reply_text = Mock()
    context = CallbackContext(application=app)

    await text_handler(update, context)

    assert update.message.reply_text.called
    assert "Доступ разрешён! Выберите способ создания задачи:" in update.message.reply_text.call_args[0][0]

# Тест для обработки inline-кнопок
@pytest.mark.asyncio
async def test_button_handler(app):
    update = Update(update_id=1, callback_query=Mock())
    update.callback_query.data = "text_task"
    update.callback_query.edit_message_text = Mock()
    context = CallbackContext(application=app)

    await button_handler(update, context)

    assert update.callback_query.edit_message_text.called
    assert "Введите текст задачи." in update.callback_query.edit_message_text.call_args[0][0]

# Тест для обработки голосового сообщения
@pytest.mark.asyncio
async def test_voice_handler(app):
    update = Update(update_id=1, message=Mock())
    update.message.voice = "dummy_voice"
    update.message.reply_text = Mock()
    context = CallbackContext(application=app)

    await voice_handler(update, context)

    assert update.message.reply_text.called
    assert "Задача -" in update.message.reply_text.call_args[0][0]
