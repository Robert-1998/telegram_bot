import logging

logger = logging.getLogger(__name__)

MOCK_DB_SCHOOL = {
    "courses": {
        "acting_basic": {
            "name": "Основы Актерского Мастерства",
            "duration": "3 месяца",
            "schedule": "Пн/Ср, 19:00",
            "instructor": "Иванов А.С.",
            "status": "Открыта запись"
        },
        "voice_tech": {
            "name": "Техника Голоса и Речи",
            "duration": "1 месяц",
            "schedule": "Вт/Чт, 10:00",
            "instructor": "Петрова Е.В.",
            "status": "Набор завершен"
        },
        "improvisation": {
            "name": "Импровизация для начинающих",
            "duration": "4 недели",
            "schedule": "Сб, 14:00",
            "instructor": "Сидоров Д.П.",
            "status": "Открыта запись"
        }
    },
    "registrations": {
        "123456789": {"course_id": "acting_basic", "date": "2024-11-01"},
        "987654321": {"course_id": "voice_tech", "date": "2024-10-20"},
    }
}

def get_course_details(course_id: str) -> dict:
    """
    Предоставляет подробную информацию о конкретном курсе по его ID в виде словаря.
    """
    course_data = MOCK_DB_SCHOOL["courses"].get(course_id)
    
    if course_data:
        logger.info(f"DB Query: Found details for course ID: {course_id}")
        return course_data
    else:
        available_ids = ', '.join(MOCK_DB_SCHOOL['courses'].keys())
        return {"error": f"Курс с ID '{course_id}' не найден. Попробуйте один из этих ID: {available_ids}"}

def check_user_registration_status(user_telegram_id: str) -> dict:
    """
    Проверяет запись пользователя, возвращая словарь.
    """
    registration_data = MOCK_DB_SCHOOL["registrations"].get(user_telegram_id)
    
    if registration_data:
        course_id = registration_data['course_id']
        course_name = MOCK_DB_SCHOOL["courses"].get(course_id, {}).get("name", "Неизвестный курс")
        logger.info(f"DB Query: Found registration for user ID: {user_telegram_id}")
        return {
            "user_id": user_telegram_id,
            "course_name": course_name,
            "course_id": course_id,
            "registration_date": registration_data['date']
        }
    else:
        return {"error": f"Пользователь {user_telegram_id} не найден в списке регистраций."}

def register_user_for_course(user_telegram_id: str, course_id: str) -> dict:
    """
    Имитация запись пользователя на курс.
    """
    user_id = str(user_telegram_id)
    
    if course_id not in MOCK_DB_SCHOOL["courses"]:
        logger.warning(f"Attempted registration for non-existent course ID: {course_id}")
        return {"error": f"Курс с ID '{course_id}' не существует."}
        
    if user_id in MOCK_DB_SCHOOL["registrations"]:
        # Если пользователь уже записан, просто возвращаем его текущую запись
        logger.info(f"User {user_id} already registered for {MOCK_DB_SCHOOL['registrations'][user_id]['course_id']}. Returning existing record.")
        return {"status": "already_registered", "details": MOCK_DB_SCHOOL["registrations"][user_id]}
        
    # Имитация успешной записи
    MOCK_DB_SCHOOL["registrations"][user_id] = {
        "course_id": course_id,
        "date": "Сегодня (Тестовая запись)"
    }
    logger.info(f"SUCCESS: User {user_id} registered for course {course_id}.")
    
    # Возвращаем дату, чтобы main.py мог ее использовать
    return {"status": "success", "course_id": course_id, "user_id": user_id, "date": "Сегодня (Тестовая запись)"}