import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ====== ВАЖНО ======
API_TOKEN = "8014851414:AAHxuKwYbud4feLObosWvNeW-z9q9MoCUTY"  # вставь сюда свой токен
CHANNELS = ["@freestar500", "@freebear15", "@mechtau0"]
REFERRAL_REWARD = 2
SUBSCRIBE_REWARD = 0.25
UNSUBSCRIBE_PENALTY = 0.25

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- База данных ---
conn = sqlite3.connect("bot.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS referrals (
    referrer_id INTEGER,
    friend_id INTEGER,
    PRIMARY KEY (referrer_id, friend_id)
)
""")
conn.commit()

# --- Вспомогательные функции ---
def get_balance(user_id):
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    res = cursor.fetchone()
    if res:
        return res[0]
    else:
        cursor.execute("INSERT INTO users(user_id) VALUES(?)", (user_id,))
        conn.commit()
        return 0

def update_balance(user_id, amount):
    balance = get_balance(user_id) + amount
    cursor.execute("UPDATE users SET balance=? WHERE user_id=?", (balance, user_id))
    conn.commit()
    return balance

# --- Реферальная система ---
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    user_id = message.from_user.id
    args = message.get_args()
    if args.isdigit():
        ref_id = int(args)
        if ref_id != user_id:
            cursor.execute("INSERT OR IGNORE INTO referrals(referrer_id, friend_id) VALUES(?,?)", (ref_id, user_id))
            update_balance(ref_id, REFERRAL_REWARD)
            await message.answer(f"Тебя пригласил пользователь {ref_id}. Он получил +{REFERRAL_REWARD}⭐!")
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n"
        f"Твоя реферальная ссылка:\n"
        f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    )

# --- Задания (подписка на каналы) ---
def check_sub_button():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Проверить подписку", callback_data="check_subs"))
    return kb

@dp.message_handler(commands=["tasks"])
async def send_tasks(message: types.Message):
    text = "Подпишись на каналы и получай ⭐ (по 0.25 за каждый):\n\n"
    for ch in CHANNELS:
        text += f"➡️ {ch}\n"
    text += "\nПосле подписки нажми кнопку ниже 👇"
    await message.answer(text, reply_markup=check_sub_button())

@dp.callback_query_handler(lambda c: c.data=="check_subs")
async def check_subs(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    balance = get_balance(user_id)
    result_text = "📋 Проверка подписки:\n"
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status in ["member", "administrator", "creator"]:
                balance = update_balance(user_id, SUBSCRIBE_REWARD)
                result_text += f"✅ Подписка на {channel} (+{SUBSCRIBE_REWARD}⭐)\n"
            else:
                balance = update_balance(user_id, -UNSUBSCRIBE_PENALTY)
                result_text += f"❌ Нет подписки на {channel} (-{UNSUBSCRIBE_PENALTY}⭐)\n"
        except:
            result_text += f"⚠️ Не удалось проверить {channel}\n"
    result_text += f"\n💰 Твой баланс: {balance} ⭐"
    await callback_query.message.answer(result_text)

# --- Автоматическая проверка отписок ---
scheduler = AsyncIOScheduler()
async def daily_check():
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    for user in users:
        user_id = user[0]
        for channel in CHANNELS:
            try:
                member = await bot.get_chat_member(channel, user_id)
                if member.status not in ["member", "administrator", "creator"]:
                    balance = update_balance(user_id, -UNSUBSCRIBE_PENALTY)
                    await bot.send_message(user_id,
                        f"⚠️ Мы заметили, что вы отписались от {channel}.\n"
                        f"С вашего баланса списано -{UNSUBSCRIBE_PENALTY}⭐")
            except:
                pass

scheduler.add_job(daily_check, "cron", hour=20, minute=0)  # раз в день в 20:00
scheduler.start()

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)