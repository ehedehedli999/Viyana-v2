import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# States (Söhbət mərhələləri)
GET_SERVER, GET_ID = range(2)


# --- ƏSAS MENÜ ---
def get_main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📁 Profillərim", callback_data="my_profiles"),
            InlineKeyboardButton(
                "➕ Profil Əlavə Et", callback_data="add_profile_start"
            ),
        ],
        [
            InlineKeyboardButton(
                "🛒 Paketlər & Mağaza", callback_data="shop_packages"
            ),
            InlineKeyboardButton("🌐 Dil / Language", callback_data="settings"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👑 **Salam, {user.first_name}!**\n\n"
        f"Game of Sultans endirimli avtomatlaşdırılmış top-up botuna xoş gəlmisiniz.\n"
        f"Zəhmət olmasa aşağıdakı menyüdən seçiminizi edin:"
    )

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            text=text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown",
        )


# --- PROFİL ƏLAVƏ ETMƏ MEXANİZMİ (Conversation) ---
async def add_profile_begin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        text=(
            "🎮 **Yeni Profil Əlavə Edilməsi**\n\n"
            "1️⃣ Zəhmət olmasa oyun **Serverini (Sunucu nömrəsini)** daxil edin:\n"
            "(Məsələn: `1001` və ya server adı)"
        ),
        parse_mode="Markdown",
    )
    return GET_SERVER


async def receive_server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    server_input = update.message.text
    context.user_data["temp_server"] = server_input

    await update.message.reply_text(
        f"✅ Server qəbul olundu: **{server_input}**\n\n"
        f"2️⃣ İndi isə oyunçu **ID nömrənizi** daxil edin:",
        parse_mode="Markdown",
    )
    return GET_ID


async def receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player_id = update.message.text
    server = context.user_data.get("temp_server")

    # Burada həmin pay.9longe.net saytının API-nə sorğu atılıb oyunçu adı yoxlanılacaq
    # Məsələn: player_name = check_game_account(server, player_id)

    text = (
        f"🎉 **Hesabınız uğurla tapıldı və yoxlandı!**\n\n"
        f"🖥 Server: `{server}`\n"
        f"🆔 ID: `{player_id}`\n"
        f"👤 Oyunçu Adı: *Lord Sültan*\n\n"
        f"Hesabı yadda saxlamaq istəyirsinizmi?"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Bəli, Yadda Saxla", callback_data="save_profile_yes"
            )
        ],
        [
            InlineKeyboardButton(
                "❌ Ləğv Et", callback_data="back_to_main_from_add"
            )
        ],
    ]

    await update.message.reply_text(
        text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Əməliyyat ləğv edildi.")
    return ConversationHandler.END


# --- CALLBACK ROUTER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "my_profiles":
        text = (
            "📁 **Sizin Qeydiyyatdakı Hesablarınız:**\n\n"
            "Hələ ki qeydiyyatda hesab yoxdur. 'Profil Əlavə Et' düyməsini basın."
        )
        keyboard = [
            [
                InlineKeyboardButton(
                    "➕ Profil Əlavə Et", callback_data="add_profile_start"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Əsas Menyüyə Qayıt", callback_data="main_menu"
                )
            ],
        ]
        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data == "shop_packages":
        text = (
            "🛒 **Game of Sultans Endirimli Paketlər**\n\n"
            "Saytdakı güncəl paketlər yüklənir...\n"
            "1. 💎 60 Almaz - Endirimli Qiymət\n"
            "2. 💎 300 Almaz - Endirimli Qiymət\n"
            "3. 📦 Aylıq Kart - Xüsusi Təklif"
        )
        keyboard = [
            [
                InlineKeyboardButton(
                    "💳 Paket Alışına Keç", callback_data="checkout"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Əsas Menyüyə Qayıt", callback_data="main_menu"
                )
            ],
        ]
        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    elif data == "main_menu" or data == "back_to_main_from_add":
        await start(update, context)


def main():
    token = "BURAYA_BOT_TOKEN_YAZILACAQ"
    app = ApplicationBuilder().token(token).build()

    # Profil əlavə etmək üçün addımlı handler (ConversationHandler)
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                add_profile_begin, pattern="^add_profile_start$"
            )
        ],
        states={
            GET_SERVER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_server)
            ],
            GET_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_id)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot işə düşdü...")
    app.run_polling()


if __name__ == "__main__":
    main()
