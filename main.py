
import logging
import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai 
from google.genai.errors import APIError
import data_manager # импорт модуля БД
from telegram import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo



logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY_CHECK = os.getenv("GEMINI_API_KEY")

# логирование
logger.info(f"Telegram Token Loaded: {'Yes' if TELEGRAM_TOKEN else 'NO'}")
logger.info(f"Gemini API Key Loaded: {'Yes' if GEMINI_KEY_CHECK else 'NO'}")


#  сервисы

# получение телеграмм токена
if not TELEGRAM_TOKEN:
    logging.critical("Запуск невозможен: TELEGRAM_TOKEN не установлен.")

# инициализация клиента Гемини
try:
    client = genai.Client()
    logging.info("Клиент Гемини подключен")
except Exception as e:
    # Исправлено форматирование f-строки для вывода ошибки
    logging.error(f"Не удалось подключить клиента Гемини. Ошибка: {e}")
    client = None

# --- 4. ОБРАБОТЧИКИ ---

# async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     """подтверждение получения команды start"""
#     user = update.effective_user
#     await update.message.reply_html(
#         f"Привет, {user.mention_html()}! Я ваш ассистент. Чем могу помочь? Спросите меня о курсах!",
#     )
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [KeyboardButton(
            "📱 Открыть приложение",
            web_app=WebAppInfo(
                url="https://robert-1998.github.io/telegram_bot/webapp.html"
            )
        )]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Откройте приложение школы:",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """отправка сообщения пользователя в Gemini и возврат ответа с поддержкой функций"""
    user_text = update.message.text
    user_id = str(update.effective_user.id) 
    logger.info(f"Получено сообщение от {user_id}: {user_text}")
    
    if not client:
        await update.message.reply_text("Ошибка ИИ. Попробуйте позже.")
        return

    # --- РЕЖИМ ТЕСТИРОВАНИЯ КНОПОК (ВРЕМЕННОЕ ОТКЛЮЧЕНИЕ LLM) ---
    TEST_BUTTON_MODE = True # Установите True для тестирования кнопок без LLM
    
    if TEST_BUTTON_MODE:
        # РЕЖИМ ЗАГЛУШКИ: Принудительно генерируем список курсов
        list_text = ""
        for cid, data in data_manager.MOCK_DB_SCHOOL["courses"].items():
            list_text += f"{cid}: {data['name']}\n"
        
        ai_response = f"[LIST_COURSES_START]\n{list_text}"
        
    else:
        # --- ОБЫЧНАЯ ЛОГИКА LLM (ВЫПОЛНЯЕТСЯ, ТОЛЬКО ЕСЛИ TEST_BUTTON_MODE = False) ---
        
        # 1. Определение инструментов (функций) для LLM
        tools = [
            genai.types.Tool(
                function_declarations=[
                    genai.types.FunctionDeclaration(
                        name="get_course_details",
                        description="Предоставляет подробную информацию о конкретном курсе по его ID.",
                        parameters={
                            "type": "object",
                            "properties": {
                                "course_id": {
                                    "type": "string",
                                    "description": "ID курса, например, 'acting_basic' или 'voice_tech'.",
                                }
                            },
                            "required": ["course_id"],
                        },
                    ),
                    genai.types.FunctionDeclaration(
                        name="check_user_registration_status",
                        description="Проверяет, на какой курс записан пользователь, используя его Telegram ID.",
                        parameters={
                            "type": "object",
                            "properties": {
                                "user_telegram_id": {
                                    "type": "string",
                                    "description": f"Telegram ID пользователя. Ваш текущий ID: {user_id}",
                                }
                            },
                            "required": ["user_telegram_id"],
                        },
                    )
                ]
            )
        ]

        try:
            # 2. Первый вызов: LLM решает, нужно ли вызывать функцию
            response = client.models.generate_content(
                model='gemini-2.5-flash', 
                contents=user_text,
                config=genai.types.GenerateContentConfig(
                    system_instruction="Ты — ассистент школы актерского мастерства. Если пользователь спрашивает о деталях курса (используя ID) или о своей записи (используя ID), ТЫ ОБЯЗАН использовать предоставленные функции. Если пользователь спрашивает 'какие у вас есть курсы?', ответь одним сообщением: [LIST_COURSES_START] и затем перечисли курсы в виде: ID: Название Курса. В остальных случаях отвечай дружелюбно.",
                    tools=tools
                )
            )
            
            # Проверка, вызвал ли LLM функцию
            function_call_part = None
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.function_call:
                        function_call_part = part.function_call
                        break

            if function_call_part:
                # --- СЛУЧАЙ 1: ВЫЗОВ ФУНКЦИИ ---
                function_name = function_call_part.name
                args = function_call_part.args
                function_result = None
                
                if function_name == "get_course_details":
                    function_result = data_manager.get_course_details(args.get("course_id"))
                elif function_name == "check_user_registration_status":
                    function_result = data_manager.check_user_registration_status(args.get("user_telegram_id"))
                
                # 3. Второй вызов: Отправляем РЕЗУЛЬТАТ ФУНКЦИИ ОБРАТНО В LLM
                second_response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[
                        genai.types.Content(role="user", parts=[genai.types.Part(text=user_text)]),
                        genai.types.Part(
                            function_response=genai.types.FunctionResponse(
                                name=function_name,
                                response=function_result
                            )
                        )
                    ]
                )
                ai_response = second_response.text
                
            else:
                # --- СЛУЧАЙ 2: ПРЯМОЙ ТЕКСТОВЫЙ ОТВЕТ ---
                ai_response = response.text
            
        except APIError as e:
            logger.error(f"Ошибка при обращении к Gemini API: {e}")
            await update.message.reply_text("Извините, возникла ошибка при запросе к ИИ (возможно, превышен лимит или проблема с ключом).")
            return 
        except Exception as e:
            logger.error(f"Непредвиденная ошибка: {e}")
            await update.message.reply_text("Произошла неизвестная ошибка при обработке запроса.")
            return 

    # --- БЛОК ПАРСИНГА И UX (ОБЩИЙ ДЛЯ ОБЕИХ ВЕТОК) ---
    
    LIST_START_MARKER = "[LIST_COURSES_START]"
    
    if LIST_START_MARKER in ai_response:
        # Логика создания кнопок
        list_text = ai_response.split(LIST_START_MARKER)[-1].strip()
        keyboard = []
        for line in list_text.split('\n'):
            if ":" in line:
                try:
                    course_id, course_name_full = line.split(":", 1)
                    course_id = course_id.strip()
                    course_name = course_name_full.strip()
                    keyboard.append([
                        InlineKeyboardButton(course_name, callback_data=f"COURSE_DETAILS:{course_id}")
                    ])
                except Exception:
                    pass
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Вот список наших курсов. Нажмите на название, чтобы узнать подробности:", reply_markup=reply_markup)
        return 

    # Если это обычный ответ (не список курсов)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    await asyncio.sleep(0.5) 
    
    await update.message.reply_text(ai_response)
    return

async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает запросы от Web App: получение списка курсов или регистрация."""
    web_app_data = update.message.web_app_data
    if not web_app_data:
        return

    user_id = str(update.effective_user.id)
    data_received = web_app_data.data
    logger.info(f"Received data from Web App from user {user_id}: {data_received}")

    # --- 1. Запрос списка курсов ---
    if data_received == "GET_COURSES":
        # Используем текущую MOCK_DB для списка курсов
        courses_list = ""
        for cid, course in data_manager.MOCK_DB_SCHOOL["courses"].items():
            courses_list += f"{cid}: {course['name']}\n"

        response_text = f"[LIST_COURSES_START]\n{courses_list}"
        await update.message.reply_web_app_data(response_text)
        return

    # --- 2. Регистрация на курс ---
    if data_received.startswith("WEB_REGISTER:"):
        course_id = data_received.split(":")[1]

        # Проверяем, не записан ли пользователь
        registration_check = data_manager.check_user_registration_status(user_id)
        if "Вы записаны на курс" in registration_check:
            response_text = registration_check
        else:
            # Выполняем регистрацию
            registration_result = data_manager.register_user_for_course(user_id, course_id)
            if registration_result.get("status") == "success":
                course_name = data_manager.MOCK_DB_SCHOOL['courses'][course_id]['name']
                response_text = f"✅ Вы успешно записаны на курс '{course_name}'!"
            else:
                response_text = f"❌ Ошибка при записи: {registration_result.get('error', 'Неизвестная ошибка.')}"

        # Отправляем результат обратно Web App
        await update.message.reply_web_app_data(response_text)
        return

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатия на inline-кнопки."""
    query = update.callback_query
    await query.answer() 

    data = query.data
    logger.info(f"Callback received: {data}")
    user_id = str(query.from_user.id) 

    # --- СЛУЧАЙ 1: ПОДРОБНЕЕ О КУРСЕ (COURSE_DETAILS) ---
    if data.startswith("COURSE_DETAILS:"):
        
        course_id = data.split(":")[1]
        course_details_dict = data_manager.get_course_details(course_id)
        
        if "error" in course_details_dict:
            response_text = course_details_dict["error"]
            reply_markup = None
        else:
            # Форматируем детали и добавляем кнопки "Записаться" и "Назад"
            response_text = (
                f"Детали курса: {course_details_dict.get('name', 'N/A')}\n"
                f"Продолжительность: {course_details_dict.get('duration', 'N/A')}\n"
                f"Расписание: {course_details_dict.get('schedule', 'N/A')}\n"
                f"Преподаватель: {course_details_dict.get('instructor', 'N/A')}\n"
                f"Статус: {course_details_dict.get('status', 'N/A')}\n\n"
            )
            
            # Создаем клавиатуру с кнопками "Записаться" и "Назад"
            keyboard = [
                [InlineKeyboardButton("Записаться", callback_data=f"REGISTER_COURSE:{course_id}")],
                [InlineKeyboardButton("⬅️ Назад к списку", callback_data="GO_HOME")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
        await query.edit_message_text(response_text, reply_markup=reply_markup)
        return

    # --- СЛУЧАЙ 2: ПОПЫТКА ЗАПИСИ (REGISTER_COURSE) ---
    elif data.startswith("REGISTER_COURSE:"):
        
        course_id = data.split(":")[1]
        
        # 1. Проверяем, не записан ли пользователь уже
        registration_check = data_manager.check_user_registration_status(user_id)
        
        if "Вы записаны на курс" in registration_check:
            await query.edit_message_text(registration_check)
            return
            
        # 2. Если не записан, сохраняем ID курса в контексте пользователя и запрашиваем данные
        context.user_data['pending_registration_course_id'] = course_id
        
        response_text = f"Отлично! Вы выбрали курс '{data_manager.MOCK_DB_SCHOOL['courses'][course_id]['name']}'. Пожалуйста, введите Ваше полное имя и номер телефона через запятую (например: Иван Петров, +79991234567)."
        
        # Создаем клавиатуру с кнопкой "Отмена"
        keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="GO_HOME")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(response_text, reply_markup=reply_markup)
        return
        
    elif data == "GO_HOME":
        # При нажатии "Назад" мы должны снова вызвать LLM (или заглушку) для генерации списка
        
        # Временно используем заглушку для генерации списка, чтобы не тратить квоту LLM
        list_text = ""
        for cid, course_data in data_manager.MOCK_DB_SCHOOL["courses"].items():
            list_text += f"{cid}: {course_data['name']}\n"
        
        ai_response = f"[LIST_COURSES_START]\n{list_text}"
        
        # парсинг и отправка списка
        LIST_START_MARKER = "[LIST_COURSES_START]"
        if LIST_START_MARKER in ai_response:
            list_text_parsed = ai_response.split(LIST_START_MARKER)[-1].strip()
            keyboard = []
            for line in list_text_parsed.split('\n'):
                if ":" in line:
                    try:
                        course_id, course_name_full = line.split(":", 1)
                        course_id = course_id.strip()
                        course_name = course_name_full.strip()
                        keyboard.append([
                            InlineKeyboardButton(course_name, callback_data=f"COURSE_DETAILS:{course_id}")
                        ])
                    except Exception:
                        pass
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Вот список наших курсов. Нажмите на название, чтобы узнать подробности:", reply_markup=reply_markup)
            return

    # обработка неизвестной кнопки
    await query.edit_message_text("Неизвестное действие кнопки.")


async def handle_data_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ловит текстовый ввод от пользователя после запроса данных (Имя, Телефон)."""
    
    # проверка ожидания данных 
    if 'pending_registration_course_id' not in context.user_data:
        # если лжидания нет, то передача управления
        await handle_message(update, context) 
        return

    user_text = update.message.text
    user_id = str(update.effective_user.id)
    
    course_id_to_register = context.user_data.pop('pending_registration_course_id') # извлечение и удаление состояния
    
    # парсинг введенных данных - надо добавить проверку
    parts = [p.strip() for p in user_text.split(',', 1)]
    
    if len(parts) < 2:
        await update.message.reply_text("Неверный формат. Пожалуйста, введите Имя и Телефон через запятую, как было запрошено. Или нажмите 'Отмена' в предыдущем сообщении.")
        return
        
    name = parts[0]
    phone = parts[1]
    
    # запись в БД
    registration_result = data_manager.register_user_for_course(user_id, course_id_to_register)
    
    # отправка подтверждения записи
    if registration_result.get("status") == "success":
        response_text = (f"🎉 Запись подтверждена!\n"
                         f"Курс: {data_manager.MOCK_DB_SCHOOL['courses'][course_id_to_register]['name']}\n"
                         f"Имя: {name}\n"
                         f"Телефон: {phone}\n"
                         f"Дата записи: {registration_result['date']}.")
    else:
        response_text = f"❌ Не удалось завершить запись: {registration_result.get('error', 'Неизвестная ошибка.')}"

    # сообщение с кнопкой "назад"
    keyboard = [[InlineKeyboardButton("⬅️ Назад к списку", callback_data="GO_HOME")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(response_text, reply_markup=reply_markup)
    
    # очистка состояния, если ошибка
    if 'pending_registration_course_id' in context.user_data:
        del context.user_data['pending_registration_course_id']


def main() -> None:
    """запуск бота"""
    
    if not TELEGRAM_TOKEN:
        logger.critical("Запуск невозможен: TELEGRAM_TOKEN не установлен.")
        return
        
    # ... (проверки токенов)
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # регистрация обработчиков
    application.add_handler(CommandHandler("start", start_command))
    
    # 1. Обработчик для Web App данных
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    
    # 2. Обработчик для сбора данных (должен идти ПЕРВЫМ для текстовых сообщений, когда ждем ввод)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_data_input)) 
    
    # 3. Обработчик для обычных текстовых запросов (когда НЕ ждем ввод)
    # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # 4. Обработчик для кнопок
    application.add_handler(CallbackQueryHandler(button_callback)) 

    logger.info("Бот запущен и ожидает сообщений...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()