import os
import asyncio
import logging
from html import escape

from openai import AsyncOpenAI

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)


# ============================================================
# VIYANA V3
# Telegram AI Savaş Koordinasyon Botu
# ============================================================


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("8916820174:AAFJPiCyKIq7liSmZPkchyxMx2P0GxLLDt8")
NVIDIA_API_KEY = os.getenv("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")
ADMIN_PASSWORD = os.getenv("ehed1995")


# ============================================================
# NVIDIA AYARLARI
# ============================================================

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


# NVIDIA'da uygun ücretsiz modeller.
# İlk model çalışmazsa bot otomatik olarak sıradakini dener.
NVIDIA_FREE_MODELS = [
    "deepseek-ai/deepseek-v4-flash-0731",
    "openai/gpt-oss-20b",
    "google/gemma-4-31b-it",
]


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("VIYANA_V3")


# ============================================================
# NVIDIA CLIENT
# ============================================================

ai_client = None

if NVIDIA_API_KEY:
    ai_client = AsyncOpenAI(
        api_key=NVIDIA_API_KEY,
        base_url=NVIDIA_BASE_URL,
    )


# ============================================================
# BOT HAFIZASI
# ============================================================

wars = {}

authenticated_admins = set()

waiting_for_password = set()


def get_war(chat_id):

    if chat_id not in wars:

        wars[chat_id] = {
            "active": False,
            "war_type": "Birlik Savaşı",
            "attackers": {},
            "defenders": {},
            "target": "",
            "instructions": "",
            "interval": 15,
            "task": None,
        }

    return wars[chat_id]


# ============================================================
# NVIDIA OTOMATİK MODEL SİSTEMİ
# ============================================================

async def ask_nvidia(messages):

    if not ai_client:

        return (
            "⚠️ NVIDIA_API_KEY ayarlanmamış."
        )

    last_error = None

    for model in NVIDIA_FREE_MODELS:

        try:

            logger.info(
                "NVIDIA modeli deneniyor: %s",
                model,
            )

            response = await ai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
                max_tokens=600,
            )

            result = response.choices[0].message.content

            if result:

                logger.info(
                    "Başarılı model: %s",
                    model,
                )

                return result.strip()

        except Exception as error:

            last_error = error

            logger.warning(
                "Model kullanılamadı: %s | %s",
                model,
                error,
            )

            # Bir sonraki modele geç
            continue

    logger.error(
        "Bütün NVIDIA modelleri başarısız: %s",
        last_error,
    )

    return (
        "⚠️ NVIDIA ücretsiz modellerinin "
        "hiçbiri şu anda kullanılamıyor. "
        "Biraz sonra tekrar deneyin."
    )


# ============================================================
# TELEGRAM KULLANICI ETİKETİ
# ============================================================

def mention_user(user_id, name):

    return (
        f'<a href="tg://user?id={user_id}">'
        f'{escape(name)}'
        f'</a>'
    )


def players_text(players):

    if not players:

        return "Henüz oyuncu yok."

    result = []

    for user_id, data in players.items():

        result.append(
            mention_user(
                user_id,
                data["name"],
            )
        )

    return "\n".join(result)


# ============================================================
# ADMIN KONTROLÜ
# ============================================================

async def is_group_admin(update):

    if not update.effective_user:
        return False

    if not update.effective_chat:
        return False

    if update.effective_chat.type == "private":

        return (
            update.effective_user.id
            in authenticated_admins
        )

    try:

        member = await update.effective_chat.get_member(
            update.effective_user.id
        )

        return member.status in (
            "administrator",
            "creator",
        )

    except Exception as error:

        logger.error(
            "Admin kontrolü: %s",
            error,
        )

        return False


