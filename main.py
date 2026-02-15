import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import time
import random

TOKEN = "8533497017:AAEr8AsVdxxR0hf6tYftdB2fzvDtgfoLY0U"
ADMIN_ID = 6151671553
bot = telebot.TeleBot(TOKEN)

# --- Фото ---
IMG_BALANCE = "https://ibb.co/b5ndP1nq"
IMG_WAIT_DUEL = "https://ibb.co/rRcZfj8g"
IMG_LEADERBOARD = "https://ibb.co/QhXYJsg"
IMG_BONUS = "https://ibb.co/wxsrLM1"
IMG_DUEL_CANCEL = "https://ibb.co/fGkKLW8s"
IMG_RANK_UP = "https://ibb.co/Kz0g8vdv"
IMG_RANK_DOWN = "https://ibb.co/KjWkJbqR"
IMG_DUEL_START = "https://ibb.co/PvXNfTTm"
IMG_DUEL_END = "https://ibb.co/QvYxJmQs"
IMG_TRANSACTION = "https://ibb.co/cSbBpXJL"  # Фото для выдачи и перевода монет

# ---------------- Игроки и дуэли ----------------
players = {}
active_duels = {}
pending_duels = {}
bonus_cooldown = {}

# Ранги с порогами рейтинга
RANKS = [
    ("⚔️ Новичок", 0),
    ("🛡️ Солдат", 100),
    ("🗡️ Рыцарь", 250),
    ("🏹 Ас", 400),
    ("💀 Легенда", 600),
    ("🔥 Легендарный", 800),
    ("👑 Мастер", 1000),
    ("🌟 Легендарный воин", 1200),
    ("💎 Элитный боец", 1400),
    ("⚡ Божественный", 1600),
    ("🔥 Непобедимый", 1800),
    ("👑 Владыка дуэлей", 2000)
]

BONUS_AMOUNT = 500
BONUS_COOLDOWN = 3600

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
    else:
        players[user_id]["username"] = user.username or user.first_name
    return players[user_id]

def update_rank_in_chat(chat_id, user_id):
    player = players[user_id]
    old_rank = player["rank"]
    new_rank = get_rank(player["rating"])
    player["rank"] = new_rank
    if old_rank != new_rank:
        if player["rating"] > 0:
            bot.send_photo(
                chat_id,
                IMG_RANK_UP,
                caption=f"🔥 Поздравляем!\n🎖 <a href='https://t.me/{player['username']}'>{player['username']}</a> Новый ранг: {new_rank}",
                parse_mode="HTML"
            )
        else:
            bot.send_photo(
                chat_id,
                IMG_RANK_DOWN,
                caption=f"⚠️ Ранг понижен!\n🎖 <a href='https://t.me/{player['username']}'>{player['username']}</a> Новый ранг: {new_rank}",
                parse_mode="HTML"
            )

# ---------------- Дуэли ----------------
@bot.message_handler(commands=['dd'])
def duel_request(message):
    try:
        parts = message.text.split()
        bet = int(parts[1])
        if bet < 50:
            bot.reply_to(message, "❌ Минимальная ставка — 50 монет")
            return
        user = ensure_player(message.from_user)
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("⚔️ Сразиться", callback_data="accept_duel"),
            InlineKeyboardButton("✖️ Отмена", callback_data="cancel_duel")
        )
        msg = bot.send_photo(
            message.chat.id,
            IMG_WAIT_DUEL,
            caption=f"⚔️ <a href='https://t.me/{user['username']}'>{user['username']}</a> вызывает любого на дуэль!\n\n💬 Чтобы принять, нажмите кнопку снизу",
            parse_mode="HTML",
            reply_markup=markup
        )
        pending_duels[message.chat.id] = {"initiator": message.from_user.id, "bet": bet, "msg_id": msg.message_id}
    except:
        bot.reply_to(message, "💬 Чтобы кинуть вызов в чат, введите /dd (сумма)")

