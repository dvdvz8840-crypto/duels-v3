import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import time
import random

TOKEN = "8533497017:AAEr8AsVdxxR0hf6tYftdB2fzvDtgfoLY0U"
ADMIN_ID = 6151671553
bot = telebot.TeleBot(TOKEN)

# ---------------- Фото ----------------
IMG_BALANCE = "https://i.ibb.co/b5ndP1nq"
IMG_BONUS = "https://i.ibb.co/wxsrLM1"
IMG_DUEL_WAIT = "https://i.ibb.co/rRcZfj8g"
IMG_DUEL_START = "https://i.ibb.co/PvXNfTTm"
IMG_DUEL_END = "https://i.ibb.co/QvYxJmQs"
IMG_RANK_UP = "https://i.ibb.co/Kz0g8vdv"
IMG_RANK_DOWN = "https://i.ibb.co/KjWkJbqR"
IMG_DUEL_CANCEL = "https://i.ibb.co/YBphVqG/duel-cancel.jpg"

# ---------------- Игроки ----------------
players = {}  # {user_id: {"username": str, "balance": int, "rating": int, "rank": str}}
active_duels = {}  # {chat_id: {"player1": id, "player2": id, "bet": int, "turn": id, "shield": {id: bool}, "msg_id": id}}
bonus_cooldown = {}  # {user_id: timestamp}

# ---------------- Ранги ----------------
RANKS = [
    ("⚔️ Новичок", 0),
    ("🛡️ Солдат", 100),
    ("🗡️ Рыцарь", 250),
    ("🏹 Ас", 400),
    ("💀 Легенда", 600),
    ("🔥 Легендарный", 800),
    ("👑 Мастер", 1000),
    ("🌟 Легенда+", 1200),
    ("💎 Элита", 1500),
    ("👑 Великий", 2000),
    ("🦁 Император", 2500)
]

BONUS_AMOUNT = 500
BONUS_COOLDOWN = 3600  # 1 час

# ---------------- Функции ----------------
def get_rank(rating):
    rank = RANKS[0][0]
    for r, val in RANKS:
        if rating >= val:
            rank = r
        else:
            break
    return rank

def ensure_player(user):
    user_id = user.id
    if user_id not in players:
        username = user.username or user.first_name
        players[user_id] = {"username": username, "balance": 1000, "rating": 0, "rank": get_rank(0)}
    return players[user_id]

def update_rank(user_id, chat_id):
    player = players[user_id]
    old_rank = player["rank"]
    new_rank = get_rank(player["rating"])
    player["rank"] = new_rank
    if old_rank != new_rank:
        if player["rating"] > 0:
            bot.send_photo(chat_id, IMG_RANK_UP,
                           caption=f"🔥 Поздравляем!\n🎖 <a href='https://t.me/{player['username']}'>{player['username']}</a> Новый ранг: {new_rank}",
                           parse_mode="HTML")
        else:
            bot.send_photo(chat_id, IMG_RANK_DOWN,
                           caption=f"⚠️ Ранг понижен!\n🎖 <a href='https://t.me/{player['username']}'>{player['username']}</a> Новый ранг: {new_rank}",
                           parse_mode="HTML")

# ---------------- Дуэль ----------------
def start_duel(chat_id, player1_id, player2_id, bet):
    p1 = players[player1_id]
    p2 = players[player2_id] if player2_id else None
    if p2 and (p1["balance"] < bet or p2["balance"] < bet):
        bot.send_message(chat_id, "❌ У одного из игроков недостаточно монет")
        return
    # Списание ставки у первого игрока
    p1["balance"] -= bet
    duel = {"player1": player1_id, "player2": player2_id, "bet": bet, "turn": player1_id, "shield": {player1_id: False, player2_id: False}}
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("⚔️ Сразиться", callback_data="accept_duel"),
        InlineKeyboardButton("✖️ Отмена", callback_data="cancel_invite")
    )
    msg = bot.send_photo(chat_id, IMG_DUEL_WAIT,
                         caption=f"⚔️ <a href='https://t.me/{p1['username']}'>{p1['username']}</a> вызывает любого на дуэль!\n💰 Ставка: {bet}\n💬 Чтобы принять нажмите кнопку ниже",
                         parse_mode="HTML", reply_markup=markup)
    duel["msg_id"] = msg.message_id
    active_duels[chat_id] = duel

