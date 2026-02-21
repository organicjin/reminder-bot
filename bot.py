import os
import json
import logging
from datetime import timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# ───────────────────────────── chat_id 관리 ─────────────────────────────

CHAT_IDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_ids.json")
registered_chat_ids: set[int] = set()


def _load_chat_ids():
    global registered_chat_ids
    try:
        with open(CHAT_IDS_FILE) as f:
            registered_chat_ids = set(json.load(f))
        logger.info(f"저장된 chat_id {len(registered_chat_ids)}개 로드")
    except (FileNotFoundError, json.JSONDecodeError):
        registered_chat_ids = set()


def _save_chat_ids():
    with open(CHAT_IDS_FILE, "w") as f:
        json.dump(sorted(registered_chat_ids), f)


def _register_chat_id(chat_id: int) -> bool:
    """chat_id 등록. 새로 추가되면 True 반환."""
    if chat_id in registered_chat_ids:
        return False
    registered_chat_ids.add(chat_id)
    _save_chat_ids()
    logger.info(f"새 chat_id 등록: {chat_id}")
    return True


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

WEEKLY_REVIEW = (
    "📝 주간 리뷰 시간이에요!\n"
    "이번 한 주 어땠어요? 잘한 것, 아쉬운 것, 다음 주 다짐까지.\n"
    "Claude 주간 리뷰 프로젝트에서 이번 주를 함께 돌아봐요 🌙"
)

# ───────────────────────────── 스케줄 전송 ─────────────────────────────

# Application 참조 (스케줄러 콜백에서 사용)
_app: Application | None = None


async def _send_to_all(message: str):
    """등록된 모든 chat_id에 메시지 전송"""
    if not _app or not registered_chat_ids:
        return
    for chat_id in list(registered_chat_ids):
        try:
            await _app.bot.send_message(chat_id=chat_id, text=message)
            logger.info(f"스케줄 메시지 전송 완료: chat_id={chat_id}")
        except Exception as e:
            logger.error(f"스케줄 메시지 전송 실패 (chat_id={chat_id}): {e}")


async def job_english():
    await _send_to_all(DAILY_ENGLISH)


async def job_health():
    await _send_to_all(DAILY_HEALTH)


async def job_reading():
    await _send_to_all(DAILY_READING)


async def job_weekly_review():
    await _send_to_all(WEEKLY_REVIEW)


# ───────────────────────────── 핸들러 ─────────────────────────────

async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    is_new = _register_chat_id(chat_id)

    if is_new:
        await update.message.reply_text(
            "✅ 알림 등록 완료!\n\n"
            "⏰ 매일 받게 될 알림:\n"
            "• 오전 9:30 — 🗣 영어 회화\n"
            "• 오후 7:00 — 💚 건강 기록\n"
            "• 오후 10:00 — 📚 독서\n"
            "• 일요일 오후 7:00 — 📝 주간 리뷰\n\n"
            "알림을 끄려면 /stop 을 입력하세요."
        )
    else:
        await update.message.reply_text(
            "이미 알림이 등록되어 있어요! 😊\n"
            "알림을 끄려면 /stop 을 입력하세요."
        )


async def cmd_stop(update: Update, _: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in registered_chat_ids:
        registered_chat_ids.discard(chat_id)
        _save_chat_ids()
        await update.message.reply_text("🔕 알림이 해제되었습니다.\n다시 받으려면 /start 를 입력하세요.")
    else:
        await update.message.reply_text("등록된 알림이 없습니다.\n/start 로 등록해주세요.")


async def cmd_status(update: Update, _: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in registered_chat_ids:
        await update.message.reply_text(
            "🔔 알림 활성 상태\n\n"
            "⏰ 스케줄 (한국 시간 KST):\n"
            "• 매일 09:30 — 🗣 영어 회화\n"
            "• 매일 19:00 — 💚 건강 기록\n"
            "• 매일 22:00 — 📚 독서\n"
            "• 일요일 19:00 — 📝 주간 리뷰"
        )
    else:
        await update.message.reply_text("🔕 알림 비활성 상태\n/start 로 등록해주세요.")


# ───────────────────────────── 스케줄러 초기화 ─────────────────────────────

async def post_init(application: Application):
    """Application 시작 후 스케줄러 설정"""
    global _app
    _app = application
    _load_chat_ids()

    scheduler = AsyncIOScheduler()

    # 매일 오전 9:30 KST — 영어 회화
    scheduler.add_job(job_english, CronTrigger(hour=9, minute=30, timezone=KST), id="daily_english")

    # 매일 오후 7:00 KST — 건강 기록
    scheduler.add_job(job_health, CronTrigger(hour=19, minute=0, timezone=KST), id="daily_health")

    # 매일 오후 10:00 KST — 독서
    scheduler.add_job(job_reading, CronTrigger(hour=22, minute=0, timezone=KST), id="daily_reading")

    # 매주 일요일 오후 7:00 KST — 주간 리뷰
    scheduler.add_job(job_weekly_review, CronTrigger(day_of_week="sun", hour=19, minute=0, timezone=KST), id="weekly_review")

    scheduler.start()
    logger.info("스케줄러 시작 완료 (KST 기준)")
    logger.info(f"등록된 chat_id: {len(registered_chat_ids)}개")


# ───────────────────────────── 메인 ─────────────────────────────

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise EnvironmentError("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.\n.env 파일을 확인하세요.")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("status", cmd_status))

    logger.info("알림 봇 시작!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
