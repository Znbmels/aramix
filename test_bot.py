import pytest
from unittest.mock import Mock, AsyncMock
from telegram import Update, Message
from telegram.ext import CallbackContext
from bot import text_handler  # Импортируем твою функцию обработчика

@pytest.mark.asyncio
async def test_text_handler():
    update = Mock(spec=Update)
    update.message = Mock(spec=Message)
    update.message.text = "Тестовое сообщение"
    update.message.reply_text = AsyncMock()

    context = Mock(spec=CallbackContext)
    context.user_data = {}

    await text_handler(update, context)

    update.message.reply_text.assert_called_once()