@bot.callback_query_handler(func=lambda call: call.data in ["accept_duel","cancel_duel","shoot","shield","cancel"])
def duel_callbacks(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    # --- Ожидающие дуэли ---
    if call.data == "accept_duel":
        if chat_id not in pending_duels:
            bot.answer_callback_query(call.id, "❌ Нет вызова на дуэль")
            return
        initiator_id = pending_duels[chat_id]["initiator"]
        bet = pending_duels[chat_id]["bet"]
        if user_id == initiator_id:
            bot.answer_callback_query(call.id, "❌ Вы не можете принять свой вызов")
            return
        opponent = ensure_player(call.from_user)
        # Удаляем сообщение с кнопками вызова
        bot.delete_message(chat_id, pending_duels[chat_id]["msg_id"])
        del pending_duels[chat_id]
        # Начинаем дуэль
        start_duel(chat_id, initiator_id, user_id, bet)
        bot.answer_callback_query(call.id, "⚔️ Дуэль началась!")
        return
    elif call.data == "cancel_duel":
        if chat_id not in pending_duels:
            bot.answer_callback_query(call.id, "❌ Нет вызова на дуэль")
            return
        if user_id != pending_duels[chat_id]["initiator"]:
            bot.answer_callback_query(call.id, "❌ Только инициатор может отменить")
            return
        bot.delete_message(chat_id, pending_duels[chat_id]["msg_id"])
        del pending_duels[chat_id]
        bot.answer_callback_query(call.id, "✅ Вы отменили дуэль")
        return

    # --- Активные дуэли ---
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
        chance = 20 if duel["shield"].get(opponent_id, False) else 35
        hit = random.randint(1,100) <= chance
        if hit:
            end_duel(chat_id, user_id, opponent_id, duel["bet"])
        else:
            msg = bot.send_message(chat_id, f"💥 <a href='https://t.me/{players[opponent_id]['username']}'>{players[opponent_id]['username']}</a> увернулся!", parse_mode="HTML")
            duel.setdefault("messages", []).append(msg.message_id)
            next_turn(chat_id)
    elif call.data == "cancel":
        opponent_id = duel["player2"] if user_id == duel["player1"] else duel["player1"]
        canceller = players[user_id]
        opponent = players[opponent_id]
        canceller["rating"] -= 15
        canceller["balance"] += int(duel["bet"]*0.35)
        opponent["balance"] += duel["bet"]
        update_rank_in_chat(chat_id, user_id)
        update_rank_in_chat(chat_id, opponent_id)
        bot.delete_message(chat_id, duel["msg_id"])
        for mid in duel.get("messages", []):
            bot.delete_message(chat_id, mid)
        bot.send_photo(
            chat_id,
            IMG_DUEL_CANCEL,
            caption=f"⚔️ <a href='https://t.me/{canceller['username']}'>{canceller['username']}</a> отменил дуэль!\n"
                    f"💰 {int(duel['bet']*0.35)} возвращено\n"
                    f"⚔️ Рейтинг -15\n"
                    f"💰 Баланс <a href='https://t.me/{opponent['username']}'>{opponent['username']}</a> возвращено {duel['bet']}",
            parse_mode="HTML"
        )
        del active_duels[chat_id]

# ---------------- Начало дуэли ----------------
def start_duel(chat_id, player1_id, player2_id, bet):
    p1 = players[player1_id]
    p2 = players[player2_id]
    active_duels[chat_id] = {
        "player1": player1_id,
        "player2": player2_id,
        "bet": bet,
        "turn": player1_id,
        "shield": {player1_id: False, player2_id: False},
        "messages": []
    }

    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("🔫 Выстрел", callback_data="shoot"),
        InlineKeyboardButton("🛡️ Защититься", callback_data="shield")
    )
    markup.row(
        InlineKeyboardButton("✖️ Отмена", callback_data="cancel")
    )

    msg = bot.send_photo(
        chat_id,
        IMG_DUEL_START,
        caption=f"⚔️ Дуэль!\n"
                f"<a href='https://t.me/{p1['username']}'>{p1['username']}</a> против "
                f"<a href='https://t.me/{p2['username']}'>{p2['username']}</a>\n\n"
                f"💰 Ставка: {bet} монет\n\n"
                f"🔹 Ход <a href='https://t.me/{p1['username']}'>{p1['username']}</a>",
        parse_mode="HTML",
        reply_markup=markup
    )
    active_duels[chat_id]["msg_id"] = msg.message_id

# ---------------- Остальные функции ----------------
def next_turn(chat_id):
    duel = active_duels[chat_id]
    duel["turn"] = duel["player2"] if duel["turn"] == duel["player1"] else duel["player1"]
    duel["shield"][duel["turn"]] = False
    p = players[duel["turn"]]
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("🔫 Выстрел", callback_data="shoot"),
        InlineKeyboardButton("🛡️ Защититься", callback_data="shield")
    )
    markup.row(
        InlineKeyboardButton("✖️ Отмена", callback_data="cancel")
    )
    bot.edit_message_caption(
        f"⚔️ Дуэль!\n"
        f"<a href='https://t.me/{players[duel['player1']]['username']}'>{players[duel['player1']]['username']}</a> против "
        f"<a href='https://t.me/{players[duel['player2']]['username']}'>{players[duel['player2']]['username']}</a>\n\n"
        f"💰 Ставка: {duel['bet']} монет\n\n"
        f"🔹 Ход <a href='https://t.me/{p['username']}'>{p['username']}</a>",
        chat_id=chat_id,
        message_id=duel["msg_id"],
        parse_mode="HTML",
        reply_markup=markup
    )

