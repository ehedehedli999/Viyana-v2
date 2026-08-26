import os
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import openai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "123456")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

client = openai.OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)

# OYUNCU ISIMLERI VE TELEGRAM ID MAPING (Elle etiket yazmana gerek kalmaz)
# Isimler: Telegram ID
PLAYERS = {
    "ehed": "123456789",
    "sabina": "987654321",
    "eda": "112233445",
    "şura": "556677889",
    "harun": "998877665",
    "şahin": "443322110",
    "vasya": "667788990"
}

bot_state = {
    "is_active": False,
    "target": "Belirtilmedi",
    "interval": 20,
    "attackers": [],
    "defenders": [],
    "authenticated_admins": set(),
    "awaiting_ai_input": set()
}

timer_task = None

SYSTEM_PROMPT = f"""
Sen VIYANA V3 Savaş Koordinasyon Yapay Zekasısın.
Admin sana sesli veya yazılı olarak oyuncu isimlerini ve talimat verecek.

Oyuncu Listesi ve ID'leri:
{PLAYERS}

Görevlerin:
1. Adminin söylediği isimleri tespit et.
2. İsimleri Telegram etiket yapısına dönüştür: [OyuncuAdı](tg://user?id=OYUNCU_ID)
3. Duyuru grubunda paylaşılacak sert, otoriter ve net bir savaş mesajı oluştur.
"""

def get_admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("⚔️ Savaşı Başlat", callback_data="start_war"),
         InlineKeyboardButton("🛑 Savaşı Bitir", callback_data="stop_war")],
        [InlineKeyboardButton("🤖 AI Talimat Ver", callback_data="ai_instruction"),
         InlineKeyboardButton("📊 Durum Raporu", callback_data="status_report")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👑 VIYANA V3 Botu Aktif.")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if update.message.chat.type != "private":
        await update.message.reply_text("⚠️ Admin paneline sadece DM'den ulaşabilirsiniz.")
        return

    if user_id in bot_state["authenticated_admins"]:
        await update.message.reply_text("👑 **VIYANA V3 Admin Paneli**", reply_markup=get_admin_keyboard(), parse_mode="Markdown")
    else:
        await update.message.reply_text("🔑 Lütfen Admin şifresini giriniz:")

async def process_ai_with_nvidia(prompt: str) -> str:
    models = ["meta/llama-3.3-70b-instruct", "nvidia/llama-3.1-nemotron-70b-instruct"]
    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=1024
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"Model hatası ({model}): {e}")
            continue
    return "⚠️ AI yanıt üretemedi, tekrar deneyin."

async def transcribe_voice(file_path: str) -> str:
    """Ses kaydını metne dönüştürür (Whisper API)"""
    try:
        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="nvidia/neva-22b", # Veya openai/whisper-large-v3
                file=audio_file
            )
            return transcript.text
    except Exception as e:
        logger.error(f"Ses işleme hatası: {e}")
        return None

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in bot_state["authenticated_admins"]:
        await query.message.reply_text("⚠️ Oturum süreniz dolmuş. /admin yazın.")
        return

    if query.data == "start_war":
        bot_state["is_active"] = True
        await query.message.reply_text("🟢 Savaş modu başlatıldı.")
        if GROUP_CHAT_ID:
            await context.bot.send_message(chat_id=GROUP_CHAT_ID, text="🚨 **SAVAŞ BAŞLADI!**", parse_mode="Markdown")

    elif query.data == "stop_war":
        bot_state["is_active"] = False
        await query.message.reply_text("🔴 Savaş modu durduruldu.")

    elif query.data == "ai_instruction":
        bot_state["awaiting_ai_input"].add(user_id)
        await query.message.reply_text("🎙️ **Sesli Mesaj veya Metin Gönderin:**\nÖrn: *'Ehed ve Şahin saldırıda, Sabina savunmada.'*")

async def handle_private_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if update.message.chat.type != "private":
        return

    # Şifre Doğrulama
    if user_id not in bot_state["authenticated_admins"]:
        if update.message.text == ADMIN_PASSWORD:
            bot_state["authenticated_admins"].add(user_id)
            await update.message.reply_text("✅ Şifre Doğrulandı!", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text("❌ Hatalı şifre.")
        return

    # AI Talimatı Bekleniyorsa (Ses veya Metin)
    if user_id in bot_state["awaiting_ai_input"]:
        bot_state["awaiting_ai_input"].remove(user_id)
        prompt_text = ""

        # Eğer Sesli Mesaj Geldiyse
        if update.message.voice:
            await update.message.reply_text("🎙️ Ses kaydınız çözümleniyor...")
            voice_file = await context.bot.get_file(update.message.voice.file_id)
            file_path = "voice_msg.ogg"
            await voice_file.download_to_drive(file_path)
            
            prompt_text = await transcribe_voice(file_path)
            if os.path.exists(file_path):
                os.remove(file_path)

            if not prompt_text:
                await update.message.reply_text("❌ Ses anlaşılamadı, lütfen yazılı gönderin.")
                return
            await update.message.reply_text(f"🗣️ **Algılanan Ses:** *\"{prompt_text}\"*")
        else:
            prompt_text = update.message.text

        # AI İşleme ve Gruba Gönderme
        await update.message.reply_text("⏳ Talimat hazırlanıyor ve Viyana Duyuru grubuna aktarılıyor...")
        ai_response = await process_ai_with_nvidia(prompt_text)
        await update.message.reply_text(f"🤖 **Yayınlanan Duyuru:**\n\n{ai_response}", parse_mode="Markdown")

        if GROUP_CHAT_ID:
            try:
                await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=ai_response, parse_mode="Markdown")
                await update.message.reply_text("🚀 **Duyuru gruba yayınlandı!**")
            except Exception as e:
                await update.message.reply_text(f"⚠️ Gruba atılamadı: {e}")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    # Hem METİN hem de SESLİ MESAJ (VOICE) filtreleri eklendi:
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.TEXT | filters.VOICE) & ~filters.COMMAND, handle_private_messages))

    logger.info("VIYANA V3 Bot Başlatılıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
