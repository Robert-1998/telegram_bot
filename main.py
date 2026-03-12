# import logging
# import os
# import asyncio
# from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
# from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
# from google import genai
# from google.genai.errors import APIError
# import data_manager  # твоя БД с MOCK_DB_SCHOOL

# logging.basicConfig(
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     level=logging.INFO
# )
# logger = logging.getLogger(__name__)

# TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# # --- Инициализация клиента Gemini ---
# try:
#     client = genai.Client()
#     logger.info("Gemini client подключен")
# except Exception as e:
#     logger.error(f"Не удалось подключить Gemini: {e}")
#     client = None

# # --- /start ---
# async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     keyboard = [
#         [KeyboardButton(
#             "📱 Открыть приложение",
#             web_app=WebAppInfo(url="https://robert-1998.github.io/telegram_bot/webapp.html")
#         )]
#     ]
#     reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#     await update.message.reply_text("Откройте приложение школы:", reply_markup=reply_markup)

# # --- Обработка Web App данных ---
# async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     web_app_data = update.message.web_app_data
#     if not web_app_data:
#         return

#     user_id = str(update.effective_user.id)
#     data_received = web_app_data.data
#     logger.info(f"WebApp data from {user_id}: {data_received}")

#     # --- Запрос списка курсов ---
#     if data_received == "GET_COURSES":
#         courses_list = ""
#         for cid, course in data_manager.MOCK_DB_SCHOOL["courses"].items():
#             courses_list += f"{cid}: {course['name']}\n"
#         # Ответ WebApp обычным сообщением
#         await update.message.reply_text(f"[LIST_COURSES_START]\n{courses_list}")
#         return

#     # --- Регистрация на курс ---
#     if data_received.startswith("WEB_REGISTER:"):
#         course_id = data_received.split(":")[1]

#         # Проверка записи
#         registration_check = data_manager.check_user_registration_status(user_id)
#         if "Вы записаны на курс" in registration_check:
#             response_text = registration_check
#         else:
#             registration_result = data_manager.register_user_for_course(user_id, course_id)
#             if registration_result.get("status") == "success":
#                 course_name = data_manager.MOCK_DB_SCHOOL['courses'][course_id]['name']
#                 response_text = f"✅ Вы успешно записаны на курс '{course_name}'!"
#             else:
#                 response_text = f"❌ Ошибка при записи: {registration_result.get('error','Неизвестная ошибка.')}"

#         # Отправка ответа WebApp
#         await update.message.reply_text(response_text)
#         return

# # --- Обработка inline-кнопок ---
# async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     await query.answer()
#     user_id = str(query.from_user.id)
#     data = query.data

#     if data.startswith("COURSE_DETAILS:"):
#         course_id = data.split(":")[1]
#         course = data_manager.get_course_details(course_id)
#         if "error" in course:
#             await query.edit_message_text(course["error"])
#             return
#         text = (
#             f"Детали курса: {course.get('name','N/A')}\n"
#             f"Продолжительность: {course.get('duration','N/A')}\n"
#             f"Расписание: {course.get('schedule','N/A')}\n"
#             f"Преподаватель: {course.get('instructor','N/A')}\n"
#             f"Статус: {course.get('status','N/A')}\n"
#         )
#         keyboard = [
#             [InlineKeyboardButton("Записаться", callback_data=f"REGISTER_COURSE:{course_id}")],
#             [InlineKeyboardButton("⬅️ Назад", callback_data="GO_HOME")]
#         ]
#         await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
#         return

#     elif data.startswith("REGISTER_COURSE:"):
#         course_id = data.split(":")[1]
#         check = data_manager.check_user_registration_status(user_id)
#         if "Вы записаны на курс" in check:
#             await query.edit_message_text(check)
#             return
#         context.user_data['pending_registration_course_id'] = course_id
#         course_name = data_manager.MOCK_DB_SCHOOL["courses"][course_id]["name"]
#         text = f"Введите ваше имя и телефон через запятую для записи на '{course_name}'"
#         await query.edit_message_text(text)
#         return

