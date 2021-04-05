import sys

import vk_api
import csv
import re
import datetime
from charset_normalizer import CharsetNormalizerMatches as CnM

# Author: Nek-12 on Github:
# https://github.com/Nek-12
# Created on Mar 18, 2021

LOGIN_REQ_STR = """Использовать аутентификацию пользователя? \n
В этом случае понадобится ваш номер телефона, пароль.\n
Необходимо, чтобы была отключена двухфакторная аутентификация. \n
При аутентификации пользователя можно получать число участников приватных и закрытых групп.\n
При аутентификации без пароля - только публичных. Пароль и логин нигде не сохраняется."""

SERVICE_TOKEN = '4622f2984622f2984622f2985146541d29446224622f2982671f14f77062bd02f2c0192'
APP_ID = 7794609

INPUT_FILE_HEADER_GROUP_TITLE = "Название"
INPUT_FILE_HEADER_LINK = "Ссылка"
INPUT_FNAME = "Input.csv"
OUTPUT_FNAME = "Output.csv"
FILE_ERR_STR = f"""Файл {INPUT_FNAME} не найден или пуст. В папке со скриптом был создан новый файл {INPUT_FNAME}\n
В файле должна быть таблица, экспортированная в csv в формате\n
|{INPUT_FILE_HEADER_GROUP_TITLE}|{INPUT_FILE_HEADER_LINK}| (без разделителей). Можно без заголовков."""

FIELDNAMES = ['Название', 'Ссылка', 'Количество участников', 'Последний пост', 'Первый пост']
DATE_ERR_STR = "Не удалось загрузить дату. Возможно, она недоступна? Пропускаю."

ENC_WARN = """ВНИМАНИЕ! Кодировка файла - не UTF-8. \n
Скорее всего в символах, отличных от латыни - будут ошибки!\n
Рекомендуется использовать UTF-8"""


def date_from_timestamp(timestamp: float):
    return datetime.date.fromtimestamp(timestamp)


def to_str(d: datetime.date):
    return f"{d.day}.{d.month}.{d.year}"


def latest_date_str(items: list):
    # date of the 1st post
    date1 = date_from_timestamp(float(items[0]['date']))
    if len(items) > 1:
        # the post might be pinned, so we check the second one
        date2 = date_from_timestamp(float(items[1]['date']))
        if date2 > date1:
            return to_str(date2)
    return to_str(date1)


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


def parse_arg(arg: str):
    if arg == "-y":
        return True
    elif arg == "-n":
        return False
    else:
        raise ValueError(arg)


use_auth = None
use_cp1251 = None
args = sys.argv
enc = None
vk = None
data = []

try:
    use_cp1251, use_auth = parse_arg(args[1]), parse_arg(args[2])
except ValueError as exc:
    print(f"Неверный аргумент: {exc.args[0]}")
    exit(-1)
except IndexError:
    pass

try:
    enc = CnM.from_path(INPUT_FNAME).best().first().encoding
    if enc != 'utf-8':
        print("\n\n", ENC_WARN, "\n\n")
        if use_cp1251 is None:
            use_cp1251 = yes_no("Использовать cp1251 вместо текущей кодировки?")
        if use_cp1251:
            enc = 'cp1251'
    # parse the file with group IDs
    print("Используется кодировка: ", enc)
    with open(INPUT_FNAME, 'r', newline='', encoding=enc) as csvf:
        dialect = csv.Sniffer().sniff(csvf.read(1024))
        csvf.seek(0)
        reader = csv.reader(csvf, dialect=dialect)
        for row in reader:
            if row[0] == INPUT_FILE_HEADER_GROUP_TITLE:
                continue
            data.append({FIELDNAMES[0]: row[0],  # name
                         FIELDNAMES[1]: row[1],  # link
                         FIELDNAMES[2]: None,  # memcount
                         FIELDNAMES[3]: None,  # last
                         FIELDNAMES[3]: None})  # first

    # remove blank lines
    data = list(filter(lambda el: len(el[FIELDNAMES[1]]) > 2, data))

    for dictionary in data:
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

        if vk is None:
            if use_auth is None:
                use_auth = yes_no(LOGIN_REQ_STR)
            if use_auth:
                login = input("Введите номер телефона или e-mail:").strip()
                passw = input("Введите пароль:").strip()
                vk = vk_api.VkApi(login=login, password=passw)
                vk.auth()
            else:
                vk = vk_api.VkApi(token=SERVICE_TOKEN,
                                  app_id=APP_ID)

        try:
            print(f"\n\nГруппа: {dictionary[FIELDNAMES[0]]}")
            response = vk.method("groups.getMembers", {
                "group_id": gid,
                "count": 0  # only need count
            })  # max 3 requests/second, blocks the script
            count = response.get('count')
            print(f"Подписчиков:  {count}")
        except Exception as e:
            print(f"Не удалось получить подписчиков для {gid}.\n Пропускаю.", e)
            count = None

        dictionary[FIELDNAMES[2]] = count

        offset = 0
        params = {
            "count": 2,  # get pinned post and the post after it
        }
        if gid.isdigit():
            params['owner_id'] = -int(gid)
        else:
            params['domain'] = gid

        try:
            response = vk.method("wall.get", params)
            total_posts = response['count']
            print("Всего постов: ", total_posts)
            date = latest_date_str(response['items'])
            print("Дата последнего поста: ", date)
            dictionary[FIELDNAMES[3]] = date
            # obtain the first post date
            params['offset'] = total_posts - 1
            response = vk.method("wall.get", params)
            date = latest_date_str(response['items'])
            dictionary[FIELDNAMES[4]] = date
            print("Дата первого поста: ", date)
        except Exception as e:
            print(DATE_ERR_STR, '\n', f"URL: {url}, err: \n{e}")

    # end the loop, save the data
    with open(OUTPUT_FNAME, 'w', newline='', encoding=enc) as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
        writer.writeheader()
        for dictionary in data:
            writer.writerow(dictionary)

    print(f"Файл был успешно сохранен. Всего обработано {len(data)} записей.")

except FileNotFoundError as e:
    print(FILE_ERR_STR, '\n', e)
    with open(INPUT_FNAME, 'w', newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[INPUT_FILE_HEADER_GROUP_TITLE,
                                               INPUT_FILE_HEADER_LINK], dialect=csv.excel)
        writer.writeheader()
except Exception as e:
    print('Произошла ошибка выполнения скрипта: ')
    print(e)
    exit(-1)
