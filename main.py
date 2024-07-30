import pandas as pd
import telebot
from telebot import types
import datetime

# Чтение данных из файла Excel
file_path = 'номенклатура.xlsx'
sheets = pd.read_excel(file_path, sheet_name=None)

# Подготовка структуры данных
nomenclature = {}

for sheet_name, data in sheets.items():
    if sheet_name == "Сварка и химическая чистка":
        welding_data = data[data['Группа'].str.contains('сварка', case=False, na=False)]
        cleaning_data = data[data['Группа'].str.contains('чистка', case=False, na=False)]
        nomenclature['Сварка'] = {group: group_data.drop(columns=['Группа']).to_dict(orient='records') for
                                  group, group_data in welding_data.groupby(welding_data.columns[0])}
        nomenclature['Химическая чистка'] = {group: group_data.drop(columns=['Группа']).to_dict(orient='records') for
                                             group, group_data in cleaning_data.groupby(cleaning_data.columns[0])}
    else:
        groups = data.groupby(data.columns[0])
        nomenclature[sheet_name] = {
            group: group_data.drop(columns=[data.columns[0]]).to_dict(orient='records')
            for group, group_data in groups
        }

# Замените 'ВАШ_ТОКЕН_БОТА' на токен вашего бота
TOKEN = '7342533936:AAFL2r8r6vHs6EURgAf9X7llHnEPJLi9gy4'
# Замените 'ID_ЧАТА' на полученный ID чата (добавьте '-' перед идентификатором для группы)
CHAT_ID = '-1002149049054'
bot = telebot.TeleBot(TOKEN)

# Определяем отделы
DEPARTMENTS = list(nomenclature.keys())

user_data = {}
temp_data = {}


def create_start_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    start_button = types.KeyboardButton('/start')
    keyboard.add(start_button)
    return keyboard


def create_back_button():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data="back"))
    return keyboard


def add_newline(text, max_length=20):
    text = str(text)  # Преобразование текста в строку
    if text.replace('.', '', 1).isdigit():  # Если текст является числом
        return text
    words = text.split()
    result = ''
    line_length = 0
    for word in words:
        if line_length + len(word) > max_length:
            result += '\n'
            line_length = 0
        result += word + ' '
        line_length += len(word) + 1
    return result.strip()


@bot.message_handler(commands=['start'])
def send_welcome(message):
    keyboard = types.InlineKeyboardMarkup()
    buttons = [types.InlineKeyboardButton(text=add_newline(department), callback_data=f"department_{department}") for
               department in DEPARTMENTS]

    # Добавляем первые 3 кнопки в один ряд
    if len(buttons) >= 3:
        keyboard.add(*buttons[:3])

    # Добавляем оставшиеся кнопки по одной в ряд
    for button in buttons[3:]:
        keyboard.add(button)

    keyboard = types.InlineKeyboardMarkup()
    buttons = [types.InlineKeyboardButton(text=add_newline(department), callback_data=f"department_{department}") for
               department in DEPARTMENTS]
    keyboard.add(*buttons)
    bot.send_message(message.chat.id, "Привет! Выбери свое направление:", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith("department_"))
def department_selection(call):
    department = call.data.split("_")[1]
    user_id = call.from_user.id
    user_data[user_id] = {'department': department, 'products': []}
    temp_data[user_id] = {'department': department}

    if department == "Упаковка":
        select_category(call.message)
    else:
        send_group_selection(user_id, call.message)


def send_group_selection(user_id, message):
    department = user_data[user_id]['department']
    keyboard = types.InlineKeyboardMarkup()
    groups = list(nomenclature[department].keys())
    for i in range(0, len(groups), 3):
        buttons = [types.InlineKeyboardButton(text=add_newline(groups[j]), callback_data=f"group_{groups[j]}") for j in range(i, min(i+3, len(groups)))]
        keyboard.add(*buttons)
    keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data="back_to_department"))
    bot.send_message(message.chat.id, f"Выбран {department}. Теперь выбери группу продукции:", reply_markup=keyboard)


def select_category(message):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="Маркетплейс", callback_data="category_marketplace"))
    keyboard.add(types.InlineKeyboardButton(text="Опт", callback_data="category_wholesale"))
    bot.send_message(message.chat.id, "Выбери категорию:", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith("category_"))
def category_selection(call):
    category = call.data.split("_")[1]
    if category == "wholesale":
        category = "опт"
    elif category == "marketplace":
        category = "маркетплейс"

    user_id = call.from_user.id
    temp_data[user_id]['category'] = category
    send_group_selection(user_id, call.message)


