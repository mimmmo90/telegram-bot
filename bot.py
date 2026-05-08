import asyncio
import time
from collections import defaultdict, deque

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ChatPermissions
from aiogram.enums import ChatMemberStatus

import os

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise Exception("TOKEN non impostato!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# =========================
# CONFIG DINAMICA
# =========================

config = {
    "TIME_WINDOW": 300,       # finestra foto (sec)
    "MAX_PHOTOS": 1,          # foto consentite
    "MUTE_TIME": 60,          # mute (sec)

    "MAX_SPAMS": 1,           # strike prima del ban
    "SPAM_WINDOW": 86400      # finestra strike (24h)
}

# =========================
# STORAGE
# =========================

user_photos = defaultdict(lambda: deque(maxlen=20))
user_spams = defaultdict(lambda: deque(maxlen=20))


# =========================
# ADMIN CHECK
# =========================

async def is_admin(chat_id, user_id):
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status in [
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR
    ]


# =========================
# ANTI SPAM FOTO
# =========================

@dp.message(F.photo)
async def handle_photo(message: Message):

    user_id = message.from_user.id
    chat_id = message.chat.id
    now = time.time()

    member = await bot.get_chat_member(chat_id, user_id)

    # ignora owner
    if member.status == ChatMemberStatus.CREATOR:
        return

    key = (chat_id, user_id)

    # filtra foto recenti
    recent = deque(
        [t for t in user_photos[key] if now - t <= config["TIME_WINDOW"]],
        maxlen=20
    )

    user_photos[key] = recent

    # se supera limite foto
    if len(recent) >= config["MAX_PHOTOS"]:

        try:
            await message.delete()
        except:
            pass

        # STRIKE SYSTEM
        strikes = deque(
            [t for t in user_spams[key] if now - t <= config["SPAM_WINDOW"]],
            maxlen=20
        )

        user_spams[key] = strikes
        user_spams[key].append(now)

        strike_count = len(user_spams[key])

        # BAN se troppi strike
        if strike_count > config["MAX_SPAMS"]:

            try:
                await bot.ban_chat_member(chat_id, user_id)
                await message.answer("🚫 Utente bannato per spam ripetuto.")
            except Exception as e:
                print(e)

            return

        # MUTE normale
        try:
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=int(now + config["MUTE_TIME"])
            )

            await message.answer(
                f"⛔ Spam rilevato\n"
                f"🔇 Mute: {config['MUTE_TIME']} sec\n"
                f"🚨 Strike: {strike_count}/{config['MAX_SPAMS']}"
            )

        except Exception as e:
            print(e)

        return

    # salva foto valida
    user_photos[key].append(now)


# =========================
# SET COMANDI CONFIG
# =========================

@dp.message(F.text.startswith("/setmute"))
async def set_mute(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    try:
        config["MUTE_TIME"] = int(message.text.split()[1]) * 60
        await message.answer("✅ Mute aggiornato")
    except:
        await message.answer("Uso: /setmute 5")


@dp.message(F.text.startswith("/setwindow"))
async def set_window(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    try:
        config["TIME_WINDOW"] = int(message.text.split()[1]) * 60
        await message.answer("✅ Finestra aggiornata")
    except:
        await message.answer("Uso: /setwindow 10")


@dp.message(F.text.startswith("/setmaxphotos"))
async def set_maxphotos(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    try:
        config["MAX_PHOTOS"] = int(message.text.split()[1])
        await message.answer("✅ Max foto aggiornate")
    except:
        await message.answer("Uso: /setmaxphotos 1")


@dp.message(F.text.startswith("/setmaxspam"))
async def set_maxspam(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    try:
        config["MAX_SPAMS"] = int(message.text.split()[1])
        await message.answer("✅ Max spam aggiornato")
    except:
        await message.answer("Uso: /setmaxspam 1")


@dp.message(F.text.startswith("/setspamwindow"))
async def set_spamwindow(message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    try:
        config["SPAM_WINDOW"] = int(message.text.split()[1]) * 60
        await message.answer("✅ Finestra strike aggiornata")
    except:
        await message.answer("Uso: /setspamwindow 1440")


# =========================
# CONFIG STATUS
# =========================

@dp.message(F.text == "/config")
async def show_config(message: Message):
    await message.answer(
        "⚙ CONFIG\n\n"
        f"📸 Max foto: {config['MAX_PHOTOS']}\n"
        f"⏱ Finestra: {config['TIME_WINDOW']//60} min\n"
        f"🔇 Mute: {config['MUTE_TIME']//60} min\n"
        f"🚨 Max spam: {config['MAX_SPAMS']}\n"
        f"📅 Strike window: {config['SPAM_WINDOW']//60} min"
    )


# =========================
# HELP
# =========================

@dp.message(F.text == "/help")
async def help_cmd(message: Message):

    await message.answer(
        "📖 COMANDI\n\n"

        "⚙ /setmute X → durata mute (min)\n"
        "⚙ /setwindow X → finestra controllo\n"
        "⚙ /setmaxphotos X → max foto\n\n"

        "🚨 /setmaxspam X → max mute prima ban\n"
        "🚨 /setspamwindow X → finestra strike\n\n"

        "👮 /unmute → rispondendo a utente\n"
        "📊 /config → stato sistema"
    )


# =========================
# UNMUTE
# =========================

@dp.message(F.text.startswith("/unmute"))
async def unmute(message: Message):

    if not await is_admin(message.chat.id, message.from_user.id):
        return

    if not message.reply_to_message:
        await message.answer("Rispondi a un utente.")
        return

    user_id = message.reply_to_message.from_user.id

    try:
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_photos=True,
                can_send_documents=True,
                can_send_videos=True,
                can_send_audio=True,
                can_send_voice=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_invite_users=True
            )
        )

        await message.answer("✅ Utente smutato")

    except Exception as e:
        print(e)


# =========================
# MAIN
# =========================

async def main():
    print("Bot avviato...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
