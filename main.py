import vk_api
import csv
import re
import datetime

# Author: Nek-12 on Github:
# https://github.com/Nek-12
# Created on Mar 18, 2021

LOGIN_REQ_STR = \
    "Использовать аутентификацию пользователя? \n" \
    "В этом случае понадобится ваш номер телефона, пароль.\n" \
    "Необходимо, чтобы была отключена двухфакторная аутентификация. \n" \
    "При аутентификации пользователя можно получать число участников приватных и закрытых групп.\n" \
    "При аутентификации без пароля - только публичных. Пароль и логин нигде не сохраняется."
SERVICE_TOKEN = '4622f2984622f2984622f2985146541d29446224622f2982671f14f77062bd02f2c0192'
APP_ID = 7794609

INPUT_FILE_HEADER_GROUP_TITLE = "Название"
INPUT_FILE_HEADER_LINK = "Ссылка"
INPUT_FNAME = "Input.csv"
OUTPUT_FNAME = "Output.csv"
FILE_ERR_STR = \
    f"Файл {INPUT_FNAME} не найден или пуст. В папке со скриптом был создан новый файл {INPUT_FNAME}\n" \
    f"В файле должна быть таблица, экспортированная в csv в формате" \
    f" |{INPUT_FILE_HEADER_GROUP_TITLE}|{INPUT_FILE_HEADER_LINK}| (без разделителей). Можно без заголовков."
FIELDNAMES = ['Название', 'Ссылка', 'Количество участников', 'Последний пост', 'Первый пост']
DATE_ERR_STR = "Не удалось загрузить дату. Возможно, она недоступна? Пропускаю."


def date_str_from_response(response_dict: dict):
    item = response_dict['items'][0]['date']
    d = datetime.date.fromtimestamp(float(item))
    return f"{d.day}.{d.month}.{d.year}"


def yes_no(msg: str):
    while True:
        print(msg)
        ans = input("Введите Y (да) или N (нет):\n")
        if ans.lower() == 'y':
            return True
        elif ans.lower() == 'n':
            return False
        else:
            print("Неверный ввод.\n\n\n")


vk = None
data = []
try:
    if yes_no(LOGIN_REQ_STR):
        login = input("Введите номер телефона или e-mail:").strip()
        passw = input("Введите пароль:").strip()
        vk = vk_api.VkApi(login=login, password=passw)
        vk.auth()
    else:
        vk = vk_api.VkApi(token=SERVICE_TOKEN,
                          app_id=APP_ID)

    # parse the file with group IDs
    with open(INPUT_FNAME, 'r', newline='') as csvf:
        reader = csv.reader(csvf, delimiter=',', quotechar="\"")
        for row in reader:
            if row[0] == INPUT_FILE_HEADER_GROUP_TITLE:
                continue
            data.append({FIELDNAMES[0]: row[0],  # name
                         FIELDNAMES[1]: row[1],  # link
                         FIELDNAMES[2]: None,  # memcount
                         FIELDNAMES[3]: None,  # first
                         FIELDNAMES[3]: None})  # last

    # remove blank lines
    data = list(filter(lambda el: len(el[FIELDNAMES[1]]) > 2, data))

    for dictionary in data:
        print(f"\n\nГруппа: {dictionary[FIELDNAMES[0]]}")
        url = dictionary[FIELDNAMES[1]]
        try:
            print(url)
            gid = re.sub("public|club", "", re.split('/', url.strip())[-1])
            if len(gid) < 2:
                raise IndexError
        except IndexError as e:
            print(f"Попалась неверная ссылка: '{url}'. Пропускаю")
            continue
        # get the count
        response = vk.method("groups.getMembers", {
            "group_id": gid,
            "count": 0  # only need count
        })  # max 3 requests/second, blocks the script
        count = response.get('count')
        print(f"Подписчиков:  {count}")
        if count is None:
            print(f"Неверное количество подписчиков для {gid}: {count}.\n Пропускаю.")

        dictionary[FIELDNAMES[2]] = count

        offset = 0
        params = {
            "count": 1,
        }
        if gid.isdigit():
            params['owner_id'] = -int(gid)
        else:
            params['domain'] = gid

        try:
            response = vk.method("wall.get", params)
            total_posts = response['count']
            print("Всего постов: ", total_posts)
            date = date_str_from_response(response)
            print("Дата последнего поста: ", date)
            dictionary[FIELDNAMES[3]] = date
            # obtain the first post date
            params['offset'] = total_posts - 1
            response = vk.method("wall.get", params)
            date = date_str_from_response(response)
            dictionary[FIELDNAMES[4]] = date
            print("Дата первого поста: ", date)
        except Exception as e:
            print(DATE_ERR_STR, '\n', f"URL: {url}, err: {e}")

    # end the loop, save the data
    with open(OUTPUT_FNAME, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
        writer.writeheader()
        for dictionary in data:
            writer.writerow(dictionary)

    print(f"Файл был успешно сохранен. Всего обработано {len(data)} записей.")

except FileNotFoundError as e:
    print(FILE_ERR_STR, '\n', e)
    with open(INPUT_FNAME, 'w', newline='') as f:
        writer = csv.DictWriter(csvfile, fieldnames=[INPUT_FILE_HEADER_GROUP_TITLE,
                                                     INPUT_FILE_HEADER_LINK])
        writer.writeheader()
except Exception as e:
    print('Произошла ошибка выполнения скрипта: ')
    print(e)
    exit(-1)
