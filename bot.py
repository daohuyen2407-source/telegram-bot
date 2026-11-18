import os
import asyncio
import logging
import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters,
)

# ---------- Đọc cấu hình từ .env ----------
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL", "openai/gpt-oss-20b")

if not TOKEN:
    raise SystemExit("Thiếu TELEGRAM_BOT_TOKEN trong file .env")

# ---------- Ghi log ----------
logging.basicConfig(level=logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)   # tránh lộ Token trong log
logging.getLogger("httpcore").setLevel(logging.WARNING)

log = logging.getLogger("bot")
log.setLevel(logging.INFO)
file_handler = logging.FileHandler("bot.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", "%Y-%m-%d %H:%M:%S"))
log.addHandler(file_handler)
console = logging.StreamHandler()
console.setFormatter(logging.Formatter("%(asctime)s | %(message)s", "%H:%M:%S"))
log.addHandler(console)

FALLBACK = "⚠️ Xin lỗi, hiện không gọi được API. Bạn thử lại sau nhé."

# ---------- Gọi API bên ngoài ----------
async def ask_ai(question: str) -> str:
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {AI_API_KEY}"},
            json={
                "model": AI_MODEL,
                "messages": [
                    {"role": "system", "content": "Bạn là trợ lý thân thiện, trả lời ngắn gọn bằng tiếng Việt."},
                    {"role": "user", "content": question},
                ],
                "max_tokens": 800,
            },
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"].get("content")
        return content or "Mình chưa nghĩ ra câu trả lời, bạn hỏi lại nhé."


async def get_exchange_rate() -> str:
    """Dự phòng khi chưa có key AI: API tỷ giá công khai."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
        r = await client.get("https://open.er-api.com/v6/latest/USD")
        r.raise_for_status()
        vnd = r.json()["rates"]["VND"]
        return f"(Chưa cấu hình AI) Tỷ giá hôm nay: 1 USD = {vnd:,.0f} VND"

# ---------- Handler ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 Xin chào! Mình là bot trợ lý AI.\n\n"
        "Cách dùng:\n"
        "• Gõ bất kỳ câu hỏi nào, mình sẽ trả lời bằng AI.\n"
        "• Gõ /start để xem lại hướng dẫn này."
    )
    await update.message.reply_text(text)
    log.info("USER %s: /start", update.effective_user.id)


async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    log.info("Nhận tin từ USER %s: %s", update.effective_user.id, user_text)
    answer = FALLBACK
    try:
        if AI_API_KEY:
            answer = await ask_ai(user_text)
        else:
            answer = await get_exchange_rate()
    except httpx.HTTPStatusError as e:
        log.error("Lỗi API %s: %s", e.response.status_code, e.response.text[:300])
    except Exception as e:
        log.error("Lỗi gọi API: %s: %s", type(e).__name__, e)
    await update.message.reply_text(answer)
    log.info("USER %s: %s || BOT: %s", update.effective_user.id,
             user_text.replace("\n", " "), answer[:100].replace("\n", " "))


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    log.error("Lỗi trong bot: %s: %s", type(context.error).__name__, context.error)


def main():
    asyncio.set_event_loop(asyncio.new_event_loop())
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))
    app.add_error_handler(on_error)
    print("Bot đang chạy... nhấn Ctrl+C để dừng.")
    app.run_polling()


if __name__ == "__main__":
    main()