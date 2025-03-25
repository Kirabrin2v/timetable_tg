import configparser
import telebot
import multiprocessing, threading
import json
import time
import parser

config = configparser.ConfigParser()
config.read("config.ini")

tg_key = config.get("VARIABLES", "tg_key")
bot = telebot.TeleBot(tg_key)

subscribers = json.load(open("subscribers.json", encoding="UTF-8"))

#Создаём общие для модулей переменные
manager = multiprocessing.Manager()
requests = manager.list()
answs = manager.list()


parser_process = multiprocessing.Process(target=parser.main, args=(requests, answs))
parser_process.start()


def transfom_lessons_to_text(type_update: str, group_name: str, date: str, lessons: list, old_lessons: list = None) -> str:
    if not old_lessons:
        old_lessons = []

    if type_update == "add_shedule":
        text = "`Появилось` расписание!\n\n" +\
                f"{group_name} ({date})\n\n"

        for lesson in lessons:
            queue_number = lesson["queue_number"]
            name_lesson = lesson["name_lesson"]
            audience = lesson["audience"]
            teacher = lesson["teacher"]

            text += f"`{queue_number}`\n" +\
                    f"`{name_lesson} ({audience})`\n" +\
                    f"{teacher}\n\n"

        return text

    elif type_update == "update_shedule":
        text = "`Обновилось` расписание!\n\n" +\
                f"{group_name} ({date})\n\n"
        
        old_lessons.extend([{"queue_number": None, "name_lesson": None, "audience": None, "teacher": None}] * (len(lessons) - len(old_lessons)))
        lessons.extend([{"queue_number": None, "name_lesson": None, "audience": None, "teacher": None}] * (len(old_lessons) - len(lessons)))

        for i in range(len(lessons)):
            print(old_lessons[i])
            queue_number1 = old_lessons[i]["queue_number"] or "Отсутствует"
            queue_number2 = lessons[i]["queue_number"] or "Отсутствует"

            name_lesson1 = old_lessons[i]["name_lesson"] or "Отсутствует"
            name_lesson2 = lessons[i]["name_lesson"] or "Отсутствует"

            audience1 = old_lessons[i]["audience"] or "Отсутствует"
            audience2 = lessons[i]["audience"] or "Отсутствует"

            teacher1 = old_lessons[i]["teacher"] or "Отсутствует"
            teacher2 = lessons[i]["teacher"] or "Отсутствует"

            text += f"{queue_number1} -> `{queue_number2}`\n" +\
                    f" {name_lesson1} ({audience1}) -> `{name_lesson2} ({audience2})`\n" +\
                    f"{teacher1} -> {teacher2}\n\n"

        return text

    #text = f"{type_update_text} раписание для {group_name} {date}:\n"


def send_messages_tg():
    pass

def monitor_shared_data() -> None:
    global parser_process
    # Фоновый процесс для отслеживания изменений в answs
    last_status = None
    while True:
        if len(answs) != 0:
            answ_object = answs.pop(0)
            if answ_object["type"] == "error":
                if not parser_process.is_alive():
                    time.sleep(900)
                    parser_process = multiprocessing.Process(target=parser.main, args=(requests, answs))
                    parser_process.start()

            else:
                group_name = answ_object["group_name"]
                text = transfom_lessons_to_text(answ_object["type"], group_name, answ_object["date"], answ_object["lessons"], answ_object["old_lessons"])

                ids = subscribers[group_name]
                print(ids)
                for i in range(len(ids)):
                    print("Отправляю сообщение:", ids[i])
                    bot.send_message(ids[i], text, parse_mode="Markdown")



        time.sleep(1)  # Проверяем раз в секунду

thread_monitor = threading.Thread(target=monitor_shared_data, daemon=True)
thread_monitor.start()

@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    bot.reply_to(message, """\
Я - бот, помогающий отслеживать расписание.
Доступные команды:
/subscribe [название_группы] - подписаться на обновления расписания у группы
/unscribe [название_группы] - отписаться от обновлений расписания у группы
""")

@bot.message_handler(commands=['subscribe'])
def subscribe_to_updates(message):
    text = message.text
    tg_id = message.from_user.id
    print(f"{tg_id}: {text}")
    args = text.split()
    answ = None
    if (len(args) > 1):
        args = args[1:]
        group_name = args[0].upper()
        if group_name in subscribers:
            if tg_id not in subscribers[group_name]:
                subscribers[group_name].append(tg_id)
                with open("subscribers.json", "w", encoding="UTF-8") as file:
                    json.dump(subscribers, file, ensure_ascii=False, indent=4)

                answ = f"Вы успешно подписались на изменения расписания у группы {group_name}"
            else:
                answ = f"Вы уже подписаны на изменение расписания у группы {group_name}"
        else:
            answ = "Группы с таким именем не существует"
    else:
        answ = "Вы не указали название группы, на которую хотите подписаться"

    if answ:
        bot.reply_to(message, answ)
    #print(message.text)

@bot.message_handler(commands=['unscribe'])
def unscribe_to_updates(message):
    text = message.text
    tg_id = message.from_user.id
    print(f"{tg_id}: {text}")
    args = text.split()
    answ = None
    if (len(args) > 1):
        args = args[1:]
        group_name = args[0].upper()
        if group_name in subscribers:
            if tg_id in subscribers[group_name]:
                subscribers[group_name].remove(tg_id)
                with open("subscribers.json", "w", encoding="UTF-8") as file:
                    json.dump(subscribers, file, ensure_ascii=False, indent=4)

                    answ = f"Вы успешно отписались от уведомлений об изменении расписания у группы {group_name}"
            else:
                answ = f"Вы не подписаны на изменение расписания у группы {group_name}"
        else:
            answ = f"Группы '{group_name}' не существует"
    else:
        answ = "Вы не указали название группы, от которой хотите отписаться"

    if answ:
        bot.reply_to(message, answ)

@bot.message_handler(func=lambda message: True)
def echo_message(message):
    text = message.text
    tg_id = message.from_user.id
    print(f"{tg_id}: {text}")
    if message.text[0] == "/":
        bot.reply_to(message, "Неизвестная команда")
    else:
        bot.reply_to(message, """\
Доступные команды:
/subscribe [название_группы] - подписаться на обновления расписания у группы
/unscribe [название_группы] - отписаться от обновлений расписания у группы
""")


bot.infinity_polling()
