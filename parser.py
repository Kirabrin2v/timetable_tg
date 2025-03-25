import requests
import bs4
import re
import json
import time, datetime
import sys
import random

base_url = 'https://guspoliteh.ru/studentu/raspisanie-zanyatiy/'

all_lessons = json.load(open("lessons.json", encoding="UTF-8"))

group_name_to_id = {} # Сопоставление названия группы и айди
group_id_to_name = {}
group_ids = [] # Список айди всех групп
index_group_id = random.randint(0, 53) # Индекс обрабатываемого в текущий момент айди


time_check_last_group = 0
interval_between_groups = 15

time_last_check_shedule = 0
interval_check_shedule = 10

plus_day_now = 0

count_days_check_shedule = 5 # На сколько дней вперёд проверять расписание

ONE_DAY = datetime.timedelta(days=1)

date_start_search = datetime.date.today()

def write_permanent_memory():
    with open("lessons.json", "w", encoding="UTF-8") as file:
        json.dump(all_lessons, file, ensure_ascii=False, indent=4)

def delete_unused_dates() -> None:
    dates = list(all_lessons.keys())
    for date_str in dates:
        year, month, day = map(int, date_str.split("-"))
        date = datetime.date(year, month, day)
        if date < date_start_search:
            print("Удалил", date_str)
            del all_lessons[date_str]

    write_permanent_memory()

def update_names_ids() -> None:
    # Парсит с сайта айди и названия групп
    global group_ids
    response = requests.get(base_url) # Отправляем get-запрос
    text = response.text # Получаем html-страницу
    soup = bs4.BeautifulSoup(text, 'html.parser') # Создаём объект BeautifulSoup для парсинга html
    for element in soup.find(id="sel_group"): # Перебираем все группы и их айди
        if type(element) is bs4.element.Tag: # Если элемент нужного типа, записываем в переменные айди и имя группы
            group_id, name_group = int(element["value"]), element.text
            if group_id != 0:
                group_id = str(group_id)
                group_name_to_id[name_group] = group_id
                group_id_to_name[group_id] = name_group
    group_ids = list(group_name_to_id.values())

def processing_update_shedule(old_shedule: list, new_shedule: list, group_name: str, date_str: str, answs: list) -> None:
    if old_shedule != new_shedule and len(new_shedule) > 0:
        if old_shedule == []:
            type_update = "add_shedule"
        else:
            type_update = "update_shedule"
        answs.append({"old_lessons": old_shedule, "type": type_update, "group_name": group_name, "date": date_str, "lessons": new_shedule})
        
def get_schedule(group_id: str, date: str) -> list:
    # Парсит с сайта расписание
    params = {"id": group_id, "date": date, "modal2": False} # Параметры POST-запроса
    response = requests.post(base_url, params) # Отправляем POST-запрос
    text = response.text # Получаем html-текст
    soup = bs4.BeautifulSoup(text, 'html.parser') # Создаём объект BeautifulSoup для парсинга html

    lessons = [] # Список всех уроков для данного айди и даты
    lessons_objects = soup.findAll("div", {"class": "rpanel"}) # Ищем элементы по названию класса
    if len(lessons_objects) < 2: return [] # Если не указаны предметы, возвращает пустой список

    group_name = lessons_objects[1].find(align="center").text # По позиции ищем название группы
    if group_name != "":
        for element in lessons_objects[2:]: # Перебираем для каждого предмета номер, название, аудиторию и преподавателя
            lesson_raw = element.findAll(align="center")
            queue_number = lesson_raw[0].text
            if len(lesson_raw[1].text.split(" (")) >= 2:
                name_lesson = " (".join(lesson_raw[1].text.split(" (")[:-1])
                audience = lesson_raw[1].text.split(" (")[-1].replace(")", "") # Берём текст после последней скобки, как номер аудитории. Убираем скобки
            else:
                name_lesson = None
                audience = None
            teacher = lesson_raw[2].text
            if teacher == "":
                teacher = None
            if queue_number and name_lesson:
                lessons.append({"queue_number": queue_number, "name_lesson": name_lesson,
                                "audience": audience, "teacher": teacher})
    return lessons

def main(requests: list, answs: list) -> None:
    global time_check_last_group, time_last_check_shedule, plus_day_now, date_start_search, index_group_id
    print("Парсер запущен")
    try:
        delete_unused_dates()
        while True:
            if len(requests) != 0:
                request = requests.pop(0)
                
            if plus_day_now != 0 or time.time() - time_check_last_group >= interval_check_shedule: # Проверяем очередную группу спустся interval_check_shedule секунд после прошлой
                update_names_ids() # Обновляем сопоставлние айди и названия групп

                group_id = str(group_ids[index_group_id]) # Записываем в переменную айди, который нужно обработать

                if index_group_id == 0:
                    date_start_search = datetime.date.today()
                if time.time() - time_last_check_shedule > interval_check_shedule:
                    print(group_id)
                    time_last_check_shedule = time.time()
                # Просматриваем расписание для текущего айди на count_days_check_shedule дней вперёд

                    date_str = (date_start_search + ONE_DAY*plus_day_now).strftime("%Y-%m-%d") # Приводим текущую дату в нужный формат
                    plus_day_now = (plus_day_now + 1) % (count_days_check_shedule + 1)
                    if plus_day_now == 0:
                        index_group_id = (index_group_id + 1) % len(group_ids) # Вычисляем индекс следующего айди
                        time_check_last_group = time.time()

                    # print(date_str, group_id)
                    lessons = get_schedule(group_id, date_str) # Получаем список предметов в текущий день
                    # print("Лессонс", lessons)
                    if date_str in all_lessons:
                        if group_id in all_lessons[date_str]: # Обновляем запись и обрабатываем событие об изменении данных
                            old_lessons = all_lessons[date_str][group_id]
                            processing_update_shedule(old_lessons, lessons, group_id_to_name[group_id], date_str, answs)
                        all_lessons[date_str][group_id] = lessons


                    else: # Если записи с текущими параметрами нет, создаём её, но не обрабатываем событие об изменении данных
                        all_lessons[date_str] = {group_id: lessons}

                    write_permanent_memory()

    except Exception as e:
        answs.append({"type": "error", "error": e})
        print("Ошибка:", e)
        sys.exit()