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

# Logging Ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ortam Değişkenleri
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "123456")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

# NVIDIA OpenAI İstemcisi
client = openai.OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)

# OYUNCU LİSTESİ VE TELEGRAM ID'LERİ (@ işareti veya kullanıcı adı yazmana gerek kalmaz)
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

# Botun Anlık Savaş Durum Hafızası
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
Admin sana sesli veya yazılı olarak komut verecek.

Tanımlı Oyuncu Listesi ve Telegram ID'leri:
{PLAYERS}

Talimatlar:
1. Adminin verdiği talimattan Saldırı ve Savunma takımlarını tespit et.
2. Metindeki isimleri Telegram'ın tıklanabilir canlı etiket formatına çevir: [OyuncuAdı](tg://user?id=OYUNCU_ID)
3. Viyana Duyuru grubunda yayınlanacak sert, otoriter, askeri disiplinde bir duyuru ve strateji metni hazırla.
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
    await update.message.reply_text("👑 VIYANA V3 Savaş Sistemi Aktif. /admin yazarak giriş yapın.")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if update.message.chat.type != "private":
        await update.message.reply_text("⚠️ Admin paneline sadece özel sohbetten (DM) erişebilirsiniz.")
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
    return "⚠️ AI yanıt üretemedi, lütfen tekrar deneyin."

async def transcribe_voice(file_path: str) -> str:
    """NVIDIA Whisper ile ses kaydını Türkçeye dönüştürür"""
    try:
        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="openai/whisper-large-v3-turbo",
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
        await query.message.reply_text("⚠️ Oturum süreniz dolmuş. Lütfen /admin yazın.")
        return

    if query.data == "start_war":
        bot_state["is_active"] = True
        await query.message.reply_text("🟢 Savaş modu başlatıldı.")
        if GROUP_CHAT_ID:
            await context.bot.send_message(chat_id=GROUP_CHAT_ID, text="🚨 **SAVAŞ BAŞLADI!** Tüm üyeler mevzilere!", parse_mode="Markdown")

    elif query.data == "stop_war":
        bot_state["is_active"] = False
        await query.message.reply_text("🔴 Savaş modu durduruldu.")
        if GROUP_CHAT_ID:
            await context.bot.send_message(chat_id=GROUP_CHAT_ID, text="🏁 **SAVAŞ BİTTİ!** Katılan tüm savaşçılara teşekkürler.", parse_mode="Markdown")

    elif query.data == "ai_instruction":
        bot_state["awaiting_ai_input"].add(user_id)
        await query.message.reply_text(
            "🎙️ **AI TALİMAT MODU AKTİF**\n\n"
            "Şimdi sesli mesaj atın veya doğrudan metin yazın.\n"
            "Örn: *'Ehed ve Şahin saldırıda, Sabina savunmada kalkan kırsın.'*"
        )

    elif query.data == "status_report":
        att_str = ", ".join(bot_state["attackers"]) if bot_state["attackers"] else "Yok"
        def_str = ", ".join(bot_state["defenders"]) if bot_state["defenders"] else "Yok"
        status_msg = (
            f"📊 **Mevcut Savaş Durumu**\n\n"
            f"**Durum:** {'🟢 AKTİF' if bot_state['is_active'] else '🔴 KAPALI'}\n"
            f"**Hedef:** {bot_state['target']}\n"
            f"**Saldırı:** {att_str}\n"
            f"**Savunma:** {def_str}"
        )
        await query.message.reply_text(status_msg, parse_mode="Markdown")

async def handle_private_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if update.message.chat.type != "private":
        return

    # Şifre Giriş Kontrolü
    if user_id not in bot_state["authenticated_admins"]:
        if update.message.text == ADMIN_PASSWORD:
            bot_state["authenticated_admins"].add(user_id)
            await update.message.reply_text("✅ Şifre Doğrulandı! Admin Paneline Hoş Geldiniz.", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text("❌ Hatalı şifre.")
        return

    # AI Talimat Bekleme Durumu (Ses veya Metin)
    if user_id in bot_state["awaiting_ai_input"]:
        prompt_text = ""

        # Sesli Mesaj Geldiyse
        if update.message.voice:
            await update.message.reply_text("🎙️ Ses kaydınız çözümleniyor...")
            voice_file = await context.bot.get_file(update.message.voice.file_id)
            file_path = "voice_msg.ogg"
            await voice_file.download_to_drive(file_path)
            
            prompt_text = await transcribe_voice(file_path)
            if os.path.exists(file_path):
                os.remove(file_path)

            if not prompt_text:
                await update.message.reply_text("❌ Ses anlaşılamadı. Lütfen tekrar ses atın veya yazılı yazın.")
                return # Moddan çıkmaz, tekrar dinler

            await update.message.reply_text(f"🗣️ **Algılanan Ses:** *\"{prompt_text}\"*")
        else:
            prompt_text = update.message.text

        # Başarıyla girdi alındıysa bekleme modundan çıkar
        bot_state["awaiting_ai_input"].remove(user_id)

        # AI İşleme & Gruba Aktarma
        await update.message.reply_text("⏳ Talimat hazırlanıyor ve Viyana Duyuru grubuna aktarılıyor...")
        ai_response = await process_ai_with_nvidia(prompt_text)
        
        await update.message.reply_text(f"🤖 **Yayınlanan Duyuru:**\n\n{ai_response}", parse_mode="Markdown")

        if GROUP_CHAT_ID:
            try:
                await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=ai_response, parse_mode="Markdown")
                await update.message.reply_text("🚀 **Duyuru başarıyla gruba gönderildi!**")
            except Exception as e:
                await update.message.reply_text(f"⚠️ Gruba mesaj gönderilemedi: {e}")
        else:
            await update.message.reply_text("⚠️ `GROUP_CHAT_ID` eksik, gruba atılamadı.")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.TEXT | filters.VOICE) & ~filters.COMMAND, handle_private_messages))

    logger.info("VIYANA V3 Bot Başlatılıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
