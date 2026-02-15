import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import time
import random
import threading

TOKEN = "8533497017:AAEr8AsVdxxR0hf6tYftdB2fzvDtgfoLY0U"
ADMIN_ID = 6151671553
bot = telebot.TeleBot(TOKEN)

# ---------------- Игроки и дуэли ----------------
players = {}  # {user_id: {"username": str, "balance": int, "rating": int, "rank": str}}
active_duels = {}  # {chat_id: {"player1": id, "player2": id, "bet": int, "turn": id, "shield": {id: bool}, "msg_id": id}}
bonus_cooldown = {}  # {user_id: timestamp}

# Ранги с порогами рейтинга
RANKS = [
    ("⚔️ Новичок", 0),
    ("🛡️ Солдат", 100),
    ("🗡️ Рыцарь", 250),
    ("🏹 Ас", 400),
    ("💀 Легенда", 600),
    ("🔥 Легендарный", 800),
    ("👑 Мастер", 1000)
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

def update_rank(user_id):
    player = players[user_id]
    old_rank = player["rank"]
    new_rank = get_rank(player["rating"])
    player["rank"] = new_rank
    if old_rank != new_rank:
        if player["rating"] > 0:
            bot.send_message(
                user_id,
                f"🔥 Поздравляем!\n🎖 <a href='https://t.me/{player['username']}'>{player['username']}</a> Новый ранг: {new_rank}",
                parse_mode="HTML"
            )
        else:
            bot.send_message(
                user_id,
                f"⚠️ Ранг понижен!\n🎖 <a href='https://t.me/{player['username']}'>{player['username']}</a> Новый ранг: {new_rank}",
                parse_mode="HTML"
            )

# ---------------- Дуэль ----------------
def start_duel(chat_id, player1_id, player2_id, bet):
    p1 = players[player1_id]
    p2 = players[player2_id]
    if p1["balance"] < bet or p2["balance"] < bet:
        bot.send_message(chat_id, "❌ У одного из игроков недостаточно монет для ставки")
        return
    # Списание ставки
    p1["balance"] -= bet
    p2["balance"] -= bet
    # Создаем дуэль
    duel = {"player1": player1_id, "player2": player2_id, "bet": bet, "turn": player1_id, "shield": {player1_id: False, player2_id: False}}
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("🔫 Выстрел", callback_data="shoot"),
        InlineKeyboardButton("🛡️ Защититься", callback_data="shield"),
        InlineKeyboardButton("✖️ Отмена", callback_data="cancel")
    )
    msg = bot.send_message(chat_id,
                           f"⚔️ Дуэль началась!\n"
                           f"Ход <a href='https://t.me/{players[player1_id]['username']}'>{players[player1_id]['username']}</a>\n"
                           f"💰 Ставка: {bet}",
                           parse_mode="HTML",
                           reply_markup=markup)
    duel["msg_id"] = msg.message_id
    active_duels[chat_id] = duel

def end_duel(chat_id, winner_id, loser_id, bet, cancelled=False):
    winner = players[winner_id]
    loser = players[loser_id]
    if cancelled:
        # Возврат 85% ставки игроку, который отменил
        winner["balance"] += int(bet*0.85)
        loser["rating"] -= 35
        update_rank(loser_id)
        bot.send_message(chat_id,
                         f"⚔️ Дуэль отменена!\n"
                         f"<a href='https://t.me/{winner['username']}'>{winner['username']}</a> получил 85% ставки обратно\n"
                         f"⚔️ Рейтинг {loser['username']}: {loser['rating']}",
                         parse_mode="HTML")
    else:
        winner["balance"] += bet*2
        winner["rating"] += 100
        loser["rating"] -= 15
        update_rank(winner_id)
        update_rank(loser_id)
        bot.send_message(chat_id,
                         f"⚔️ Дуэль завершилась!\n"
                         f"🏆 Победитель: <a href='https://t.me/{winner['username']}'>{winner['username']}</a>\n"
                         f"💀 Проигравший: <a href='https://t.me/{loser['username']}'>{loser['username']}</a>\n"
                         f"💰 Выигрыш: {bet*2}\n"
                         f"⚔️ Рейтинг: {winner['rating']} | {loser['rating']}",
                         parse_mode="HTML")
    if chat_id in active_duels:
        del active_duels[chat_id]

