import telebot
import sqlite3
from TOKEN import TOKEN
from telebot import types

conn = sqlite3.connect('movies.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS movies
             (id INTEGER PRIMARY KEY, title TEXT, description TEXT, rating REAL, url TEXT, image_url TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS admins
             (id INTEGER PRIMARY KEY)''')
c.execute('''CREATE TABLE IF NOT EXISTS sponsors
             (id INTEGER PRIMARY KEY, name TEXT, url TEXT)''')
conn.commit()
conn.close()

bot = telebot.TeleBot(TOKEN)

ADMIN_IDS = [121345678, 987654321]


user_states = {}

def is_authorized(user_id):
    if user_id in ADMIN_IDS:
        return True
    with sqlite3.connect('movies.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM admins WHERE id = ?", (user_id,))
        return cursor.fetchone() is not None

def is_admin(user_id):
    with sqlite3.connect('movies.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM admins WHERE id = ?", (user_id,))
        return cursor.fetchone() is not None

def send_movie_list_text(chat_id, offset, message_id=None):
    with sqlite3.connect('movies.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title FROM movies ORDER BY id LIMIT 10 OFFSET ?", (offset,))
        movies = cursor.fetchall()

        if movies:
            message = "Все фильмы, сериалы и мультфильмы которые вы можете у нас посмотреть:\n\n"
            for movie in movies:
                message += f"{movie[0]}. {movie[1]}\n"

            keyboard = types.InlineKeyboardMarkup()
            cursor.execute("SELECT COUNT(*) FROM movies")
            total_movies_count = cursor.fetchone()[0]
            if offset + 10 < total_movies_count:
                next_button = types.InlineKeyboardButton(text="Дальше", callback_data=f'next_movies_{offset + 10}')
                keyboard.add(next_button)
            if offset > 0:
                back_button = types.InlineKeyboardButton(text="Назад", callback_data=f'back_movies_{offset - 10}')
                keyboard.add(back_button)

            if message_id:
                bot.edit_message_text(message, chat_id, message_id, reply_markup=keyboard)
            else:
                bot.send_message(chat_id, message, reply_markup=keyboard)
        else:
            bot.send_message(chat_id, "Фильмы не найдены в базе данных.")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.chat.id), dict) and user_states[message.chat.id].get('state') == 'adding_movie_title')
def handle_movie_title(message):
    user_states[message.chat.id] = {
        'state': 'adding_movie_description',
        'title': message.text,
        'description': None,
        'rating': None,
        'url': None,
        'image_url': None
    }
    bot.send_message(message.chat.id, "Введите описание фильма:")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.chat.id), dict) and user_states[message.chat.id].get('state') == 'adding_movie_description')
def handle_movie_description(message):
    user_states[message.chat.id]['description'] = message.text
    user_states[message.chat.id]['state'] = 'adding_movie_rating'
    bot.send_message(message.chat.id, "Введите рейтинг фильма (например, 8.5):")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.chat.id), dict) and user_states[message.chat.id].get('state') == 'adding_movie_rating')
def handle_movie_rating(message):
    try:
        user_states[message.chat.id]['rating'] = float(message.text)
        user_states[message.chat.id]['state'] = 'adding_movie_url'
        bot.send_message(message.chat.id, "Введите URL фильма:")
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите правильный рейтинг (например, 8.5):")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.chat.id), dict) and user_states[message.chat.id].get('state') == 'adding_movie_url')
def handle_movie_url(message):
    user_states[message.chat.id]['url'] = message.text
    user_states[message.chat.id]['state'] = 'adding_movie_image_url'
    bot.send_message(message.chat.id, "Введите URL изображения фильма:")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.chat.id), dict) and user_states[message.chat.id].get('state') == 'adding_movie_image_url')
def handle_movie_image_url(message):
    movie_data = user_states[message.chat.id]
    title = movie_data['title']
    description = movie_data['description']
    rating = movie_data['rating']
    url = movie_data['url']
    image_url = message.text

    try:
        with sqlite3.connect('movies.db') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO movies (title, description, rating, url, image_url) VALUES (?, ?, ?, ?, ?)",
                           (title, description, rating, url, image_url))
            conn.commit()
        bot.send_message(message.chat.id, "Фильм успешно добавлен!")
    except sqlite3.Error as e:
        bot.send_message(message.chat.id, f"Ошибка при добавлении фильма: {e}")
    finally:
        user_states.pop(message.chat.id, None)

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'adding_admin')
def handle_adding_admin(message):
    try:
        new_admin_id = int(message.text.strip())
        with sqlite3.connect('movies.db') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO admins (id) VALUES (?)", (new_admin_id,))
            conn.commit()
        bot.send_message(message.chat.id, "Администратор успешно добавлен.")
    except ValueError:
        bot.send_message(message.chat.id, "Введите действительный ID администратора.")
    except sqlite3.Error as e:
        bot.send_message(message.chat.id, f"Ошибка при добавлении администратора: {e}")
    finally:
        del user_states[message.chat.id]

@bot.message_handler(commands=['start'])
def start_command(message):
    with sqlite3.connect('movies.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name, url FROM sponsors")
        sponsors = cursor.fetchall()

    if sponsors:
        message_text = "Чтобы начать просмотр, подпишитесь на наших спонсоров:"
        keyboard = types.InlineKeyboardMarkup()
        for sponsor in sponsors[:4]:
            keyboard.add(types.InlineKeyboardButton(text=sponsor[0], url=sponsor[1]))
        if len(sponsors) > 4:
            keyboard.add(types.InlineKeyboardButton(text="Следующие", callback_data='next_sponsors_4'))
        keyboard.add(types.InlineKeyboardButton(text="Проверить", callback_data='check_subscriptions'))
        bot.send_message(message.chat.id, message_text, reply_markup=keyboard)
    else:
        bot.send_message(message.chat.id, 'Нет спонсоров для отображения.')

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id in ADMIN_IDS:
        keyboard = types.InlineKeyboardMarkup()
        button_add_admin = types.InlineKeyboardButton(text="Добавить администратора", callback_data='add_admin')
        button_add_sponsor = types.InlineKeyboardButton(text="Добавить спонсоров", callback_data='add_sponsor')
        button_add_movie = types.InlineKeyboardButton(text="Добавить фильм", callback_data='add_movie')
        keyboard.add(button_add_admin, button_add_sponsor, button_add_movie)
        bot.send_message(message.chat.id, 'Выберите ваше действие:', reply_markup=keyboard)
    else:
        bot.send_message(message.chat.id, 'У вас нет прав для использования этой команды.')

@bot.message_handler(commands=['add_movie'])
def add_movie_command(message):
    if is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "Пожалуйста, отправьте название фильма:")
        user_states[message.chat.id] = {'state': 'adding_movie_title'}
    else:
        bot.send_message(message.chat.id, 'У вас нет прав для использования этой команды.')

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == 'check_subscriptions':
        check_subscriptions(call.message.chat.id)
    if call.data == 'add_movie':
        if is_admin(call.from_user.id):
            bot.send_message(call.message.chat.id, "Пожалуйста, отправьте название фильма:")
            user_states[call.message.chat.id] = {'state': 'adding_movie_title'}
        else:
            bot.send_message(call.message.chat.id, 'У вас нет прав для использования этой команды.')
    elif call.data == 'add_admin':
        bot.send_message(call.message.chat.id, "Пожалуйста, отправьте ID администратора:")
        user_states[call.message.chat.id] = 'adding_admin'
    elif call.data.startswith('next_sponsors_'):
        offset = int(call.data.split('_')[2])
        with sqlite3.connect('movies.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, url FROM sponsors LIMIT 4 OFFSET ?", (offset,))
            sponsors = cursor.fetchall()
        if sponsors:
            keyboard = types.InlineKeyboardMarkup()
            for sponsor in sponsors:
                keyboard.add(types.InlineKeyboardButton(text=sponsor[0], url=sponsor[1]))
            if len(sponsors) == 4:
                keyboard.add(types.InlineKeyboardButton(text="Следующие", callback_data=f'next_sponsors_{offset + 4}'))
            if offset > 0:
                keyboard.add(types.InlineKeyboardButton(text="Назад", callback_data=f'prev_sponsors_{offset - 4}'))
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    elif call.data == 'add_sponsor':
        if is_authorized(call.from_user.id):
            bot.send_message(call.message.chat.id, "Введите имя спонсора:")
            user_states[call.message.chat.id] = {
                'state': 'adding_sponsor',
                'name': None,
                'url': None
            }
        else:
            bot.send_message(call.message.chat.id, 'У вас нет прав для использования этой команды.')
    elif call.data == 'check_subscriptions':
        bot.send_message(call.message.chat.id, 'Проверка подписок...')

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.chat.id), dict) and user_states[message.chat.id].get('state') == 'adding_sponsor')
def handle_sponsor_name(message):
    user_states[message.chat.id]['name'] = message.text
    user_states[message.chat.id]['state'] = 'adding_sponsor_url'
    bot.send_message(message.chat.id, "Введите URL спонсора:")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.chat.id), dict) and user_states[message.chat.id].get('state') == 'adding_sponsor_url')
def handle_sponsor_url(message):
    sponsor_data = user_states[message.chat.id]
    sponsor_name = sponsor_data['name']
    sponsor_url = message.text

    try:
        with sqlite3.connect('movies.db') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO sponsors (name, url) VALUES (?, ?)", (sponsor_name, sponsor_url))
            conn.commit()
        bot.send_message(message.chat.id, "Спонсор успешно добавлен!")
    except sqlite3.Error as e:
        bot.send_message(message.chat.id, f"Ошибка при добавлении спонсора: {e}")
    finally:
        user_states.pop(message.chat.id, None)

@bot.message_handler(commands=['show_movies'])
def show_movies_command(message):
    send_movie_list_text(message.chat.id, 0)

@bot.callback_query_handler(func=lambda call: call.data.startswith('next_movies_') or call.data.startswith('back_movies_'))
def callback_movies(call):
    offset = int(call.data.split('_')[2])
    send_movie_list_text(call.message.chat.id, offset, call.message.message_id)

def check_subscriptions(message):
    user_id = message.from_user.id
    with sqlite3.connect('movies.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM sponsors")
        sponsors = cursor.fetchall()

    not_subscribed = []

    for sponsor in sponsors:
        sponsor_url = sponsor[0]
        channel_username = sponsor_url.split('/')[-1]
        try:
            member = bot.get_chat_member(channel_username, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                not_subscribed.append(channel_username)
        except:
            not_subscribed.append(channel_username)

    if not_subscribed:
        bot.send_message(user_id, f"Вы не подписаны на следующие каналы: {', '.join(not_subscribed)}")
    else:
        bot.send_message(user_id, "Вы подписаны на все необходимые каналы.")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'adding_movie_title')
def handle_movie_title(message):
    user_states[message.chat.id] = 'adding_movie_description'
    bot.send_message(message.chat.id, "Введите описание фильма:")
    user_states[message.chat.id] = {
        'title': message.text,
        'description': None,
        'rating': None,
        'url': None,
        'image_url': None
    }

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'adding_movie_description')
def handle_movie_description(message):
    user_states[message.chat.id]['description'] = message.text
    bot.send_message(message.chat.id, "Введите рейтинг фильма (например, 8.5):")
    user_states[message.chat.id]['rating'] = None

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'adding_movie_rating')
def handle_movie_rating(message):
    try:
        user_states[message.chat.id]['rating'] = float(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите правильный рейтинг (например, 8.5):")
        return

    bot.send_message(message.chat.id, "Введите URL фильма:")
    user_states[message.chat.id]['url'] = None

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'adding_movie_image_url')
def handle_movie_image_url(message):
    movie_data = user_states[message.chat.id]
    title = movie_data['title']
    description = movie_data['description']
    rating = movie_data['rating']
    url = movie_data['url']
    image_url = message.text

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'adding_movie_image_url')
def handle_movie_image_url(message):
    movie_data = user_states[message.chat.id]
    title = movie_data['title']
    description = movie_data['description']
    rating = movie_data['rating']
    url = movie_data['url']
    image_url = message.text

    with sqlite3.connect('movies.db') as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO movies (title, description, rating, url, image_url) VALUES (?, ?, ?, ?, ?)",
                       (title, description, rating, url, image_url))
        conn.commit()

    bot.send_message(message.chat.id, "Фильм успешно добавлен!")
    user_states.pop(message.chat.id, None)

def send_movie_info(chat_id, movie):
    title = movie[1]
    description = movie[2]
    rating = movie[3]
    url = movie[4]
    image_url = movie[5]

    message = f"Название: {title}\nОписание: {description}\nРейтинг: {rating}"
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="Посмотреть", url=url))
    
    bot.send_photo(chat_id, photo=image_url, caption=message, reply_markup=keyboard)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    state = user_states.get(chat_id)

    if isinstance(state, str):
        if state == 'adding_movie_title':
            movie_title = message.text.strip()
            print(f"Received movie title: {movie_title}")
            user_states[chat_id] = ('adding_movie_description', movie_title)
            bot.send_message(chat_id, "Пожалуйста, отправьте описание фильма:")
        elif state == 'searching_movie':
            search_query = message.text.strip()
            with sqlite3.connect('movies.db') as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM movies WHERE title LIKE ?", (f'%{search_query}%',))
                movie = cursor.fetchone()
            if movie:
                send_movie_info(chat_id, movie)
            else:
                bot.send_message(chat_id, "Фильм не найден. Попробуйте другой запрос.")
        elif state == 'searching_movie_by_id':
            try:
                movie_id = int(message.text.strip())
                with sqlite3.connect('movies.db') as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
                    movie = cursor.fetchone()
                if movie:
                    send_movie_info(chat_id, movie)
                else:
                    bot.send_message(chat_id, "Фильм с таким ID не найден.")
            except ValueError:
                bot.send_message(chat_id, "Введите действительный ID.")
        elif state == 'adding_admin':
            new_admin_id = message.text.strip()
            try:
                new_admin_id = int(new_admin_id)
                with sqlite3.connect('movies.db') as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO admins (id) VALUES (?)", (new_admin_id,))
                    conn.commit()
                bot.send_message(chat_id, "Администратор успешно добавлен.")
            except ValueError:
                bot.send_message(chat_id, "Введите действительный ID администратора.")
            except sqlite3.Error as e:
                bot.send_message(chat_id, f"Ошибка при добавлении администратора: {e}")
            finally:
                del user_states[chat_id]
        elif state == 'adding_sponsor_url':
            sponsor_url = message.text.strip()
            bot.send_message(chat_id, "Введите название спонсора:")
            user_states[chat_id] = ('adding_sponsor_name', sponsor_url)
    
    elif isinstance(state, tuple):
        if state[0] == 'adding_movie_description':
            movie_description = message.text.strip()
            print(f"Received movie description: {movie_description}")
            user_states[chat_id] = ('adding_movie_rating', state[1], movie_description)
            bot.send_message(chat_id, "Пожалуйста, отправьте рейтинг фильма (например, 8.5):")
        elif state[0] == 'adding_movie_rating':
            try:
                movie_rating = float(message.text.strip())
                print(f"Received movie rating: {movie_rating}")
                user_states[chat_id] = ('adding_movie_url', state[1], state[2], movie_rating)
                bot.send_message(chat_id, "Пожалуйста, отправьте ссылку на фильм:")
            except ValueError:
                bot.send_message(chat_id, "Пожалуйста, введите действительный рейтинг.")
        elif state[0] == 'adding_movie_url':
            movie_url = message.text.strip()
            print(f"Received movie URL: {movie_url}")
            user_states[chat_id] = ('adding_movie_image_url', state[1], state[2], state[3], movie_url)
            bot.send_message(chat_id, "Пожалуйста, отправьте URL изображения фильма:")
        elif state[0] == 'adding_movie_image_url':
            movie_image_url = message.text.strip()
            print(f"Adding movie with data: Title: {state[1]}, Description: {state[2]}, Rating: {state[3]}, URL: {state[4]}, Image URL: {movie_image_url}")  # Отладка
            try:
                with sqlite3.connect('movies.db') as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO movies (title, description, rating, url, image_url) VALUES (?, ?, ?, ?, ?)",
                                   (state[1], state[2], state[3], state[4], movie_image_url))
                    conn.commit()
                bot.send_message(chat_id, "Фильм успешно добавлен.")
            except sqlite3.Error as e:
                bot.send_message(chat_id, f"Ошибка при добавлении фильма: {e}")
            finally:
                del user_states[chat_id]
        elif state[0] == 'adding_sponsor_name':
            sponsor_name = message.text.strip()
            try:
                with sqlite3.connect('movies.db') as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO sponsors (name, url) VALUES (?, ?)", (state[1], sponsor_name))
                    conn.commit()
                bot.send_message(chat_id, "Спонсор успешно добавлен.")
            except sqlite3.Error as e:
                bot.send_message(chat_id, f"Ошибка при добавлении спонсора: {e}")
            finally:
                del user_states[chat_id]

if __name__ == '__main__':
    bot.polling()