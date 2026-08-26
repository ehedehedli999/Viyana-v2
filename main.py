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

# Çevre Değişkenleri
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "123456")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")  # Viyana Duyuru Grubu ID'si

# NVIDIA OpenAI İstemcisi
client = openai.OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)

# Global Durum Hafızası (In-Memory Database)
bot_state = {
    "is_active": False,
    "war_type": "Birlik Savaşları",
    "target": "Belirtilmedi",
    "interval": 20,  # Dakika
    "attackers": [],
    "defenders": [],
    "authenticated_admins": set(),
    "awaiting_ai_input": set()
}

timer_task = None

# System Prompt - AI'ın Görevi
SYSTEM_PROMPT = """
Sen VIYANA V3 Savaş Koordinasyon Yapay Zekasısın.
Görevin admin tarafından verilen doğal dil talimatlarını analiz etmek ve çıktı üretmektir.

Yönergeler:
1. Adminin mesajından Saldırı (Attackers) ve Savunma (Defenders) kadrolarını ayıkla.
2. Hedef veya özel bir emir/duyuru mesajı varsa tespit et.
3. Çıktıyı doğrudan Telegram duyuru grubuna gönderilmeye uygun, son derece karizma, otoriter ve profesyonel bir formatta hazırla.
4. Etiketlenmesi gereken oyuncuları metin içerisinde eksiksiz @etiket şeklinde kullan.
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
    await update.message.reply_text("👑 VIYANA V3 Savaş Koordinasyon Botu Aktif. Admin olmak için /admin yazınız.")

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
    models = ["deepseek-ai/deepseek-v3", "meta/llama-3.3-70b-instruct", "google/gemma-2-27b-it"]
    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=1024
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"Model {model} hatası: {e}. Diğer modele geçiliyor...")
            continue
    return "⚠️ AI yanıt üretemedi, lütfen tekrar deneyin."

async def auto_war_announcement_loop(app: Application):
    global timer_task
    while bot_state["is_active"]:
        if GROUP_CHAT_ID:
            att_str = ", ".join(bot_state["attackers"]) if bot_state["attackers"] else "Kadro Belirtilmedi"
            def_str = ", ".join(bot_state["defenders"]) if bot_state["defenders"] else "Kadro Belirtilmedi"
            
            msg = (
                f"⚔️ **VIYANA V3 - PERİYODİK SAVAŞ DUYURUSU** ⚔️\n\n"
                f"🎯 **Hedef:** {bot_state['target']}\n"
                f"⏱️ **Hatırlatma Aralığı:** {bot_state['interval']} Dakika\n\n"
                f"🗡️ **SALDIRI TAKIMI:**\n{att_str}\n👉 *Saldırı emri verilen hedeflere odaklanın!*\n\n"
                f"🛡️ **SAVUNMA TAKIMI:**\n{def_str}\n👉 *Kalkanları kırın ve hattı koruyun!*\n\n"
                f"🔥 *Savaş disiplinini bozmayın, zafere odaklanın!*"
            )
            try:
                await app.bot.send_message(chat_id=GROUP_CHAT_ID, text=msg, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Gruba otomatik mesaj gönderilemedi: {e}")
        
        await asyncio.sleep(bot_state["interval"] * 60)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in bot_state["authenticated_admins"]:
        await query.message.reply_text("⚠️ Oturumunuz süresi dolmuş. Tekrar /admin yazın.")
        return

    if query.data == "start_war":
        global timer_task
        bot_state["is_active"] = True
        if timer_task is None or timer_task.done():
            timer_task = asyncio.create_task(auto_war_announcement_loop(context.application))
        await query.message.reply_text("🟢 Savaş modu başlatıldı ve otomatik 20 dk döngü devreye girdi.")
        if GROUP_CHAT_ID:
            await context.bot.send_message(chat_id=GROUP_CHAT_ID, text="🚨 **SAVAŞ BAŞLADI!** Tüm birlik üyeleri mevzilere!", parse_mode="Markdown")

    elif query.data == "stop_war":
        bot_state["is_active"] = False
        await query.message.reply_text("🔴 Savaş modu durduruldu.")
        if GROUP_CHAT_ID:
            await context.bot.send_message(chat_id=GROUP_CHAT_ID, text="🏁 **SAVAŞ BİTTİ!** Katılan tüm savaşçılara teşekkürler.", parse_mode="Markdown")

    elif query.data == "ai_instruction":
        bot_state["awaiting_ai_input"].add(user_id)
        await query.message.reply_text(
            "🤖 **AI TALİMAT MODU AKTİF**\n\n"
            "Lütfen yapmak istediğiniz emri yazın veya ses kaydı atın.\n"
            "Örnek: *'Savunma @Ali @Ahmet kalkan kırsın, Saldırı @Mehmet saldırsın. Herkes 20 dakikada bir etiketlensin ve elmas harcasın.'*"
        )

    elif query.data == "status_report":
        att_str = ", ".join(bot_state["attackers"]) if bot_state["attackers"] else "Yok"
        def_str = ", ".join(bot_state["defenders"]) if bot_state["defenders"] else "Yok"
        status_msg = (
            f"📊 **Mevcut Savaş Durumu**\n\n"
            f"**Durum:** {'🟢 AKTİF' if bot_state['is_active'] else '🔴 KAPALI'}\n"
            f"**Hedef:** {bot_state['target']}\n"
            f"**Saldırı Ekibi:** {att_str}\n"
            f"**Savunma Ekibi:** {def_str}"
        )
        await query.message.reply_text(status_msg, parse_mode="Markdown")

async def handle_private_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if update.message.chat.type != "private":
        return

    # Şifre Doğrulama
    if user_id not in bot_state["authenticated_admins"]:
        if text == ADMIN_PASSWORD:
            bot_state["authenticated_admins"].add(user_id)
            await update.message.reply_text("✅ Şifre Doğrulandı! Admin Paneline Hoş Geldiniz.", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text("❌ Hatalı şifre.")
        return

    # AI Talimat İşleme
    if user_id in bot_state["awaiting_ai_input"]:
        bot_state["awaiting_ai_input"].remove(user_id)
        await update.message.reply_text("⏳ Talimat NVIDIA AI ile işleniyor ve gruba aktarılıyor...")

        # AI Analizi
        ai_response = await process_ai_with_nvidia(text)

        # Yanıtı Admin'e Göster
        await update.message.reply_text(f"🤖 **Üretilen Komut/Duyuru:**\n\n{ai_response}", parse_mode="Markdown")

        # Duyuru Grubuna Otomatik Postala
        if GROUP_CHAT_ID:
            try:
                await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=ai_response, parse_mode="Markdown")
                await update.message.reply_text("🚀 **Duyuru Viyana Grubu'na başarıyla yayınlandı!**")
            except Exception as e:
                await update.message.reply_text(f"⚠️ Mesaj gruba atılamadı. GROUP_CHAT_ID ayarını kontrol edin: {e}")
        else:
            await update.message.reply_text("⚠️ `GROUP_CHAT_ID` Tanımlanmadığı için gruba atılamadı. Render Ortam Değişkenlerini kontrol edin.")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_private_messages))

    logger.info("VIYANA V3 Bot Başlatılıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