@bot.callback_query_handler(func=lambda call: call.data.startswith("group_"))
def group_selection(call):
    user_id = call.from_user.id
    if user_id not in user_data:
        bot.send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, начни сначала.",
                         reply_markup=create_start_keyboard())
        return

    group = call.data.split("_")[1]
    department = user_data[user_id]['department']
    temp_data[user_id]['group'] = group
    items = nomenclature[department][group]

    print(f"Items in group '{group}' from department '{department}': {items}")

    subgroups = list(set(item.get('Подгруппа1', '') for item in items if pd.notna(item.get('Подгруппа1'))))
    subgroups.sort(key=str)  # Сортировка подгрупп для упорядоченности
    print(f"Subgroups found: {subgroups}")  # Отладка

    if not subgroups:
        bot.send_message(call.message.chat.id,
                         text=f"Выбрана группа {group}. Введи количество произведенной продукции:",
                         reply_markup=create_back_button())
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, product_quantity)
        return

    keyboard = types.InlineKeyboardMarkup()
    buttons = [types.InlineKeyboardButton(text=add_newline(subgroup), callback_data=f"subgroup1_{subgroup}") for
               subgroup in subgroups]

    if (department == "Слесарка" and group in ["резка", "гибка", "закатка"]) or \
            (group == "копчение" and department in ["Упаковка", "Сварка", "Химическая чистка",
                                                    "Полировка механическая"]):
        # Для указанных групп и отделов по 1 кнопке в ряд
        for button in buttons:
            keyboard.add(button)
    else:
        # Для всех остальных по 4 кнопки в ряд
        for i in range(0, len(buttons), 4):
            keyboard.add(*buttons[i:i + 4])

    keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data="back_to_department"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                          text=f"Выбрана группа {group}. Теперь уточни вид продукции:", reply_markup=keyboard)
    temp_data[user_id]['last_action'] = 'group_selection'


@bot.callback_query_handler(func=lambda call: call.data.startswith("subgroup1_"))
def subgroup1_selection(call):
    user_id = call.from_user.id
    if user_id not in user_data:
        bot.send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, начни сначала.",
                         reply_markup=create_start_keyboard())
        return

    subgroup1 = call.data.split("_")[1]
    department = user_data[user_id]['department']
    group = temp_data[user_id]['group']
    items = [item for item in nomenclature[department][group] if
             item.get('Подгруппа1') == (float(subgroup1) if subgroup1.replace('.', '', 1).isdigit() else subgroup1)]

    print(f"Items in subgroup1 '{subgroup1}' from group '{group}': {items}")  # Отладка

    temp_data[user_id]['subgroup1'] = subgroup1

    subsubgroups = list(set(item.get('Подгруппа2', '') for item in items if pd.notna(item.get('Подгруппа2'))))
    subsubgroups.sort(key=str)  # Сортировка подгрупп для упорядоченности
    print(f"Sub-subgroups found: {subsubgroups}")  # Отладка
    if not subsubgroups:
        bot.send_message(call.message.chat.id,
                         text=f"Выбрано: {group} → {subgroup1}. Введи количество произведенной продукции:",
                         reply_markup=create_back_button())
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, product_quantity)
        return

    keyboard = types.InlineKeyboardMarkup()
    buttons = [types.InlineKeyboardButton(text=add_newline(subsubgroup), callback_data=f"subgroup2_{subsubgroup}") for
               subsubgroup in subsubgroups]

    if (department == "Слесарка" and group in ["резка", "гибка", "закатка"] and subgroup1 in ["дымогенератор",
                                                                                              "попугай"]) or \
            (group == "копчение" and department in ["Упаковка", "Сварка", "Химическая чистка",
                                                    "Полировка механическая"]):
        # Для указанных групп и подгрупп по 1 кнопке в ряд
        for button in buttons:
            keyboard.add(button)
    else:
        # Для всех остальных по 2 кнопки в ряд
        for i in range(0, len(buttons), 2):
            keyboard.add(*buttons[i:i + 2])

    print(f"Buttons для subgroup2: {buttons}")  # Отладка
    keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data="back_to_group"))
    bot.send_message(call.message.chat.id,
                     text=f"Выбрано: {group} → {subgroup1}. Теперь выбери вид продукции:",
                     reply_markup=keyboard)
    temp_data[user_id]['last_action'] = 'subgroup1_selection'


