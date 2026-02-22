import os
import logging
from datetime import timezone, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
CHAT_ID = (os.getenv("CHAT_ID") or "").strip()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# ───────────────────────────── 스케줄 메시지 정의 ─────────────────────────────

DAILY_ENGLISH = (
    "🗣 영어 회화 시간이에요!\n"
    "오늘의 영어 한 마디, Gemini Gems에서 시작해볼까요?\n"
    "매일 조금씩이 쌓여서 큰 변화가 돼요 💪"
)

DAILY_HEALTH = (
    "💚 건강 기록 시간이에요!\n"
    "오늘 뭐 먹었어요? 몸 상태는요? 잠은 잘 잤어요?\n"
    "30초면 충분해요, 오늘 하루 나를 돌아봐요 🌿"
)

DAILY_READING = (
    "📚 독서 시간이에요!\n"
    "오늘 딱 10분만 책 펼쳐볼까요?\n"
    "Claude 독서 파트너가 기다리고 있어요 🕯"
)

# ───────────────────────────── 스케줄 전송 ─────────────────────────────

_app: Optional[Application] = None


async def _send_message(message: str):
    """환경변수에 설정된 CHAT_ID로 메시지 전송"""
    if not _app or not CHAT_ID:
        logger.warning("CHAT_ID가 설정되지 않아 메시지를 보낼 수 없습니다.")
        return
    try:
        await _app.bot.send_message(chat_id=int(CHAT_ID), text=message)
        logger.info(f"스케줄 메시지 전송 완료: chat_id={CHAT_ID}")
    except Exception as e:
        logger.error(f"스케줄 메시지 전송 실패 (chat_id={CHAT_ID}): {e}")


async def job_english():
    await _send_message(DAILY_ENGLISH)


async def job_health():
    await _send_message(DAILY_HEALTH)


async def job_reading():
    await _send_message(DAILY_READING)


# ───────────────────────────── 핸들러 ─────────────────────────────

async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    await update.message.reply_text(
        f"✅ 알림 등록 완료!\n\n"
        f"당신의 chat_id: {chat_id}\n\n"
        f"Railway 배포 시 이 값을 CHAT_ID 환경변수에 입력하세요.",
    )


async def cmd_status(update: Update, _: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if CHAT_ID and str(chat_id) == CHAT_ID:
        await update.message.reply_text(
            "🔔 알림 활성 상태\n\n"
            "⏰ 스케줄 (한국 시간 KST):\n"
            "• 평일 07:30 — 📚 독서\n"
            "• 평일 07:50 — 🗣 영어 회화\n"
            "• 매일 19:00 — 💚 건강 기록\n"
            "• 주말 22:00 — 📚 독서"
        )
    else:
        await update.message.reply_text(
            f"🔕 알림 비활성 상태\n\n"
            f"환경변수 CHAT_ID에 `{chat_id}` 를 설정해주세요.",
            parse_mode="Markdown",
        )


# ───────────────────────────── 스케줄러 초기화 ─────────────────────────────

async def post_init(application: Application):
    """Application 시작 후 스케줄러 설정"""
    global _app
    _app = application

    scheduler = AsyncIOScheduler()

    # 평일 오전 7:50 KST — 영어 회화 (월~금)
    scheduler.add_job(job_english, CronTrigger(day_of_week="mon-fri", hour=7, minute=50, timezone=KST), id="daily_english")

    # 매일 오후 7:00 KST — 건강 기록
    scheduler.add_job(job_health, CronTrigger(hour=19, minute=0, timezone=KST), id="daily_health")

    # 평일 오전 7:30 KST — 독서 (월~금)
    scheduler.add_job(job_reading, CronTrigger(day_of_week="mon-fri", hour=7, minute=30, timezone=KST), id="weekday_reading")

    # 주말 오후 10:00 KST — 독서 (토~일)
    scheduler.add_job(job_reading, CronTrigger(day_of_week="sat,sun", hour=22, minute=0, timezone=KST), id="weekend_reading")

    scheduler.start()
    logger.info("스케줄러 시작 완료 (KST 기준)")
    if CHAT_ID:
        logger.info(f"알림 대상 CHAT_ID: {CHAT_ID}")
    else:
        logger.warning("CHAT_ID 미설정 — /start 로 chat_id를 확인하세요")


# ───────────────────────────── 메인 ─────────────────────────────

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise EnvironmentError("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.\n.env 파일을 확인하세요.")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))

    logger.info("알림 봇 시작!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