def next_turn(chat_id):
    duel = active_duels[chat_id]
    duel["turn"] = duel["player2"] if duel["turn"] == duel["player1"] else duel["player1"]
    # Сбрасываем щит
    duel["shield"][duel["turn"]] = False
    # Обновляем сообщение
    p = players[duel["turn"]]
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("🔫 Выстрел", callback_data="shoot"),
        InlineKeyboardButton("🛡️ Защититься", callback_data="shield"),
        InlineKeyboardButton("✖️ Отмена", callback_data="cancel")
    )
    bot.edit_message_text(
        f"⚔️ Ход <a href='https://t.me/{p['username']}'>{p['username']}</a>\n"
        f"💰 Ставка: {duel['bet']}",
        chat_id=chat_id,
        message_id=duel["msg_id"],
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_duel(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    if chat_id not in active_duels:
        bot.answer_callback_query(call.id, "❌ Нет активной дуэли")
        return
    duel = active_duels[chat_id]
    if user_id != duel["turn"]:
        bot.answer_callback_query(call.id, "❌ Сейчас не ваш ход")
        return
    if call.data == "shield":
        duel["shield"][user_id] = True
        bot.answer_callback_query(call.id, "🛡️ Вы активировали защиту")
        next_turn(chat_id)
    elif call.data == "shoot":
        opponent_id = duel["player2"] if user_id == duel["player1"] else duel["player1"]
        chance = 35 if duel["shield"].get(opponent_id, False) else 50
        hit = random.randint(1, 100) <= chance
        if hit:
            end_duel(chat_id, user_id, opponent_id, duel["bet"])
        else:
            bot.send_message(chat_id, f"💥 <a href='https://t.me/{players[opponent_id]['username']}'>{players[opponent_id]['username']}</a> увернулся!", parse_mode="HTML")
            next_turn(chat_id)
    elif call.data == "cancel":
        opponent_id = duel["player2"] if user_id == duel["player1"] else duel["player1"]
        end_duel(chat_id, user_id, opponent_id, duel["bet"], cancelled=True)

# ---------------- Команды ----------------
@bot.message_handler(commands=['dd'])
def duel_command(message):
    try:
        parts = message.text.split()
        bet = int(parts[1])
        user = ensure_player(message.from_user)
        start_duel(message.chat.id, message.from_user.id, None, bet)
    except:
        bot.reply_to(message, "Использование: /dd сумма_ставки")

# ---------------- Остальной функционал ----------------
@bot.message_handler(commands=['dbal'])
def check_balance(message):
    # Убедиться, что игрок есть в players
    user = ensure_player(message.from_user)
    
    username = user["username"]
    balance = user["balance"]
    rating = user["rating"]
    rank = user["rank"]
    
    # Ссылка на изображение "Ваша статистика"
    balance_image_url = "https://i.ibb.co/b5ndP1nq"
    
    # Отправляем фото с текстом под ним
    bot.send_photo(
        message.chat.id,
        balance_image_url,
        caption=(
            f"⚔️ <a href='https://t.me/{username}'>{username}</a> — Ваша статистика!\n\n"
            f"💰 Баланс: {balance}\n"
            f"🎖️ Ранг: {rank}\n"
            f"⚔️ Рейтинг: {rating}"
        ),
        parse_mode="HTML"
    )

@bot.message_handler(commands=['dg'])
def transfer_coins(message):
    user = ensure_player(message.from_user)
    try:
        parts = message.text.split()
        target_username = parts[1].replace("@", "")
        amount = int(parts[2])
        if user["balance"] < amount:
            bot.reply_to(message, "❌ Недостаточно монет для перевода")
            return
        target = None
        for u in players.values():
            if u["username"] == target_username:
                target = u
                break
        if not target:
            bot.reply_to(message, "❌ Игрок не найден")
            return
        user["balance"] -= amount
        target["balance"] += amount
        bot.send_message(
            message.chat.id,
            f"⚔️ <a href='https://t.me/{user['username']}'>{user['username']}</a> перевел "
            f"<a href='https://t.me/{target['username']}'>{target['username']}</a> {amount} монет.\n"
            f"💰 Баланс {target['username']}: {target['balance']}",
            parse_mode="HTML"
        )
    except Exception:
        bot.reply_to(message, "Использование: /dg @username сумма")

@bot.message_handler(commands=['двыдать'])
def admin_give(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        target_username = parts[1].replace("@", "")
        amount = int(parts[2])
        target = None
        for u in players.values():
            if u["username"] == target_username:
                target = u
                break
        if not target:
            target = {"username": target_username, "balance": 0, "rating": 0, "rank": get_rank(0)}
            players[hash(target_username)] = target
        target["balance"] += amount
        bot.send_message(
            message.chat.id,
            f"💰 К балансу <a href='https://t.me/{target['username']}'>{target['username']}</a> добавлено {amount} монет.",
            parse_mode="HTML"
        )
    except Exception:
        bot.reply_to(message, "Использование: /двыдать @username сумма")

@bot.message_handler(commands=['дбонус'])
def daily_bonus(message):
    user = ensure_player(message.from_user)
    user_id = message.from_user.id
    now = time.time()
    if user_id in bonus_cooldown and now - bonus_cooldown[user_id] < BONUS_COOLDOWN:
        remaining = int(BONUS_COOLDOWN - (now - bonus_cooldown[user_id]))
        mins, secs = divmod(remaining, 60)
        bot.reply_to(message, f"🕒 Бонус снова будет доступен через {mins} минут и {secs} секунд")
        return
    rating_gain = random.randint(5, 40)
    user["balance"] += BONUS_AMOUNT
    user["rating"] += rating_gain
    update_rank(user_id)
    bonus_cooldown[user_id] = now
    bot.send_message(
        message.chat.id,
        f"⚔️ <a href='https://t.me/{user['username']}'>{user['username']}</a> Вы получили бонус!\n\n"
        f"💰 +{BONUS_AMOUNT}\n"
        f"🎖️ +{rating_gain}",
        parse_mode="HTML"
    )

@bot.message_handler(commands=['drang'])
def leaderboard(message):
    top = sorted(players.values(), key=lambda x: x["rating"], reverse=True)[:10]
    text = "⚔️ Список лидеров:\n\n"
    for i, p in enumerate(top, start=1):
        text += f"🔹 {i}. <a href='https://t.me/{p['username']}'>{p['username']}</a> - {p['rank']} | {p['rating']}\n"
    bot.send_message(message.chat.id, text, parse_mode="HTML")

# ---------------- Запуск бота ----------------
bot.infinity_polling()