@bot.callback_query_handler(func=lambda call: call.data.startswith("subgroup2_"))
def subgroup2_selection(call):
    user_id = call.from_user.id
    if user_id not in user_data:
        bot.send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, начни сначала.",
                         reply_markup=create_start_keyboard())
        return

    subgroup2 = call.data.split("_")[1]
    department = user_data[user_id]['department']
    group = temp_data[user_id]['group']
    subgroup1 = temp_data[user_id]['subgroup1']
    items = [item for item in nomenclature[department][group] if item.get('Подгруппа1') == (
        float(subgroup1) if subgroup1.replace('.', '', 1).isdigit() else subgroup1) and item.get('Подгруппа2') == (
                 float(subgroup2) if subgroup2.replace('.', '', 1).isdigit() else subgroup2)]

    print(f"Items в subgroup2 '{subgroup2}' из subgroup1 '{subgroup1}' и group '{group}': {items}")  # Отладка

    temp_data[user_id]['subgroup2'] = subgroup2

    bot.send_message(call.message.chat.id,
                     text=f"Выбрано: {group} → {subgroup1} → {subgroup2}. Введи количество произведенной продукции:",
                     reply_markup=create_back_button())
    bot.register_next_step_handler_by_chat_id(call.message.chat.id, product_quantity)
    temp_data[user_id]['last_action'] = 'subgroup2_selection'


def product_quantity(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, начни сначала.",
                         reply_markup=create_start_keyboard())
        return

    try:
        quantity = float(message.text)
        if quantity <= 0:
            raise ValueError("Количество должно быть положительным числом.")
    except ValueError:
        bot.send_message(message.chat.id, "Введите корректное количество (положительное число). Попробуйте еще раз:",
                         reply_markup=create_back_button())
        bot.register_next_step_handler_by_chat_id(message.chat.id, product_quantity)
        return

    department = user_data[user_id]['department']
    category = temp_data[user_id].get('category', 'не указано')
    group = temp_data[user_id]['group']
    subgroup1 = temp_data[user_id].get('subgroup1', '')
    subgroup2 = temp_data[user_id].get('subgroup2', '')

    items = [item for item in nomenclature[department][group] if item.get('Подгруппа1') == (
        float(subgroup1) if subgroup1.replace('.', '', 1).isdigit() else subgroup1) and (item.get('Подгруппа2', '') == (
        float(subgroup2) if subgroup2.replace('.', '', 1).isdigit() else subgroup2) or pd.isna(item.get('Подгруппа2')))]
    print(f"Items найденные для окончательного выбора: {items}")  # Отладка
    if items:
        product_name = items[0]['Товар для вывода в сообщение']
    else:
        product_name = f"{group} {subgroup1} {subgroup2}".strip()

    product_info = {
        'product_name': product_name,
        'quantity': quantity,
        'category': category
    }
    if 'products' not in temp_data[user_id]:
        temp_data[user_id]['products'] = []
    temp_data[user_id]['products'].append(product_info)

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="Добавить еще один вид продукции", callback_data="add_more"))
    keyboard.add(types.InlineKeyboardButton(text="Завершить ввод продукции", callback_data="finish_entry"))
    bot.send_message(message.chat.id, 'Хочешь ввести еще один вид продукции или завершить ввод?', reply_markup=keyboard)
    temp_data[user_id]['last_action'] = 'product_quantity'

@bot.callback_query_handler(func=lambda call: call.data == "add_more")
def ask_for_more(call):
    user_id = call.from_user.id
    department = user_data[user_id]['department']
    if department == "Упаковка":
        select_category(call.message)
    else:
        send_group_selection(user_id, call.message)
    temp_data[user_id]['last_action'] = 'add_more'


@bot.callback_query_handler(func=lambda call: call.data == "finish_entry")
def finish_entry(call):
    user_id = call.from_user.id
    user_data[user_id]['products'].extend(temp_data[user_id].get('products', []))
    temp_data[user_id]['products'] = []
    bot.send_message(call.message.chat.id, 'Введи дополнительную информацию, если есть, или введи "нет":',
                     reply_markup=create_back_button())
    bot.register_next_step_handler_by_chat_id(call.message.chat.id, additional_info)
    temp_data[user_id]['last_action'] = 'finish_entry'


def additional_info(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, начни сначала.",
                         reply_markup=create_start_keyboard())
        return

    additional_info_text = message.text
    user_data[user_id]['additional_info'] = additional_info_text

    bot.send_message(message.chat.id, 'Введи дату, за которую отчитываешься (формат ДД.ММ.ГГ):',
                     reply_markup=create_back_button())
    bot.register_next_step_handler_by_chat_id(message.chat.id, report_date)
    temp_data[user_id]['last_action'] = 'additional_info'