# ============================================================
# START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    text = (
        "⚔️ <b>VIYANA V3</b>\n\n"
        "AI destekli savaş koordinasyon botu.\n\n"

        "🔐 Admin paneli:\n"
        "/admin\n\n"

        "📊 Savaş durumu:\n"
        "/durum\n\n"

        "🗡️ Saldırı:\n"
        "/saldiri\n\n"

        "🛡️ Savunma:\n"
        "/savunma\n\n"

        "🎯 Hedef:\n"
        "/hedef"
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# HELP
# ============================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    text = (
        "🤖 <b>VIYANA V3 KOMUTLARI</b>\n\n"

        "🔐 /admin\n"
        "Admin panelini açar.\n\n"

        "⚔️ /savasbaslat\n"
        "Savaş modunu başlatır.\n\n"

        "⏹️ /savasbitir\n"
        "Savaş modunu kapatır.\n\n"

        "📊 /durum\n"
        "Savaş durumunu gösterir.\n\n"

        "🗡️ /saldiri\n"
        "Saldırı oyuncularını gösterir.\n\n"

        "🛡️ /savunma\n"
        "Savunma oyuncularını gösterir.\n\n"

        "🎯 /hedef Birlik Adı\n"
        "Hedef belirler.\n\n"

        "Oyuncu mesajına yanıt vererek:\n"
        "/saldiriyorum\n"
        "veya\n"
        "/savunmadayim\n"
        "kullanabilirsiniz."
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# ADMIN KOMUTU
# ============================================================

