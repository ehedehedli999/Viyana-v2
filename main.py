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
from groq import Groq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "123456")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

# Groq İstemcisi
groq_client = Groq(api_key=GROQ_API_KEY)

PLAYERS = {
    "ehed": "123456789",
    "sabina": "987654321",
    "eda": "112233445",
    "şura": "556677889",
    "sura": "556677889",
    "harun": "998877665",
    "şahin": "443322110",
    "sahin": "443322110",
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

SYSTEM_PROMPT = f"""
Sen VIYANA V3 Savaş Koordinasyon Yapay Zekasısın.
Admin sana sesli veya yazılı komut verecek.

Tanımlı Oyuncu Listesi ve ID'leri:
{PLAYERS}

Görevlerin:
1. Adminin mesajını analiz et. Eğer savaşla ilgili bir komutsa Saldırı ve Savunma kadrolarını ayır.
2. Metinde geçen oyuncu isimlerini tıklanabilir etiket formatına dönüştür: [OyuncuAdı](tg://user?id=OYUNCU_ID)
3. Eğer admin sadece "Nasılsın", "Merhaba" gibi sohbet mesajı attıysa, komutan edasıyla kısa ve saygılı bir cevap ver.
4. Savaş talimatlarında sert, otoriter ve net bir üslup kullan.
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
        await update.message.reply_text("⚠️ Admin paneline sadece özel sohbetten erişebilirsiniz.")
        return

    if user_id in bot_state["authenticated_admins"]:
        await update.message.reply_text("👑 **VIYANA V3 Admin Paneli**", reply_markup=get_admin_keyboard(), parse_mode="Markdown")
    else:
        await update.message.reply_text("🔑 Lütfen Admin şifresini giriniz:")

async def process_ai_with_groq(prompt: str) -> str:
    """Groq Llama-3.3 70B Modeli İle Yanıt Oluşturma"""
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=1024
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Groq Chat Hatası: {e}")
        return "⚠️ AI yanıt üretirken bir hata oluştu."

async def transcribe_voice(file_path: str) -> str:
    """Groq Whisper-Large-V3 İle Ses Kaydını Çözümleme"""
    try:
        with open(file_path, "rb") as file:
            transcription = groq_client.audio.transcriptions.create(
                file=(file_path, file.read()),
                model="whisper-large-v3-turbo",
                language="tr",
                response_format="json"
            )
            return transcription.text
    except Exception as e:
        logger.error(f"Groq Ses İşleme Hatası: {e}")
        return None

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in bot_state["authenticated_admins"]:
        await query.message.reply_text("⚠️ Oturum süreniz dolmuş. Lütfen /admin yazın.")
        return

    if query.data == "start_war":
        bot_state["is_active"] = True
        await query.message.reply_text("🟢 Savaş modu başlatıldı.")
        if GROUP_CHAT_ID:
            await context.bot.send_message(chat_id=GROUP_CHAT_ID, text="🚨 **SAVAŞ BAŞLADI!** Herkes mevzilere!", parse_mode="Markdown")

    elif query.data == "stop_war":
        bot_state["is_active"] = False
        await query.message.reply_text("🔴 Savaş modu durduruldu.")

    elif query.data == "ai_instruction":
        bot_state["awaiting_ai_input"].add(user_id)
        await query.message.reply_text("🎙️ **AI TALİMAT MODU AKTİF (Groq)**\n\nKomutunuzu yazın veya sesli mesaj atın.")

    elif query.data == "status_report":
        status_msg = f"📊 **Mevcut Savaş Durumu:** {'🟢 AKTİF' if bot_state['is_active'] else '🔴 KAPALI'}"
        await query.message.reply_text(status_msg, parse_mode="Markdown")

async def handle_private_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if update.message.chat.type != "private":
        return

    if user_id not in bot_state["authenticated_admins"]:
        if update.message.text == ADMIN_PASSWORD:
            bot_state["authenticated_admins"].add(user_id)
            await update.message.reply_text("✅ Şifre Doğrulandı!", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text("❌ Hatalı şifre.")
        return

    if user_id in bot_state["awaiting_ai_input"]:
        prompt_text = ""

        if update.message.voice:
            await update.message.reply_text("🎙️ Ses kaydınız Groq Whisper ile işleniyor...")
            voice_file = await context.bot.get_file(update.message.voice.file_id)
            file_path = "voice_msg.ogg"
            await voice_file.download_to_drive(file_path)
            
            prompt_text = await transcribe_voice(file_path)
            if os.path.exists(file_path):
                os.remove(file_path)

            if not prompt_text:
                await update.message.reply_text("❌ Ses anlaşılamadı. Tekrar deneyin.")
                return

            await update.message.reply_text(f"🗣️ **Algılanan Ses:** *\"{prompt_text}\"*")
        else:
            prompt_text = update.message.text

        bot_state["awaiting_ai_input"].remove(user_id)

        await update.message.reply_text("⏳ Groq AI yanıt oluşturuyor...")
        ai_response = await process_ai_with_groq(prompt_text)
        
        await update.message.reply_text(f"🤖 **Yayınlanan Duyuru:**\n\n{ai_response}", parse_mode="Markdown")

        if GROUP_CHAT_ID:
            try:
                await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=ai_response, parse_mode="Markdown")
                await update.message.reply_text("🚀 **Duyuru gruba gönderildi!**")
            except Exception as e:
                await update.message.reply_text(f"⚠️ Gruba atılamadı: {e}")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.TEXT | filters.VOICE) & ~filters.COMMAND, handle_private_messages))

    logger.info("VIYANA V3 Groq Bot Başlatılıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