def report_date(message):
    user_id = message.from_user.id
    if user_id not in user_data:
        bot.send_message(message.chat.id, "Произошла ошибка. Пожалуйста, начни сначала.",
                         reply_markup=create_start_keyboard())
        return

    report_date_input = message.text
    try:
        # Попробуем преобразовать строку в дату с новым форматом
        report_date_obj = datetime.datetime.strptime(report_date_input, '%d.%m.%y')
    except ValueError:
        bot.send_message(message.chat.id, "Введите корректную дату в формате ДД.ММ.ГГ. Попробуйте еще раз:",
                         reply_markup=create_back_button())
        bot.register_next_step_handler_by_chat_id(message.chat.id, report_date)
        return

    # Форматируем дату в нужный формат
    formatted_date = report_date_obj.strftime('%d.%m.%y')
    user_data[user_id]['report_date'] = formatted_date

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="Посмотреть отчет", callback_data="review_report"))
    bot.send_message(message.chat.id, 'Дата введена. Проверь свой отчет.', reply_markup=keyboard)
    temp_data[user_id]['last_action'] = 'report_date'


@bot.callback_query_handler(func=lambda call: call.data == "review_report")
def review_report(call):
    user_id = call.from_user.id
    user = call.from_user
    data = user_data[user_id]
    report = (
        f"Отчет от {user.first_name} {user.last_name or ''} (@{user.username}):\n"
        f"Дата: {data['report_date']}\n"
        f"Отдел: {data['department']}\n"
    )
    report += "Продукция:\n"

    # Сортировка продуктов по категориям
    marketplace_products = [p for p in data['products'] if p['category'] == 'маркетплейс']
    wholesale_products = [p for p in data['products'] if p['category'] == 'опт']
    other_products = [p for p in data['products'] if p['category'] not in ['маркетплейс', 'опт']]

    if marketplace_products:
        report += "- Маркетплейс:\n"
        for product in marketplace_products:
            product_name = " ".join([part for part in product['product_name'].split() if part.lower() != 'nan'])
            report += f"  - {product_name}: {int(product['quantity'])} шт.\n"

    if wholesale_products:
        report += "- Опт:\n"
        for product in wholesale_products:
            product_name = " ".join([part for part in product['product_name'].split() if part.lower() != 'nan'])
            report += f"  - {product_name}: {int(product['quantity'])} шт.\n"

    if other_products:
        report += f"- Итого:\n"
        for product in other_products:
            product_name = " ".join([part for part in product['product_name'].split() if part.lower() != 'nan'])
            report += f"  - {product_name}: {int(product['quantity'])} шт.\n"

    report += f"Дополнительная информация: {data.get('additional_info', 'нет')}"

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="Подтвердить отчет", callback_data="confirm_report"))
    keyboard.add(types.InlineKeyboardButton(text="Удалить все и начать заново", callback_data="reset_all"))
    bot.send_message(call.message.chat.id, report, reply_markup=keyboard)
    temp_data[user_id]['last_action'] = 'review_report'

@bot.callback_query_handler(func=lambda call: call.data == "confirm_report")
def confirm_report(call):
    user_id = call.from_user.id
    user = call.from_user
    data = user_data[user_id]

    report = (
        f"Отчет от {user.first_name} {user.last_name or ''} (@{user.username}):\n"
        f"Дата: {data['report_date']}\n"
        f"Отдел: {data['department']}\n"
    )
    report += "Продукция:\n"

    # Сортировка продуктов по категориям
    marketplace_products = [p for p in data['products'] if p['category'] == 'маркетплейс']
    wholesale_products = [p for p in data['products'] if p['category'] == 'опт']

    if marketplace_products:
        report += "- Маркетплейс:\n"
        for product in marketplace_products:
            product_name = " ".join([part for part in product['product_name'].split() if part.lower() != 'nan'])
            report += f"  - {product_name}: {int(product['quantity'])} шт.\n"

    if wholesale_products:
        report += "- Опт:\n"
        for product in wholesale_products:
            product_name = " ".join([part for part in product['product_name'].split() if part.lower() != 'nan'])
            report += f"  - {product_name}: {int(product['quantity'])} шт.\n"

    report += f"Дополнительная информация: {data.get('additional_info', 'нет')}"

    try:
        bot.send_message(CHAT_ID, report)
        bot.send_message(call.message.chat.id,
                         "Твой отчет успешно отправлен! Ты молодец, спасибо за проделанную работу 👍",
                         reply_markup=create_start_keyboard())
    except telebot.apihelper.ApiTelegramException as e:

        bot.send_message(call.message.chat.id, f"Произошла ошибка при отправке отчета: {e}",
                         reply_markup=create_start_keyboard())

    # Очистка данных пользователя после отправки отчета
    del user_data[user_id]
    del temp_data[user_id]