def next_turn(chat_id):
    duel = active_duels[chat_id]
    duel["turn"] = duel["player2"] if duel["turn"] == duel["player1"] else duel["player1"]
    duel["shield"][duel["turn"]] = False
    p = players[duel["turn"]]
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("🔫 Выстрел", callback_data="shoot"),
        InlineKeyboardButton("🛡️ Защититься", callback_data="shield"),
        InlineKeyboardButton("✖️ Отмена", callback_data="cancel")
    )
    bot.edit_message_media(chat_id=chat_id,
                           message_id=duel["msg_id"],
                           media=telebot.types.InputMediaPhoto(media=IMG_DUEL_START,
                                                               caption=f"⚔️ Ход <a href='https://t.me/{p['username']}'>{p['username']}</a>\n💰 Ставка: {duel['bet']}"
                                                               , parse_mode="HTML"),
                           reply_markup=markup)

def end_duel(chat_id, winner_id, loser_id, bet, rating_gain=30):
    winner = players[winner_id]
    loser = players[loser_id]
    winner["balance"] += bet*2
    winner["rating"] += rating_gain
    loser["rating"] -= 15
    update_rank(winner_id, chat_id)
    update_rank(loser_id, chat_id)
    bot.send_photo(chat_id, IMG_DUEL_END,
                   caption=(f"⚔️ Дуэль завершилась.\n\n"
                            f"🔫 <a href='https://t.me/{winner['username']}'>{winner['username']}</a> убил "
                            f"<a href='https://t.me/{loser['username']}'>{loser['username']}</a>\n\n"
                            f"👑 Победитель: <a href='https://t.me/{winner['username']}'>{winner['username']}</a>\n"
                            f"💰 Выигрыш: {bet*2}\n"
                            f"🎖️ Рейтинг: +{rating_gain}"),
                   parse_mode="HTML")
    if chat_id in active_duels:
        del active_duels[chat_id]

# ---------------- Коллбэк дуэли ----------------
@bot.callback_query_handler(func=lambda call: True)
def callback_duel(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    if chat_id not in active_duels:
        bot.answer_callback_query(call.id, "❌ Нет активной дуэли")
        return
    duel = active_duels[chat_id]

    # Отмена до начала
    if call.data == "cancel_invite":
        if user_id != duel["player1"]:
            bot.answer_callback_query(call.id, "❌ Только инициатор может отменить вызов")
            return
        players[user_id]["balance"] += int(duel["bet"]*0.4)
        players[user_id]["rating"] -= 20
        update_rank(user_id, chat_id)
        bot.send_photo(chat_id, IMG_DUEL_CANCEL,
                       caption=f"⚔️ Дуэль отменена!\n<a href='https://t.me/{players[user_id]['username']}'>{players[user_id]['username']}</a> отменил дуэль",
                       parse_mode="HTML")
        del active_duels[chat_id]
        return

    # Прием дуэли
    if call.data == "accept_duel":
        if duel["player2"]:
            bot.answer_callback_query(call.id, "❌ Дуэль уже принята")
            return
        duel["player2"] = user_id
        players[user_id]["balance"] -= duel["bet"]
        p1 = players[duel["player1"]]
        p2 = players[user_id]
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("🔫 Выстрел", callback_data="shoot"),
            InlineKeyboardButton("🛡️ Защититься", callback_data="shield"),
            InlineKeyboardButton("✖️ Отмена", callback_data="cancel")
        )
        msg = bot.send_photo(chat_id, IMG_DUEL_START,
                             caption=(f"⚔️ <a href='https://t.me/{p2['username']}'>{p2['username']}</a> готов сражаться с "
                                      f"<a href='https://t.me/{p1['username']}'>{p1['username']}</a>\n"
                                      f"💰 Ставка: {duel['bet']}\n⏪ Первый ход предоставляется <a href='https://t.me/{p1['username']}'>{p1['username']}</a>"),
                             parse_mode="HTML",
                             reply_markup=markup)
        duel["msg_id"] = msg.message_id
        duel["turn"] = duel["player1"]
        return

    if call.data == "shield":
        duel["shield"][user_id] = True
        bot.answer_callback_query(call.id, "🛡️ Вы активировали защиту")
        next_turn(chat_id)
    elif call.data == "shoot":
        opponent_id = duel["player2"] if user_id == duel["player1"] else duel["player1"]
        chance = 35 if duel["shield"].get(opponent_id, False) else 50
        hit = random.randint(1,100) <= chance
        if hit:
            end_duel(chat_id, user_id, opponent_id, duel["bet"])
        else:
            bot.send_message(chat_id, f"💥 <a href='https://t.me/{players[opponent_id]['username']}'>{players[opponent_id]['username']}</a> увернулся!", parse_mode="HTML")
            next_turn(chat_id)
    elif call.data == "cancel":
        # Отмена во время дуэли
        opponent_id = duel["player2"] if user_id == duel["player1"] else duel["player1"]
        canceling_player = players[user_id]
        opponent_player = players[opponent_id]

        canceling_return = int(duel["bet"]*0.4)
        canceling_player["balance"] += canceling_return
        canceling_player["rating"] -= 20
        update_rank(user_id, chat_id)

        opponent_player["balance"] += duel["bet"]

        bot.send_photo(chat_id, IMG_DUEL_CANCEL,
                       caption=(f"⚔️ Дуэль отменена!\n"
                                f"<a href='https://t.me/{canceling_player['username']}'>{canceling_player['username']}</a> отменил дуэль\n\n"
                                f"💰 {canceling_player['username']} получил возврат 40% ставки: {canceling_return}\n"
                                f"🎖️ Рейтинг {canceling_player['username']}: {canceling_player['rating']}\n\n"
                                f"<a href='https://t.me/{opponent_player['username']}'>{opponent_player['username']}</a> получил возврат полной ставки: {duel['bet']}"),
                       parse_mode="HTML")
        del active_duels[chat_id]