async def admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if update.effective_chat.type != "private":

        await update.message.reply_text(
            "🔐 Admin paneli özel sohbetten açılır."
        )

        return

    user_id = update.effective_user.id

    if user_id in authenticated_admins:

        await send_admin_panel(
            update.message,
            context,
        )

        return

    if not ADMIN_PASSWORD:

        await update.message.reply_text(
            "❌ ADMIN_PASSWORD ayarlanmamış."
        )

        return

    waiting_for_password.add(user_id)

    await update.message.reply_text(
        "🔐 <b>VIYANA V3 ADMIN PANELİ</b>\n\n"
        "Admin şifrenizi gönderin.",
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# ADMIN PANEL
# ============================================================

async def send_admin_panel(
    message,
    context,
):

    keyboard = [

        [
            InlineKeyboardButton(
                "⚔️ SAVAŞI BAŞLAT",
                callback_data="war_start",
            ),
            InlineKeyboardButton(
                "⏹️ SAVAŞI BİTİR",
                callback_data="war_stop",
            ),
        ],

        [
            InlineKeyboardButton(
                "📊 SAVAŞ DURUMU",
                callback_data="status",
            ),
        ],

        [
            InlineKeyboardButton(
                "🗡️ SALDIRI",
                callback_data="attackers",
            ),
            InlineKeyboardButton(
                "🛡️ SAVUNMA",
                callback_data="defenders",
            ),
        ],

        [
            InlineKeyboardButton(
                "🎯 HEDEF",
                callback_data="target",
            ),
            InlineKeyboardButton(
                "⏱️ SÜRE",
                callback_data="interval",
            ),
        ],

        [
            InlineKeyboardButton(
                "🤖 AI KOMUTU",
                callback_data="ai_info",
            ),
        ],

        [
            InlineKeyboardButton(
                "🔒 PANELİ KİLİTLE",
                callback_data="logout",
            ),
        ],
    ]

    await message.reply_text(
        "👑 <b>VIYANA V3 ADMIN PANELİ</b>\n\n"
        "Yönetmek istediğiniz işlemi seçin:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


# ============================================================
# ADMIN ŞİFRE KONTROLÜ
# ============================================================

async def check_password(update):

    if update.effective_chat.type != "private":

        return False

    user_id = update.effective_user.id

    if user_id not in waiting_for_password:

        return False

    waiting_for_password.discard(user_id)

    password = update.message.text.strip()

    if password == ADMIN_PASSWORD:

        authenticated_admins.add(user_id)

        await update.message.reply_text(
            "✅ Admin doğrulaması başarılı."
        )

        await send_admin_panel(
            update.message,
            None,
        )

    else:

        await update.message.reply_text(
            "❌ Admin şifresi yanlış."
        )

    return True


# ============================================================
# ADMIN BUTONLARI
# ============================================================

async def admin_buttons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    if user_id not in authenticated_admins:

        await query.edit_message_text(
            "🔒 Admin oturumu kapalı."
        )

        return

    data = query.data

    if data == "logout":

        authenticated_admins.discard(user_id)

        await query.edit_message_text(
            "🔒 Admin paneli kilitlendi."
        )

        return

    chat_id = context.user_data.get(
        "active_group"
    )

    if not chat_id:

        await query.edit_message_text(
            "⚠️ Önce botun bulunduğu grupta "
            "bir admin komutu kullanın.\n\n"
            "Örneğin:\n"
            "/durum"
        )

        return

    war = get_war(chat_id)

    # --------------------------------------------------------
    # SAVAŞ BAŞLAT
    # --------------------------------------------------------

    if data == "war_start":

        if war["active"]:

            await query.edit_message_text(
                "⚠️ Savaş zaten aktif."
            )

            return

        war["active"] = True

        if war["task"]:

            war["task"].cancel()

        war["task"] = asyncio.create_task(
            war_reminder_loop(
                context.application,
                chat_id,
            )
        )

        await query.edit_message_text(
            "⚔️ <b>SAVAŞ MODU AKTİF</b>\n\n"
            "Otomatik savaş koordinasyonu başladı.",
            parse_mode=ParseMode.HTML,
        )

        return

    # --------------------------------------------------------
    # SAVAŞ BİTİR
    # --------------------------------------------------------

    if data == "war_stop":

        war["active"] = False

        if war["task"]:

            war["task"].cancel()
            war["task"] = None

        await query.edit_message_text(
            "⏹️ <b>SAVAŞ MODU KAPATILDI</b>",
            parse_mode=ParseMode.HTML,
        )

        return

    # --------------------------------------------------------
    # DURUM
    # --------------------------------------------------------

    if data == "status":

        await query.edit_message_text(
            create_status_text(war),
            parse_mode=ParseMode.HTML,
        )

        return

    # --------------------------------------------------------
    # SALDIRI
    # --------------------------------------------------------

    if data == "attackers":

        text = (
            "🗡️ <b>SALDIRI EKİBİ</b>\n\n"
            + players_text(
                war["attackers"]
            )
        )

        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
        )

        return

    # --------------------------------------------------------
    # SAVUNMA
    # --------------------------------------------------------

    if data == "defenders":

        text = (
            "🛡️ <b>SAVUNMA EKİBİ</b>\n\n"
            + players_text(
                war["defenders"]
            )
        )

        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
        )

        return

    # --------------------------------------------------------
    # HEDEF
    # --------------------------------------------------------

    if data == "target":

        await query.edit_message_text(
            "🎯 Hedefi değiştirmek için grupta:\n\n"
            "/hedef Birlik Adı\n\n"
            "yazın.",
        )

        return

    # --------------------------------------------------------
    # SÜRE
    # --------------------------------------------------------

    if data == "interval":

        keyboard = [

            [
                InlineKeyboardButton(
                    "⏱️ 15 DAKİKA",
                    callback_data="interval_15",
                ),
                InlineKeyboardButton(
                    "⏱️ 20 DAKİKA",
                    callback_data="interval_20",
                ),
            ]

        ]

        await query.edit_message_text(
            "Otomatik mesaj süresini seç:",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
        )

        return

    # --------------------------------------------------------
    # 15 DAKİKA
    # --------------------------------------------------------

    if data == "interval_15":

        war["interval"] = 15

        await query.edit_message_text(
            "✅ Otomatik savaş mesajı "
            "<b>15 dakika</b> olarak ayarlandı.",
            parse_mode=ParseMode.HTML,
        )

        return

    # --------------------------------------------------------
    # 20 DAKİKA
    # --------------------------------------------------------

    if data == "interval_20":

        war["interval"] = 20

        await query.edit_message_text(
            "✅ Otomatik savaş mesajı "
            "<b>20 dakika</b> olarak ayarlandı.",
            parse_mode=ParseMode.HTML,
        )

        return

    # --------------------------------------------------------
    # AI BİLGİ
    # --------------------------------------------------------

    if data == "ai_info":

        await query.edit_message_text(
            "🤖 <b>AI SİSTEMİ</b>\n\n"
            "Admin doğal dilde talimat verebilir.\n\n"
            "Örnek:\n\n"
            "Birlik savaşı başladı. "
            "Ali ve Mehmet savunmada. "
            "Hasan ve Ehed saldırıda. "
            "İkinci sıradaki birliğe saldırıyoruz.\n\n"
            "Bot bu bilgiyi AI ile analiz eder "
            "ve savaş koordinasyonu oluşturur.",
            parse_mode=ParseMode.HTML,
        )

        return


# ============================================================
# DURUM METNİ
# ============================================================