#     elif data == "GO_HOME":
#         list_text = ""
#         for cid, course in data_manager.MOCK_DB_SCHOOL["courses"].items():
#             list_text += f"{cid}: {course['name']}\n"
#         keyboard = [[InlineKeyboardButton(course['name'], callback_data=f"COURSE_DETAILS:{cid}")] for cid, course in data_manager.MOCK_DB_SCHOOL["courses"].items()]
#         await query.edit_message_text("Выберите курс:", reply_markup=InlineKeyboardMarkup(keyboard))
#         return

# # --- Ввод данных пользователя для записи ---
# async def handle_data_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     if 'pending_registration_course_id' not in context.user_data:
#         return
#     user_id = str(update.effective_user.id)
#     course_id = context.user_data.pop('pending_registration_course_id')
#     parts = [p.strip() for p in update.message.text.split(",",1)]
#     if len(parts) < 2:
#         await update.message.reply_text("Неверный формат. Введите: Имя, Телефон")
#         return
#     name, phone = parts
#     result = data_manager.register_user_for_course(user_id, course_id)
#     if result.get("status") == "success":
#         text = f"🎉 Вы записаны!\nКурс: {data_manager.MOCK_DB_SCHOOL['courses'][course_id]['name']}\nИмя: {name}\nТелефон: {phone}"
#     else:
#         text = f"❌ Ошибка записи: {result.get('error','Неизвестная ошибка')}"
#     await update.message.reply_text(text)

# # --- Запуск ---
# def main():
#     if not TELEGRAM_TOKEN:
#         logger.critical("Нет TELEGRAM_TOKEN")
#         return

#     app = Application.builder().token(TELEGRAM_TOKEN).build()
#     app.add_handler(CommandHandler("start", start_command))
#     app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
#     app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_data_input))
#     app.add_handler(CallbackQueryHandler(button_callback))
#     logger.info("Бот запущен")
#     app.run_polling(allowed_updates=Update.ALL_TYPES)

# if __name__ == "__main__":
#     main()

# bot.py
import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import data_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Откройте Web App для записи на курсы!")

# --- Web App Data Handler ---
async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    web_app_data = update.message.web_app_data
    if not web_app_data:
        return

    user_id = str(update.effective_user.id)
    data_received = web_app_data.data
    logger.info(f"Web App data from {user_id}: {data_received}")

    # --- GET COURSES ---
    if data_received == "GET_COURSES":
        courses_list = ""
        for cid, course in data_manager.MOCK_DB_SCHOOL["courses"].items():
            courses_list += f"{cid}: {course['name']}\n"
        await context.bot.send_message(chat_id=user_id, text=f"[LIST_COURSES_START]\n{courses_list}")
        return

    # --- REGISTER COURSE ---
    if data_received.startswith("WEB_REGISTER:"):
        try:
            parts = data_received.split(":", 3)
            if len(parts) < 4:
                raise ValueError("Неверный формат данных")
            course_id, name, phone = parts[1], parts[2].strip(), parts[3].strip()

            reg_check = data_manager.check_user_registration_status(user_id)
            if "Вы записаны на курс" in reg_check:
                response_text = reg_check
            else:
                result = data_manager.register_user_for_course(user_id, course_id, name=name, phone=phone)
                if result.get("status") == "success":
                    course_name = data_manager.MOCK_DB_SCHOOL['courses'][course_id]['name']
                    response_text = f"✅ Вы успешно записаны на курс '{course_name}'!\nИмя: {name}\nТелефон: {phone}\nДата записи: {result['date']}"
                else:
                    response_text = f"❌ Ошибка при записи: {result.get('error', 'Неизвестная ошибка.')}"
        except Exception as e:
            logger.error(f"Ошибка регистрации: {e}")
            response_text = "❌ Не удалось обработать запись. Проверьте формат данных."

        await context.bot.send_message(chat_id=user_id, text=response_text)

def main():
    if not TELEGRAM_TOKEN:
        logger.critical("TELEGRAM_TOKEN не установлен")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    application.run_polling()

if __name__ == "__main__":
    main()