@bot.callback_query_handler(func=lambda call: call.data == "reset_all")
def reset_all(call):
    user_id = call.from_user.id
    if user_id in user_data:
        del user_data[user_id]
    if user_id in temp_data:
        del temp_data[user_id]
    bot.send_message(call.message.chat.id, "Все данные удалены. Можешь начать заново.",
                     reply_markup=create_start_keyboard())


@bot.callback_query_handler(
    func=lambda call: call.data == "back" or call.data == "back_to_department" or call.data == "back_to_group")
def go_back(call):
    user_id = call.from_user.id
    if user_id not in temp_data:
        bot.send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, начни сначала.",
                         reply_markup=create_start_keyboard())
        return

    last_action = temp_data[user_id].get('last_action')
    if last_action == 'department_selection' or call.data == "back_to_department":
        send_welcome(call.message)
        del temp_data[user_id]
    elif last_action == 'category_selection' or call.data == "back_to_category":
        department_selection(call)
        del temp_data[user_id]['category']
    elif last_action == 'group_selection':
        send_group_selection(call.message)
        if 'group' in temp_data[user_id]:
            del temp_data[user_id]['group']

    last_action = temp_data[user_id].get('last_action')
    if last_action == 'department_selection' or call.data == "back_to_department":
        send_welcome(call.message)
        del temp_data[user_id]
    elif last_action == 'subgroup2_selection' or call.data == "back_to_group":
        department = user_data[user_id]['department']
        group = temp_data[user_id]['group']
        items = nomenclature[department][group]
        subgroups = list(set(item.get('Подгруппа1', '') for item in items if pd.notna(item.get('Подгруппа1'))))
        subgroups.sort(key=str)  # Сортировка подгрупп для упорядоченности
        keyboard = types.InlineKeyboardMarkup()
        buttons = [types.InlineKeyboardButton(text=add_newline(subgroup), callback_data=f"subgroup1_{subgroup}") for
                   subgroup in subgroups]

        if (department == "Слесарка" and group in ["резка", "гибка", "закатка"]) or \
                (group == "копчение" and department in ["Упаковка", "Сварка", "Химическая чистка",
                                                        "Полировка механическая"]):
            # Для указанных групп и отделов по 1 кнопке в ряд
            for button in buttons:
                keyboard.add(button)
        else:
            # Для всех остальных по 4 кнопки в ряд
            for i in range(0, len(buttons), 4):
                keyboard.add(*buttons[i:i + 4])

        keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data="back_to_department"))
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text=f"Группа {group} выбрана. Теперь выбери вид продукции:",
                              reply_markup=keyboard)
        if 'subgroup2' in temp_data[user_id]:
            del temp_data[user_id]['subgroup2']
    elif last_action == 'subgroup1_selection':
        department = user_data[user_id]['department']
        group = temp_data[user_id]['group']
        items = nomenclature[department][group]
        subgroup1 = temp_data[user_id]['subgroup1']
        subsubgroups = list(set(item.get('Подгруппа2', '') for item in items if pd.notna(item.get('Подгруппа2'))))
        subsubgroups.sort(key=str)  # Сортировка подгрупп для упорядоченности
        keyboard = types.InlineKeyboardMarkup()
        buttons = [types.InlineKeyboardButton(text=add_newline(subsubgroup), callback_data=f"subgroup2_{subsubgroup}")
                   for subsubgroup in subsubgroups]

        if (department == "Слесарка" and group in ["резка", "гибка", "закатка"] and subgroup1 in ["дымогенератор",
                                                                                                  "попугай"]) or \
                (group == "копчение" and department in ["Упаковка", "Сварка", "Химическая чистка",
                                                        "Полировка механическая", "Полировка механическая"]):
            # Для указанных групп и подгрупп по 1 кнопке в ряд
            for button in buttons:
                keyboard.add(button)
        else:
            # Для всех остальных по 2 кнопки в ряд
            for i in range(0, len(buttons), 2):
                keyboard.add(*buttons[i:i + 2])

        print(f"Buttons для subgroup2: {buttons}")  # Отладка
        keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data="back_to_group"))
        bot.send_message(call.message.chat.id, text=f"Выбрано: {group} → {subgroup1}. Теперь выбери вид продукции:",
                         reply_markup=keyboard)
        if 'subgroup1' in temp_data[user_id]:
            del temp_data[user_id]['subgroup1']
    elif last_action == 'group_selection':
        department = user_data[user_id]['department']
        keyboard = types.InlineKeyboardMarkup()
        groups = list(nomenclature[department].keys())
        buttons = [types.InlineKeyboardButton(text=add_newline(group), callback_data=f"group_{group}") for group in
                   groups]

        # Добавляем кнопки в зависимости от контекста
        for i in range(0, len(buttons), 3):
            keyboard.add(*buttons[i:i + 3])

        if len(buttons) % 3 != 0:
            keyboard.add(*buttons[-(len(buttons) % 3):])

        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                              text=f"Отдел {department} выбран. Теперь выберите группу продукции:",
                              reply_markup=keyboard)
        if 'group' in temp_data[user_id]:
            del temp_data[user_id]['group']
    elif last_action == 'product_quantity':
        department = user_data[user_id]['department']
        group = temp_data[user_id]['group']
        subgroup1 = temp_data[user_id]['subgroup1']
        items = [item for item in nomenclature[department][group] if
                 item.get('Подгруппа1') == (float(subgroup1) if subgroup1.replace('.', '', 1).isdigit() else subgroup1)]
        subsubgroups = list(set(item.get('Подгруппа2', '') for item in items if pd.notna(item.get('Подгруппа2'))))
        subsubgroups.sort(key=str)  # Сортировка подгрупп для упорядоченности
        if not subsubgroups:
            bot.send_message(call.message.chat.id,
                             text=f"Выбрано: {group} → {subgroup1}. Введи количество произведенной продукции:",
                             reply_markup=create_back_button())
            bot.register_next_step_handler_by_chat_id(call.message.chat.id, product_quantity)
        else:
            keyboard = types.InlineKeyboardMarkup()
            buttons = [
                types.InlineKeyboardButton(text=add_newline(subsubgroup), callback_data=f"subgroup2_{subsubgroup}") for
                subsubgroup in subsubgroups]

            if (department == "Слесарка" and group in ["резка", "гибка", "закатка"] and subgroup1 in ["дымогенератор",
                                                                                                      "попугай"]) or \
                    (group == "копчение" and department in ["Упаковка", "Сварка", "Химическая чистка",
                                                            "Полировка механическая"]):
                # Для указанных групп и подгрупп по 1 кнопке в ряд
                for button in buttons:
                    keyboard.add(button)
            else:
                # Для всех остальных по 2 кнопки в ряд
                for i in range(0, len(buttons), 2):
                    keyboard.add(*buttons[i:i + 2])

            keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data="back_to_group"))
            bot.send_message(call.message.chat.id, text=f"Выбрано: {group} → {subgroup1}. Теперь выбери вид продукции:",
                             reply_markup=keyboard)
        if 'products' in temp_data[user_id] and temp_data[user_id]['products']:
            del temp_data[user_id]['products'][-1]
    elif last_action == 'finish_entry':
        department = user_data[user_id]['department']
        keyboard = types.InlineKeyboardMarkup()
        groups = list(nomenclature[department].keys())
        buttons = [types.InlineKeyboardButton(text=add_newline(group), callback_data=f"group_{group}") for group in
                   groups]

        # Добавляем кнопки в зависимости от контекста
        for i in range(0, len(buttons), 3):
            keyboard.add(*buttons[i:i + 3])

        if len(buttons) % 3 != 0:
            keyboard.add(*buttons[-(len(buttons) % 3):])

        keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data="back_to_department"))
        bot.send_message(call.message.chat.id, text=f"Выбери следующую группу продукции:", reply_markup=keyboard)
    elif last_action == 'additional_info':
        bot.send_message(call.message.chat.id, 'Введи дополнительную информацию, если есть, или введи "нет":',
                         reply_markup=create_back_button())
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, additional_info)
    elif last_action == 'review_report':
        bot.send_message(call.message.chat.id, 'Введи дополнительную информацию, если есть, или введи "нет":',
                         reply_markup=create_back_button())
        bot.register_next_step_handler_by_chat_id(call.message.chat.id, additional_info)


# Запуск бота
bot.polling()