def create_status_text(war):

    status = (
        "🟢 AKTİF"
        if war["active"]
        else "🔴 KAPALI"
    )

    return (
        "📊 <b>VIYANA V3 SAVAŞ DURUMU</b>\n\n"

        f"Durum: {status}\n"
        f"Savaş: {escape(war['war_type'])}\n"
        f"Hedef: "
        f"{escape(war['target'] or 'Belirlenmedi')}\n"
        f"Süre: {war['interval']} dakika\n\n"

        "🗡️ <b>SALDIRI</b>\n"
        f"{players_text(war['attackers'])}\n\n"

        "🛡️ <b>SAVUNMA</b>\n"
        f"{players_text(war['defenders'])}"
    )


# ============================================================
# GRUBU HAFIZAYA AL
# ============================================================

async def remember_group(
    update,
    context,
):

    if not update.effective_chat:

        return

    if update.effective_chat.type == "private":

        return

    if await is_group_admin(update):

        context.user_data[
            "active_group"
        ] = update.effective_chat.id


# ============================================================
# SAVAŞ BAŞLAT
# ============================================================

async def start_war(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not await is_group_admin(update):

        await update.message.reply_text(
            "⛔ Bu komut yalnızca yöneticilere açıktır."
        )

        return

    chat_id = update.effective_chat.id

    context.user_data[
        "active_group"
    ] = chat_id

    war = get_war(chat_id)

    if war["active"]:

        await update.message.reply_text(
            "⚠️ Savaş zaten aktif."
        )

        return

    war["active"] = True

    war["task"] = asyncio.create_task(
        war_reminder_loop(
            context.application,
            chat_id,
        )
    )

    await update.message.reply_text(
        "⚔️ <b>SAVAŞ MODU AKTİF</b>",
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# SAVAŞ BİTİR
# ============================================================

async def stop_war(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not await is_group_admin(update):

        await update.message.reply_text(
            "⛔ Bu komut yalnızca yöneticilere açıktır."
        )

        return

    chat_id = update.effective_chat.id

    context.user_data[
        "active_group"
    ] = chat_id

    war = get_war(chat_id)

    war["active"] = False

    if war["task"]:

        war["task"].cancel()
        war["task"] = None

    await update.message.reply_text(
        "⏹️ <b>SAVAŞ MODU KAPATILDI</b>",
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# OTOMATİK SAVAŞ DÖNGÜSÜ
# ============================================================

async def war_reminder_loop(
    application,
    chat_id,
):

    while True:

        try:

            war = get_war(chat_id)

            if not war["active"]:

                return

            await asyncio.sleep(
                war["interval"] * 60
            )

            war = get_war(chat_id)

            if not war["active"]:

                return

            await send_war_reminder(
                application,
                chat_id,
            )

        except asyncio.CancelledError:

            return

        except Exception as error:

            logger.error(
                "Savaş döngüsü hatası: %s",
                error,
            )

            await asyncio.sleep(30)


# ============================================================
# AI SAVAŞ MESAJI
# ============================================================

async def generate_war_message(war):

    attackers = [
        data["name"]
        for data in war["attackers"].values()
    ]

    defenders = [
        data["name"]
        for data in war["defenders"].values()
    ]

    prompt = f"""
Sen VIYANA V3 adlı Telegram savaş koordinasyon
botunun yapay zeka asistanısın.

Bu sistem yalnızca oyun içi savaş koordinasyonu
için kullanılıyor.

SAVAŞ TÜRÜ:
{war["war_type"]}

HEDEF:
{war["target"] or "Belirlenmedi"}

SALDIRI OYUNCULARI:
{", ".join(attackers) if attackers else "Yok"}

SAVUNMA OYUNCULARI:
{", ".join(defenders) if defenders else "Yok"}

YÖNETİCİ TALİMATI:
{war["instructions"] or "Özel talimat yok"}

Telegram grubuna gönderilecek kısa ve net
bir savaş koordinasyon mesajı hazırla.

Saldırı ekibine:
- Gereksiz saldırı yapmamalarını
- Avantajı korumalarını
- Uygun hedefi beklemelerini

Savunma ekibine:
- Takipte kalmalarını
- Rakip kalkanlarını kırmalarını
- Saldırı ekibinin önünü açmalarını

hatırlat.

Mesaj oyun içi koordinasyon şeklinde olsun.
"""


    return await ask_nvidia(
        [
            {
                "role": "system",
                "content": (
                    "Sen VIYANA V3 savaş "
                    "koordinasyon AI'sısın."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]
    )


# ============================================================
# SAVAŞ MESAJI GÖNDER
# ============================================================

async def send_war_reminder(
    application,
    chat_id,
):

    war = get_war(chat_id)

    ai_message = await generate_war_message(
        war
    )

    text = (
        "⚔️ <b>VIYANA V3 SAVAŞ TAKİBİ</b>\n\n"

        f"🎯 <b>HEDEF:</b>\n"
        f"{escape(war['target'] or 'Belirlenmedi')}\n\n"

        "🗡️ <b>SALDIRI EKİBİ</b>\n"
        f"{players_text(war['attackers'])}\n\n"

        "🛡️ <b>SAVUNMA EKİBİ</b>\n"
        f"{players_text(war['defenders'])}\n\n"

        "🤖 <b>AI KOORDİNASYONU</b>\n"
        f"{escape(ai_message)}"
    )

    await application.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# DURUM KOMUTU
# ============================================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    if update.effective_chat.type != "private":

        context.user_data[
            "active_group"
        ] = chat_id

    war = get_war(chat_id)

    await update.message.reply_text(
        create_status_text(war),
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# SALDIRI LİSTESİ
# ============================================================

async def attack_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    war = get_war(chat_id)

    await update.message.reply_text(
        "🗡️ <b>SALDIRI EKİBİ</b>\n\n"
        + players_text(
            war["attackers"]
        ),
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# SAVUNMA LİSTESİ
# ============================================================

async def defense_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    chat_id = update.effective_chat.id

    war = get_war(chat_id)

    await update.message.reply_text(
        "🛡️ <b>SAVUNMA EKİBİ</b>\n\n"
        + players_text(
            war["defenders"]
        ),
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# HEDEF
# ============================================================

async def target_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not await is_group_admin(update):

        await update.message.reply_text(
            "⛔ Yalnızca grup yöneticileri "
            "hedef belirleyebilir."
        )

        return

    chat_id = update.effective_chat.id

    context.user_data[
        "active_group"
    ] = chat_id

    target = " ".join(
        context.args
    ).strip()

    if not target:

        await update.message.reply_text(
            "Örnek:\n"
            "/hedef İkinci sıradaki birlik"
        )

        return

    war = get_war(chat_id)

    war["target"] = target

    await update.message.reply_text(
        "🎯 Hedef güncellendi:\n"
        f"<b>{escape(target)}</b>",
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# OYUNCU EKLEME
# ============================================================

async def add_player(
    update,
    role,
):

    if not await is_group_admin(update):

        await update.message.reply_text(
            "⛔ Yalnızca yöneticiler "
            "oyuncu ekleyebilir."
        )

        return

    if not update.message.reply_to_message:

        await update.message.reply_text(
            "Oyuncunun mesajına yanıt vererek "
            "komutu kullan."
        )

        return

    target = (
        update.message.reply_to_message.from_user
    )

    if target.is_bot:

        await update.message.reply_text(
            "❌ Bot eklenemez."
        )

        return

    chat_id = update.effective_chat.id

    war = get_war(chat_id)

    player = {
        "name": target.full_name,
        "username": target.username or "",
    }

    if role == "attack":

        war["attackers"][target.id] = player

        war["defenders"].pop(
            target.id,
            None,
        )

        message = (
            "🗡️ "
            + mention_user(
                target.id,
                target.full_name,
            )
            + " saldırı ekibine eklendi."
        )

    else:

        war["defenders"][target.id] = player

        war["attackers"].pop(
            target.id,
            None,
        )

        message = (
            "🛡️ "
            + mention_user(
                target.id,
                target.full_name,
            )
            + " savunma ekibine eklendi."
        )

    await update.message.reply_text(
        message,
        parse_mode=ParseMode.HTML,
    )


async def attack_me(
    update,
    context,
):

    await add_player(
        update,
        "attack",
    )


async def defense_me(
    update,
    context,
):

    await add_player(
        update,
        "defense",
    )


# ============================================================
# GENEL AI KOMUTU
# ============================================================

async def ask_game_ai(text):

    system_prompt = """
Sen VIYANA V3 Telegram botunun yapay zeka
savaş koordinasyon asistanısın.

Bu bot yalnızca oyun içi savaş koordinasyonu
için kullanılır.

Yönetici sana doğal dille savaş talimatı
verebilir.

Saldırı ve savunma oyuncularını,
hedefleri, birlik sıralarını, kalkan durumlarını
ve savaş taktiklerini anlayabilirsin.

Kısa, net ve uygulanabilir Telegram mesajları
oluştur.
"""

    return await ask_nvidia(
        [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": text,
            },
        ]
    )


# ============================================================
# NORMAL MESAJ / AI
# ============================================================

async def natural_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:

        return

    text = update.message.text.strip()

    if not text:

        return

    # --------------------------------------------------------
    # ADMIN ŞİFRESİ
    # --------------------------------------------------------

    if update.effective_chat.type == "private":

        handled = await check_password(
            update
        )

        if handled:

            return

        if (
            update.effective_user.id
            not in authenticated_admins
        ):

            return

        answer = await ask_game_ai(
            text
        )

        await update.message.reply_text(
            "🤖 <b>VIYANA AI</b>\n\n"
            + escape(answer),
            parse_mode=ParseMode.HTML,
        )

        return

    # --------------------------------------------------------
    # GRUP MESAJI
    # --------------------------------------------------------

    if not await is_group_admin(update):

        return

    chat_id = update.effective_chat.id

    context.user_data[
        "active_group"
    ] = chat_id

    war = get_war(chat_id)

    # Yönetici talimatını kaydet
    war["instructions"] = text

    lower = text.lower()

    # --------------------------------------------------------
    # SAVAŞ BAŞLADI
    # --------------------------------------------------------

    start_words = [
        "savaş başladı",
        "savas basladi",
        "savaşı başlat",
        "savasi baslat",
        "savaş başlat",
        "savas baslat",
    ]

    if any(
        word in lower
        for word in start_words
    ):

        war["active"] = True

        if war["task"]:

            war["task"].cancel()

        war["task"] = asyncio.create_task(
            war_reminder_loop(
                context.application,
                chat_id,
            )
        )

    # --------------------------------------------------------
    # SAVAŞ BİTTİ
    # --------------------------------------------------------

    stop_words = [
        "savaş bitti",
        "savas bitti",
        "savaşı bitir",
        "savasi bitir",
        "savaş bitir",
        "savas bitir",
    ]

    if any(
        word in lower
        for word in stop_words
    ):

        war["active"] = False

        if war["task"]:

            war["task"].cancel()
            war["task"] = None

    # --------------------------------------------------------
    # AI
    # --------------------------------------------------------

    answer = await ask_game_ai(
        text
    )

    await update.message.reply_text(
        "🤖 <b>VIYANA AI</b>\n\n"
        + escape(answer),
        parse_mode=ParseMode.HTML,
    )


# ============================================================
# HATA
# ============================================================

async def error_handler(
    update,
    context,
):

    logger.error(
        "Telegram hatası: %s",
        context.error,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not TELEGRAM_BOT_TOKEN:

        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN bulunamadı."
        )

    if not NVIDIA_API_KEY:

        raise RuntimeError(
            "NVIDIA_API_KEY bulunamadı."
        )

    if not ADMIN_PASSWORD:

        raise RuntimeError(
            "ADMIN_PASSWORD bulunamadı."
        )

    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    # ========================================================
    # COMMAND HANDLERS
    # ========================================================

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "yardim",
            help_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "admin",
            admin_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "savasbaslat",
            start_war,
        )
    )

    application.add_handler(
        CommandHandler(
            "savasbitir",
            stop_war,
        )
    )

    application.add_handler(
        CommandHandler(
            "durum",
            status,
        )
    )

    application.add_handler(
        CommandHandler(
            "saldiri",
            attack_list,
        )
    )

    application.add_handler(
        CommandHandler(
            "savunma",
            defense_list,
        )
    )

    application.add_handler(
        CommandHandler(
            "hedef",
            target_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "saldiriyorum",
            attack_me,
        )
    )

    application.add_handler(
        CommandHandler(
            "savunmadayim",
            defense_me,
        )
    )

    # ========================================================
    # ADMIN BUTTONS
    # ========================================================

    application.add_handler(
        CallbackQueryHandler(
            admin_buttons
        )
    )

    # ========================================================
    # TEXT
    # ========================================================

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            natural_message,
        )
    )

    application.add_error_handler(
        error_handler
    )

    logger.info(
        "========================================"
    )

    logger.info(
        "VIYANA V3 BASLATILIYOR"
    )

    logger.info(
        "Otomatik NVIDIA model sistemi aktif"
    )

    logger.info(
        "========================================"
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    main()
