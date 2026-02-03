# -*- coding: utf-8 -*-
import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

import gspread
from google.oauth2.service_account import Credentials

# ===============================
# 🔐 الإعدادات
# ===============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
START_TOKENS = 100
DESIGN_COST = 50

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN غير موجود")

# ===============================
# 📊 Google Sheets
# ===============================
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

sheet = None

try:
    google_creds_json = os.getenv("GOOGLE_JSON")

    if not google_creds_json:
        raise RuntimeError("❌ GOOGLE_JSON غير موجود")

    creds_dict = json.loads(google_creds_json)

    # إصلاح private_key
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)

    sheet = client.open("Posty_Coupons").sheet1
    print("✅ Google Sheets متصل بنجاح")

except Exception as e:
    print(f"❌ خطأ Google Sheets: {e}")

# ===============================
# 🧠 التخزين المؤقت
# ===============================
users = {}
waiting_for_coupon = set()

# ===============================
# 🧩 لوحة المفاتيح
# ===============================
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 تصميم منشور", callback_data="design")],
        [InlineKeyboardButton("👤 الملف الشخصي", callback_data="profile")],
        [InlineKeyboardButton("🎟️ شحن كوبون", callback_data="coupon")],
        [InlineKeyboardButton("🆘 الدعم الفني", callback_data="support")]
    ])

# ===============================
# 🚀 Handlers
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users.setdefault(user_id, {"tokens": START_TOKENS})
    await update.message.reply_text(
        "مرحبًا بك 👋\nاختر الخدمة:",
        reply_markup=main_keyboard()
    )

async def design(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    users.setdefault(user_id, {"tokens": START_TOKENS})

    if users[user_id]["tokens"] < DESIGN_COST:
        await query.edit_message_text("❌ رصيدك غير كافٍ")
        return

    users[user_id]["tokens"] -= DESIGN_COST
    await query.edit_message_text(
        "✅ تم استلام طلبك!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("رجوع", callback_data="back")]
        ])
    )

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    tokens = users.get(user_id, {}).get("tokens", START_TOKENS)

    await query.edit_message_text(
        f"👤 ملفك الشخصي\n\n🔹 التوكنز: {tokens}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("رجوع", callback_data="back")]
        ])
    )

async def coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    waiting_for_coupon.add(query.from_user.id)
    await query.edit_message_text("✏️ أرسل كود الكوبون:")

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "مرحبًا بك 👋\nاختر الخدمة:",
        reply_markup=main_keyboard()
    )

async def receive_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if sheet is None:
        await update.message.reply_text("❌ خدمة الكوبونات متوقفة")
        return

    user_id = update.effective_user.id
    if user_id not in waiting_for_coupon:
        return

    code = update.message.text.strip()

    try:
        records = sheet.get_all_records()
        for i, row in enumerate(records, start=2):
            if str(row["code"]) == code and str(row["used"]).upper() == "FALSE":
                tokens = int(row["tokens"])
                users.setdefault(user_id, {"tokens": START_TOKENS})
                users[user_id]["tokens"] += tokens

                used_col = list(row.keys()).index("used") + 1
                sheet.update_cell(i, used_col, "TRUE")

                await update.message.reply_text(f"✅ تم شحن {tokens} توكن 🎉")
                break
        else:
            await update.message.reply_text("❌ كود غير صالح")

    except Exception as e:
        await update.message.reply_text("❌ خطأ أثناء التحقق")

    waiting_for_coupon.discard(user_id)

# ===============================
# ▶️ تشغيل البوت
# ===============================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(design, pattern="design"))
    app.add_handler(CallbackQueryHandler(profile, pattern="profile"))
    app.add_handler(CallbackQueryHandler(coupon, pattern="coupon"))
    app.add_handler(CallbackQueryHandler(back, pattern="back"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_coupon))

    print("🚀 البوت يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