# ---------------- Команды ----------------
@bot.message_handler(commands=['dbal'])
def check_balance(message):
    user = ensure_player(message.from_user)
    bot.send_photo(message.chat.id, IMG_BALANCE,
                   caption=(f"⚔️ <a href='https://t.me/{user['username']}'>{user['username']}</a> — Ваша статистика!\n\n"
                            f"💰 Баланс: {user['balance']}\n"
                            f"🎖️ Ранг: {user['rank']}\n"
                            f"⚔️ Рейтинг: {user['rating']}"),
                   parse_mode="HTML")

@bot.message_handler(commands=['dg'])
def transfer_coins(message):
    user = ensure_player(message.from_user)
    try:
        parts = message.text.split()
        target_username = parts[1].replace("@","")
        amount = int(parts[2])
        if user["balance"] < amount:
            bot.reply_to(message,"❌ Недостаточно монет")
            return
        target = None
        for u in players.values():
            if u["username"] == target_username:
                target = u
                break
        if not target:
            bot.reply_to(message,"❌ Игрок не найден")
            return
        user["balance"] -= amount
        target["balance"] += amount
        bot.send_message(message.chat.id,
                         f"⚔️ <a href='https://t.me/{user['username']}'>{user['username']}</a> перевел "
                         f"<a href='https://t.me/{target['username']}'>{target['username']}</a> {amount} монет.\n"
                         f"💰 Баланс {target['username']}: {target['balance']}",
                         parse_mode="HTML")
    except:
        bot.reply_to(message,"Использование: /dg @username сумма")

@bot.message_handler(commands=['двыдать'])
def admin_give(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        target_username = parts[1].replace("@","")
        amount = int(parts[2])
        target = None
        for u in players.values():
            if u["username"] == target_username:
                target = u
                break
        if not target:
            target = {"username": target_username,"balance":0,"rating":0,"rank":get_rank(0)}
            players[hash(target_username)] = target
        target["balance"] += amount
        bot.send_message(message.chat.id,
                         f"💰 К балансу <a href='https://t.me/{target['username']}'>{target['username']}</a> добавлено {amount} монет.",
                         parse_mode="HTML")
    except:
        bot.reply_to(message,"Использование: /двыдать @username сумма")

@bot.message_handler(commands=['dbonus'])
def daily_bonus(message):
    user = ensure_player(message.from_user)
    user_id = message.from_user.id
    now = time.time()
    if user_id in bonus_cooldown and now - bonus_cooldown[user_id] < BONUS_COOLDOWN:
        remaining = int(BONUS_COOLDOWN - (now - bonus_cooldown[user_id]))
        mins, secs = divmod(remaining,60)
        bot.reply_to(message,f"🕒 Бонус снова будет доступен через {mins} минут и {secs} секунд")
        return
    rating_gain = random.randint(5,40)
    user["balance"] += BONUS_AMOUNT
    user["rating"] += rating_gain
    update_rank(user_id, message.chat.id)
    bonus_cooldown[user_id] = now
    bot.send_photo(message.chat.id, IMG_BONUS,
                   caption=(f"⚔️ <a href='https://t.me/{user['username']}'>{user['username']}</a> Вы получили бонус!\n\n"
                            f"💰 +{BONUS_AMOUNT}\n"
                            f"🎖️ +{rating_gain}"),
                   parse_mode="HTML")

@bot.message_handler(commands=['drang'])
def cmd_drang(message):
    top = sorted(players.values(), key=lambda x: x["rating"], reverse=True)[:10]
    text = ""
    for i, p in enumerate(top, start=1):
        text += f"🔹 {i}. <a href='https://t.me/{p['username']}'>{p['username']}</a> - {p['rank']} | {p['rating']}\n"
    bot.send_photo(
        message.chat.id,
        photo=IMG_LEADERBOARD,
        caption="⚔️ Список лидеров:\n\n" + text,
        parse_mode="HTML"
     )

# ---------------- Запуск бота ----------------
bot.infinity_polling()