def end_duel(chat_id, winner_id, loser_id, bet):
    winner = players[winner_id]
    loser = players[loser_id]
    winner["balance"] += bet*2
    winner["rating"] += 30
    loser["rating"] -= 15
    update_rank_in_chat(chat_id, winner_id)
    update_rank_in_chat(chat_id, loser_id)
    bot.delete_message(chat_id, active_duels[chat_id]["msg_id"])
    for mid in active_duels[chat_id].get("messages", []):
        bot.delete_message(chat_id, mid)
    bot.send_photo(
        chat_id,
        IMG_DUEL_END,
        caption=f"⚔️ Дуэль завершилась.\n\n"
                f"🔫 <a href='https://t.me/{winner['username']}'>{winner['username']}</a> убил "
                f"<a href='https://t.me/{loser['username']}'>{loser['username']}</a>\n\n"
                f"👑 Победитель: <a href='https://t.me/{winner['username']}'>{winner['username']}</a>\n"
                f"💰 Выигрыш: {bet*2} монет\n"
                f"🎖️ Рейтинг: +30",
        parse_mode="HTML"
    )
    del active_duels[chat_id]

# ---------------- Баланс ----------------
@bot.message_handler(commands=['dbal'])
def check_balance(message):
    user_data = ensure_player(message.from_user)
    bot.send_photo(
        message.chat.id,
        IMG_BALANCE,
        caption=f"⚔️ <a href='https://t.me/{user_data['username']}'>{user_data['username']}</a> — Ваша статистика!\n\n"
                f"💰 Баланс: {user_data['balance']}\n"
                f"🎖️ Ранг: {user_data['rank']}\n"
                f"⚔️ Рейтинг: {user_data['rating']}",
        parse_mode="HTML"
    )

# ---------------- Бонус ----------------
@bot.message_handler(commands=['dbonus'])
def daily_bonus(message):
    user = ensure_player(message.from_user)
    user_id = message.from_user.id
    now = time.time()
    if user_id in bonus_cooldown and now - bonus_cooldown[user_id] < BONUS_COOLDOWN:
        remaining = int(BONUS_COOLDOWN - (now - bonus_cooldown[user_id]))
        mins, secs = divmod(remaining, 60)
        bot.reply_to(message, f"🕒 Бонус снова будет доступен через {mins} минут и {secs} секунд")
        return
    rating_gain = random.randint(5,40)
    user["balance"] += BONUS_AMOUNT
    user["rating"] += rating_gain
    update_rank_in_chat(message.chat.id, user_id)
    bonus_cooldown[user_id] = now
    bot.send_photo(
        message.chat.id,
        IMG_BONUS,
        caption=f"⚔️ <a href='https://t.me/{user['username']}'>{user['username']}</a> Вы получили бонус!\n\n"
                f"💰 +{BONUS_AMOUNT}\n"
                f"🎖️ +{rating_gain}",
        parse_mode="HTML"
    )

# ---------------- Админ / Перевод / Лидерборд ----------------
@bot.message_handler(commands=['двыдать'])
def admin_give(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        target_username = parts[1].replace("@","")
        amount = int(parts[2])
        target = None
        for uid, u in players.items():
            if u["username"] == target_username:
                target = u
                target_id = uid
                break
        if not target:
            target_id = hash(target_username)
            players[target_id] = {"username": target_username, "balance": 0, "rating":0, "rank": get_rank(0)}
            target = players[target_id]
        target["balance"] += amount
        bot.send_photo(
            message.chat.id,
            IMG_TRANSACTION,
            caption=f"💰 К балансу <a href='https://t.me/{target['username']}'>{target['username']}</a> добавлено {amount} монет.",
            parse_mode="HTML"
        )
    except:
        bot.reply_to(message, "💎 Чтобы выдать монеты: /двыдать @username сумма")

@bot.message_handler(commands=['дперевод'])
def transfer_coins(message):
    user = ensure_player(message.from_user)
    try:
        parts = message.text.split()
        target_username = parts[1].replace("@","")
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
        bot.send_photo(
            message.chat.id,
            IMG_TRANSACTION,
            caption=f"⚔️ <a href='https://t.me/{user['username']}'>{user['username']}</a> перевел "
                    f"<a href='https://t.me/{target['username']}'>{target['username']}</a> {amount} монет.\n"
                    f"💰 Баланс <a href='https://t.me/{user['username']}'>{user['username']}</a>: {target['balance']}",
            parse_mode="HTML"
        )
    except:
        bot.reply_to(message, "🔹 Чтобы перевести монеты: /дперевод @username сумма")

@bot.message_handler(commands=['drang'])
def leaderboard(message):
    top = sorted(players.values(), key=lambda x:x["rating"], reverse=True)[:10]
    text = "⚔️ Список лидеров:\n\n"
    for i,p in enumerate(top,start=1):
        text += f"🔹 {i}. <a href='https://t.me/{p['username']}'>{p['username']}</a> - {p['rank']} | {p['rating']}\n"
    bot.send_photo(message.chat.id, IMG_LEADERBOARD, caption=text, parse_mode="HTML")
# ---------------- Запуск ----------------
bot.infinity_polling()