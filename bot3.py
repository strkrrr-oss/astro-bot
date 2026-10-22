import logging
import os

from dotenv import load_dotenv
from google import genai
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

if not TELEGRAM_TOKEN:
    raise RuntimeError("Добавьте TELEGRAM_TOKEN в файл .env")

if not GEMINI_API_KEY:
    raise RuntimeError("Добавьте GEMINI_API_KEY в файл .env")

client = genai.Client(api_key=GEMINI_API_KEY)


def parse_birth_data(text: str):
    parts = text.strip().split()

    if len(parts) < 3:
        return None

    return {
        "date": parts[0],
        "time": parts[1],
        "city": " ".join(parts[2:]),
    }


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["stage"] = "birth1"
    await update.message.reply_text(
        "Привет! Отправь данные первого человека в формате:\n"
        "ДД.ММ.ГГГГ ЧЧ:ММ Город"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    stage = context.user_data.get("stage")

    if stage == "birth1":
        context.user_data["birth1"] = text
        context.user_data["stage"] = "birth2"
        await update.message.reply_text(
            "Теперь отправь данные второго человека в том же формате:"
        )
        return

    if stage != "birth2":
        await update.message.reply_text("Начни с команды /start.")
        return

    birth1 = parse_birth_data(context.user_data.get("birth1", ""))
    birth2 = parse_birth_data(text)
    context.user_data["stage"] = None

    if not birth1 or not birth2:
        await update.message.reply_text(
            "Не удалось распознать данные. Формат: ДД.ММ.ГГГГ ЧЧ:ММ Город"
        )
        return

    prompt = (
        "Сделай краткий развлекательный анализ совместимости двух людей. "
        "Уточни, что это не научная оценка.\n\n"
        f"Первый человек: {birth1}\n"
        f"Второй человек: {birth2}"
    )

    try:
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

        answer = response.text or "Модель вернула пустой ответ."

        for start_index in range(0, len(answer), 4000):
            await update.message.reply_text(
                answer[start_index:start_index + 4000]
            )

    except ServerError as e:
        logging.exception("Ошибка сервера Gemini")

        if getattr(e, "code", None) == 503:
            await update.message.reply_text(
                "Gemini сейчас перегружен. Подожди немного и попробуй снова."
            )
        else:
            await update.message.reply_text(
                "Gemini временно вернул ошибку. Попробуй позже."
            )

    except Exception:
        logging.exception("Неожиданная ошибка при запросе к Gemini")
        await update.message.reply_text(
            "Произошла ошибка. Подробности есть в терминале VS Code."
        )


def main():
    logging.basicConfig(level=logging.INFO)

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    app.run_polling()


if __name__ == "__main__":
    main()