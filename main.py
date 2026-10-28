import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Logging quraşdırması
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# States (Söhbət mərhələləri - Server və ID üçün)
GET_SERVER, GET_ID = range(2)


# --- ƏSAS MENÜ KLAVİATURASI ---
def get_main_menu():
    keyboard = [
        [
            InlineKeyboardButton("📁 Profillerim / Мои профили", callback_data="my_profiles"),
            InlineKeyboardButton("➕ Profil Ekle / Добавить", callback_data="add_profile_start"),
        ],
        [
            InlineKeyboardButton("🛒 Paketler & Mağaza / Пакеты", callback_data="shop_packages"),
            InlineKeyboardButton("⚙️ Destek / Поддержка", callback_data="support"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# --- /start VƏ ƏSAS MENÜ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👑 **Salam, {user.first_name} / Привет, {user.first_name}!**\n\n"
        f"🇹🇷 Game of Sultans endirimli avtomatlaşdırılmış botuna xoş gəlmisiniz.\n"
        f"🇷🇺 Добро пожаловать в автоматизированный бот Game of Sultans.\n\n"
        f"👇 Zəhmət olmasa menyüdən seçiminizi edin / Пожалуйста, выберите пункт меню:"
    )

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(text=text, reply_markup=get_main_menu(), parse_mode="Markdown")
    else:
        await update.message.reply_text(text=text, reply_markup=get_main_menu(), parse_mode="Markdown")


# --- PROFİL ƏLAVƏ ETMƏ (CONVERSATION) ---
async def add_profile_begin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = (
        "🎮 **Yeni Profil Ekleme / Добавление профиля**\n\n"
        "🇹🇷 Zəhmət olmasa oyun **Serverini (Sunucu nömrəsini)** daxil edin (məsələn: `1001`):\n"
        "🇷🇺 Пожалуйста, введите номер **Сервера** (например: `1001`):"
    )
    await query.edit_message_text(text=text, parse_mode="Markdown")
    return GET_SERVER


async def receive_server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    server_input = update.message.text
    context.user_data["temp_server"] = server_input

    text = (
        f"✅ Server: `{server_input}`\n\n"
        "🇹🇷 İndi isə oyunçu **ID nömrənizi** daxil edin:\n"
        "🇷🇺 Теперь введите ваш игровой **ID номер**:"
    )
    await update.message.reply_text(text=text, parse_mode="Markdown")
    return GET_ID


async def receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.message.text
    server = context.user_data.get("temp_server")

    text = (
        f"🎉 **Hesab uğurla yoxlandı / Аккаунт успешно проверен!**\n\n"
        f"🖥 Server / Сервер: `{server}`\n"
        f"🆔 ID: `{player_id}`\n\n"
        f"🇹🇷 Hesabı yadda saxlamaq istəyirsinizmi?\n"
        f"🇷🇺 Хотите сохранить этот аккаунт?"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Bəli / Да", callback_data="main_menu")],
        [InlineKeyboardButton("❌ Ləğv Et / Отмена", callback_data="main_menu")],
    ]

    await update.message.reply_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🇹🇷 Əməliyyat ləğv edildi.\n🇷🇺 Операция отменена.")
    return ConversationHandler.END


# --- CALLBACK IDARƏETMƏSİ (DÜYMƏLƏR) ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "my_profiles":
        text = (
            "📁 **Oyunçu Hesablarım / Мои аккаунты:**\n\n"
            "🇹🇷 Hələ ki qeydiyyatda hesab yoxdur.\n"
            "🇷🇺 Пока нет зарегистрированных аккаунтов."
        )
        keyboard = [
            [InlineKeyboardButton("➕ Profil Ekle / Добавить", callback_data="add_profile_start")],
            [InlineKeyboardButton("🔙 Əsas Menyü / Главное меню", callback_data="main_menu")],
        ]
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "shop_packages":
        text = (
            "🛒 **Endirimli Paketlər / Скидочные пакеты:**\n\n"
            "1. 💎 60 Almaz / Алмазов\n"
            "2. 💎 300 Almaz / Алмазов\n"
            "3. 📦 Aylıq Kart / Месячная карта\n\n"
            "🇹🇷 Almaq üçün paketi seçin:\n"
            "🇷🇺 Выберите пакет для покупки:"
        )
        keyboard = [
            [InlineKeyboardButton("💳 Satın Al / Купить", callback_data="main_menu")],
            [InlineKeyboardButton("🔙 Əsas Menyü / Главное меню", callback_data="main_menu")],
        ]
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "support":
        text = (
            "⚙️ **Dəstək Mərkəzi / Центр поддержки**\n\n"
            "🇹🇷 Problem olduqda adminlə əlaqə saxlayın: @Admin\n"
            "🇷🇺 При возникновении проблем свяжитесь с админом: @Admin"
        )
        keyboard = [[InlineKeyboardButton("🔙 Əsas Menyü / Главное меню", callback_data="main_menu")]]
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "main_menu":
        await start(update, context)


def main():
    # Render-də yazdığın dəqiq Environment adını bura yazırıq: TELEGRAM_BOT_TOKEN
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN tapılmadı! Zəhmət olmasa Environment variables yoxlayın.")
        return

    app = ApplicationBuilder().token(token).build()

    # Profil əlavə etmək üçün addımlı handler
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_profile_begin, pattern="^add_profile_start$")],
        states={
            GET_SERVER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_server)],
            GET_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_id)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot uğurla işə düşdü...")
    app.run_polling()


if __name__ == "__main__":
    main()
