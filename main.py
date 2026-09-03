import random
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- ТОКЕН (замените на свой) ---
import os
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
@dp.message(Command("game"))
async def show_menu(message: types.Message):
    text = (
        "Привет! Я игровой бот.\n\n"
        "Вот список доступных игр:\n"
        "/rps – Камень, ножницы, бумага (для 2 игроков).\n"
        "/ttt – Крестики-нолики (для 2 игроков).\n"
        "/guess – Угадай число (для 2 игроков).\n"
        "/slot – Игровой автомат (для 2 игроков).\n"
        "/flappy – Играть в Flappy Bird.\n\n"
        "Чтобы остановить текущую игру, используйте /stop.\n"
        "Для игры вдвоём добавьте бота в группу и пригласите друга!"
    )
    await message.answer(text)

# ---------- ИГРА RPS (Камень, ножницы, бумага) вдвоём ----------
pvp_sessions = {}

def get_choice_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Бумага", callback_data="paper")
    builder.button(text="✂️ Ножницы", callback_data="scissors")
    builder.button(text="🪨 Камень", callback_data="rock")
    builder.adjust(3)
    return builder.as_markup()

def get_number_keyboard(prefix="guess"):
    """Генерирует клавиатуру с цифрами 1-6 для игры 'Угадай число'."""
    keyboard = []
    row = []
    for i in range(1, 7):
        row.append(InlineKeyboardButton(text=str(i), callback_data=f"{prefix}_{i}"))
        if i % 3 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("rps"))
async def cmd_rps(message: types.Message):
    chat_id = message.chat.id
    if chat_id in pvp_sessions:
        await message.answer("В этом чате уже идёт игра! Дождитесь окончания.")
        return
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("Эта игра работает только в группе! Добавьте бота в группу с другом.")
        return
    pvp_sessions[chat_id] = {
        "players": {},
        "names": {},
        "turn": 0,
    }
    text = "👥 Камень, ножницы, бумага (вдвоём)\n\nПервый игрок, делай ход! (нажми кнопку)"
    await message.answer(text, reply_markup=get_choice_keyboard())

@dp.callback_query(lambda c: c.data and c.data in ["paper", "scissors", "rock"])
async def handle_rps(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    choice = callback.data

    session = pvp_sessions.get(chat_id)
    if not session:
        await callback.answer("Нет активной игры. Напишите /rps для начала.")
        return

    if "names" not in session:
        session["names"] = {}

    if user_id in session["players"]:
        await callback.answer("Ты уже сделал ход! Жди второго игрока.")
        return

    if user_id not in session["names"]:
        session["names"][user_id] = callback.from_user.first_name or callback.from_user.username or "Игрок"

    if session["turn"] == 0:
        session["players"][user_id] = choice
        session["turn"] = 1
        await callback.message.edit_text(
            "👥 Камень, ножницы, бумага (вдвоём)\n\nПервый игрок сделал ход. Теперь второй игрок, твой черёд!",
            reply_markup=get_choice_keyboard()
        )
        await callback.answer()
        return

    if session["turn"] == 1:
        session["players"][user_id] = choice
        players = session["players"]
        user_ids = list(players.keys())
        if len(user_ids) != 2:
            await callback.answer("Ошибка! Начните заново через /rps")
            return
        u1, u2 = user_ids[0], user_ids[1]
        ch1, ch2 = players[u1], players[u2]

        name1 = session["names"].get(u1, "Игрок 1")
        name2 = session["names"].get(u2, "Игрок 2")

        if ch1 == ch2:
            result = "🤝 Ничья!"
        elif (ch1 == "paper" and ch2 == "rock") or \
             (ch1 == "scissors" and ch2 == "paper") or \
             (ch1 == "rock" and ch2 == "scissors"):
            result = f"🏆 Победил {name1}!"
        else:
            result = f"🏆 Победил {name2}!"

        emoji = {"paper": "📄", "scissors": "✂️", "rock": "🪨"}
        final_text = (
            f"👥 Камень, ножницы, бумага — Результат\n\n"
            f"{name1}: {emoji[ch1]}\n"
            f"{name2}: {emoji[ch2]}\n\n"
            f"{result}\n\n"
            f"Игра завершена! Начните новую через /rps."
        )
        await callback.message.edit_text(final_text, reply_markup=None)
        del pvp_sessions[chat_id]
        await callback.answer()
        return

# ---------- ИГРА КРЕСТИКИ-НОЛИКИ ----------
ttt_games = {}

class TicTacToe:
    def __init__(self, player1_id, player2_id, name1, name2):
        self.players = [player1_id, player2_id]
        self.names = [name1, name2]
        self.board = [''] * 9
        self.turn = 0
        self.winner = None
        self.message_id = None

def get_ttt_keyboard(game):
    keyboard = []
    for i in range(0, 9, 3):
        row = []
        for j in range(3):
            idx = i + j
            symbol = game.board[idx] if game.board[idx] else '⬜'
            row.append(InlineKeyboardButton(text=symbol, callback_data=f"ttt_{idx}"))
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("ttt"))
async def cmd_ttt(message: types.Message):
    chat_id = message.chat.id
    if chat_id in ttt_games and isinstance(ttt_games[chat_id], TicTacToe):
        await message.answer("В этом чате уже идёт игра! Дождитесь окончания.")
        return
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("Эта игра работает только в группе! Добавьте бота в группу с другом.")
        return

    ttt_games[chat_id] = {
        "msg_id": None,
        "players": [],
        "names": []
    }
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Присоединиться", callback_data="ttt_join")]
    ])
    msg = await message.answer(
        "🎮 Крестики-нолики (для 2 игроков)\n\n"
        "Два игрока должны нажать кнопку «Присоединиться».\n"
        "Первый нажавший будет X, второй – O.",
        reply_markup=keyboard
    )
    ttt_games[chat_id]["msg_id"] = msg.message_id

@dp.callback_query(lambda c: c.data == "ttt_join")
async def ttt_join(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    game_data = ttt_games.get(chat_id)

    if not game_data or isinstance(game_data, TicTacToe):
        await callback.answer("Игра уже началась или недоступна.")
        return

    if user_id in game_data["players"]:
        await callback.answer("Ты уже в игре!")
        return
    if len(game_data["players"]) >= 2:
        await callback.answer("Уже два игрока!")
        return

    game_data["players"].append(user_id)
    name = callback.from_user.first_name or callback.from_user.username or "Игрок"
    game_data["names"].append(name)
    await callback.answer(f"Ты присоединился как {name}!")

    if len(game_data["players"]) == 2:
        p1, p2 = game_data["players"]
        n1, n2 = game_data["names"]
        game = TicTacToe(p1, p2, n1, n2)
        ttt_games[chat_id] = game

        text = (
            "🎮 Крестики-нолики\n\n"
            f"{n1} — X\n"
            f"{n2} — O\n\n"
            "Игра началась! Первый ход — X."
        )
        await callback.message.edit_text(text, reply_markup=get_ttt_keyboard(game))
        game.message_id = callback.message.message_id

@dp.callback_query(lambda c: c.data and c.data.startswith('ttt_') and c.data != "ttt_join")
async def ttt_move(callback: CallbackQuery):
    data = callback.data.split('_')
    if len(data) != 2:
        return
    try:
        idx = int(data[1])
    except ValueError:
        return

    chat_id = callback.message.chat.id
    game = ttt_games.get(chat_id)
    if not isinstance(game, TicTacToe):
        await callback.answer("Игра не найдена или уже завершена.")
        return

    user_id = callback.from_user.id
    if user_id != game.players[game.turn]:
        await callback.answer("Сейчас не твой ход!")
        return

    if game.board[idx] != '':
        await callback.answer("Эта клетка уже занята!")
        return

    symbol = 'X' if game.turn == 0 else 'O'
    game.board[idx] = symbol

    win_combos = [
        [0,1,2], [3,4,5], [6,7,8],
        [0,3,6], [1,4,7], [2,5,8],
        [0,4,8], [2,4,6]
    ]
    winner = None
    for combo in win_combos:
        if game.board[combo[0]] == game.board[combo[1]] == game.board[combo[2]] != '':
            winner = game.board[combo[0]]
            break
    if winner:
        winner_idx = 0 if winner == 'X' else 1
        winner_name = game.names[winner_idx]
        await callback.message.edit_text(
            f"🏆 Победил {winner_name} ({winner})!\n\n"
            "Игра завершена. Чтобы сыграть снова, введите /ttt.",
            reply_markup=None
        )
        del ttt_games[chat_id]
        await callback.answer()
        return

    if all(cell != '' for cell in game.board):
        await callback.message.edit_text(
            "🤝 Ничья!\n\nИгра завершена. Чтобы сыграть снова, введите /ttt.",
            reply_markup=None
        )
        del ttt_games[chat_id]
        await callback.answer()
        return

    game.turn = 1 - game.turn
    next_symbol = 'X' if game.turn == 0 else 'O'
    next_name = game.names[game.turn]
    text = (
        "🎮 Крестики-нолики\n\n"
        f"{game.names[0]} — X\n"
        f"{game.names[1]} — O\n\n"
        f"Сейчас ходит {next_symbol} ({next_name})."
    )
    await callback.message.edit_text(text, reply_markup=get_ttt_keyboard(game))
    await callback.answer()

# ---------- ИГРА "УГАДАЙ ЧИСЛО" ----------
guess_games = {}

class GuessGame:
    def __init__(self, player1_id, player2_id, name1, name2):
        self.players = [player1_id, player2_id]
        self.names = [name1, name2]
        self.guesses = {}
        self.turn = 0
        self.result = None
        self.message_id = None

@dp.message(Command("guess"))
async def cmd_guess(message: types.Message):
    chat_id = message.chat.id
    if chat_id in guess_games and isinstance(guess_games[chat_id], GuessGame):
        await message.answer("В этом чате уже идёт игра! Дождитесь окончания.")
        return
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("Эта игра работает только в группе! Добавьте бота в группу с другом.")
        return

    guess_games[chat_id] = {
        "msg_id": None,
        "players": [],
        "names": []
    }
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Присоединиться", callback_data="guess_join")]
    ])
    msg = await message.answer(
        "🎲 **Угадай число**\n\n"
        "Два игрока должны нажать кнопку «Присоединиться».\n"
        "Каждый по очереди выбирает число от 1 до 6.\n"
        "Побеждает тот, кто точно угадает выпавшее число!",
        reply_markup=keyboard
    )
    guess_games[chat_id]["msg_id"] = msg.message_id

@dp.callback_query(lambda c: c.data == "guess_join")
async def guess_join(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    game_data = guess_games.get(chat_id)

    if not game_data or isinstance(game_data, GuessGame):
        await callback.answer("Игра уже началась или недоступна.")
        return

    if user_id in game_data["players"]:
        await callback.answer("Ты уже в игре!")
        return
    if len(game_data["players"]) >= 2:
        await callback.answer("Уже два игрока!")
        return

    game_data["players"].append(user_id)
    name = callback.from_user.first_name or callback.from_user.username or "Игрок"
    game_data["names"].append(name)
    await callback.answer(f"Ты присоединился как {name}!")

    if len(game_data["players"]) == 2:
        p1, p2 = game_data["players"]
        n1, n2 = game_data["names"]
        game = GuessGame(p1, p2, n1, n2)
        guess_games[chat_id] = game

        text = (
            "🎲 **Угадай число**\n\n"
            f"{n1} — твой ход! Выбери число от 1 до 6."
        )
        keyboard = get_number_keyboard("guess")
        await callback.message.edit_text(text, reply_markup=keyboard)
        game.message_id = callback.message.message_id

@dp.callback_query(lambda c: c.data and c.data.startswith('guess_') and c.data != "guess_join")
async def guess_move(callback: CallbackQuery):
    data = callback.data.split('_')
    if len(data) != 2:
        return
    try:
        number = int(data[1])
    except ValueError:
        return

    chat_id = callback.message.chat.id
    game = guess_games.get(chat_id)
    if not isinstance(game, GuessGame):
        await callback.answer("Игра не найдена или уже завершена.")
        return

    user_id = callback.from_user.id
    if user_id != game.players[game.turn]:
        await callback.answer("Сейчас не твой ход!")
        return

    if user_id in game.guesses:
        await callback.answer("Ты уже выбрал число!")
        return

    game.guesses[user_id] = number
    await callback.answer(f"Ты выбрал число {number}!")

    if game.turn == 0:
        game.turn = 1
        text = (
            "🎲 **Угадай число**\n\n"
            f"{game.names[1]} — твой ход! Выбери число от 1 до 6."
        )
        await callback.message.edit_text(text, reply_markup=get_number_keyboard("guess"))
        return

    if game.turn == 1:
        # Оба игрока выбрали числа – бросаем кубик
        await asyncio.sleep(3)
        dice_msg = await bot.send_dice(chat_id=chat_id, emoji="🎲")
        dice_value = dice_msg.dice.value
        await asyncio.sleep(3)

        p1_id, p2_id = game.players
        p1_guess = game.guesses[p1_id]
        p2_guess = game.guesses[p2_id]

        if p1_guess == dice_value and p2_guess == dice_value:
            result_text = f"🤝 Ничья! Оба угадали число {dice_value}!"
        elif p1_guess == dice_value:
            result_text = f"🏆 Победил {game.names[0]} (выбрал {p1_guess}, выпало {dice_value})!"
        elif p2_guess == dice_value:
            result_text = f"🏆 Победил {game.names[1]} (выбрал {p2_guess}, выпало {dice_value})!"
        else:
            result_text = f"😞 Никто не угадал! Выпало {dice_value}."

        final_text = (
            f"🎲 **Угадай число — Результат**\n\n"
            f"{game.names[0]} выбрал: {p1_guess}\n"
            f"{game.names[1]} выбрал: {p2_guess}\n"
            f"Выпало: **{dice_value}**\n\n"
            f"{result_text}\n\n"
            f"Игра завершена! Начните новую через /guess."
        )
        await callback.message.edit_text(final_text, reply_markup=None)
        del guess_games[chat_id]
        await callback.answer()

# ---------- ИГРА "ИГРОВОЙ АВТОМАТ (777)" ----------
slot_games = {}

class SlotGame:
    def __init__(self, player1_id, player2_id, name1, name2):
        self.players = [player1_id, player2_id]
        self.names = [name1, name2]
        self.turn = 0
        self.winner = None
        self.message_id = None
        self.last_slot_message_id = None

@dp.message(Command("slot"))
async def cmd_slot(message: types.Message):
    chat_id = message.chat.id
    if chat_id in slot_games and isinstance(slot_games[chat_id], SlotGame):
        await message.answer("В этом чате уже идёт игра! Дождитесь окончания.")
        return
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("Эта игра работает только в группе! Добавьте бота в группу с другом.")
        return

    slot_games[chat_id] = {
        "msg_id": None,
        "players": [],
        "names": []
    }
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Присоединиться", callback_data="slot_join")]
    ])
    msg = await message.answer(
        "🎰 **Игровой автомат (777)**\n\n"
        "Два игрока должны нажать кнопку «Присоединиться».\n"
        "Каждый по очереди крутит слот.\n"
        "Кто первым выбьет **777** (джекпот) — тот победил!",
        reply_markup=keyboard
    )
    slot_games[chat_id]["msg_id"] = msg.message_id

@dp.callback_query(lambda c: c.data == "slot_join")
async def slot_join(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    game_data = slot_games.get(chat_id)

    if not game_data or isinstance(game_data, SlotGame):
        await callback.answer("Игра уже началась или недоступна.")
        return

    if user_id in game_data["players"]:
        await callback.answer("Ты уже в игре!")
        return
    if len(game_data["players"]) >= 2:
        await callback.answer("Уже два игрока!")
        return

    game_data["players"].append(user_id)
    name = callback.from_user.first_name or callback.from_user.username or "Игрок"
    game_data["names"].append(name)
    await callback.answer(f"Ты присоединился как {name}!")

    if len(game_data["players"]) == 2:
        p1, p2 = game_data["players"]
        n1, n2 = game_data["names"]
        game = SlotGame(p1, p2, n1, n2)
        slot_games[chat_id] = game

        text = (
            "🎰 **Игровой автомат (777)**\n\n"
            f"{n1} — твой ход! Нажми «Крутить», чтобы испытать удачу."
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Крутить", callback_data="slot_spin")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard)
        game.message_id = callback.message.message_id

@dp.callback_query(lambda c: c.data == "slot_spin")
async def slot_spin(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    game = slot_games.get(chat_id)
    if not isinstance(game, SlotGame):
        await callback.answer("Игра не найдена или уже завершена.")
        return

    user_id = callback.from_user.id
    if user_id != game.players[game.turn]:
        await callback.answer("Сейчас не твой ход!")
        return

    if game.last_slot_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=game.last_slot_message_id)
        except Exception:
            pass

    slot_msg = await bot.send_dice(chat_id=chat_id, emoji="🎰")
    slot_value = slot_msg.dice.value
    game.last_slot_message_id = slot_msg.message_id

    await asyncio.sleep(3)

    if slot_value == 64:
        winner_name = game.names[game.turn]
        await callback.message.edit_text(
            f"🎰 **ДЖЕКПОТ!**\n\n"
            f"{winner_name} выбил **777**!\n\n"
            f"🏆 {winner_name} победил в игре!",
            reply_markup=None
        )
        try:
            await bot.delete_message(chat_id=chat_id, message_id=game.last_slot_message_id)
        except:
            pass
        del slot_games[chat_id]
        await callback.answer()
        return

    game.turn = 1 - game.turn
    next_name = game.names[game.turn]
    text = (
        "🎰 **Игровой автомат (777)**\n\n"
        f"Выпало: **{slot_value}**\n\n"
        f"{next_name} — твой ход! Нажми «Крутить»."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Крутить", callback_data="slot_spin")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# ---------- КОМАНДА /stop (остановить все игры) ----------
@dp.message(Command("stop"))
async def cmd_stop(message: types.Message):
    chat_id = message.chat.id
    stopped = []

    if chat_id in pvp_sessions:
        del pvp_sessions[chat_id]
        stopped.append("Камень-ножницы-бумага (PvP)")
    if chat_id in ttt_games:
        if isinstance(ttt_games[chat_id], TicTacToe):
            del ttt_games[chat_id]
            stopped.append("Крестики-нолики")
        elif isinstance(ttt_games[chat_id], dict) and "players" in ttt_games[chat_id]:
            del ttt_games[chat_id]
            stopped.append("Крестики-нолики (ожидание)")
    if chat_id in guess_games:
        if isinstance(guess_games[chat_id], GuessGame):
            del guess_games[chat_id]
            stopped.append("Угадай число")
        elif isinstance(guess_games[chat_id], dict) and "players" in guess_games[chat_id]:
            del guess_games[chat_id]
            stopped.append("Угадай число (ожидание)")
    if chat_id in slot_games:
        if isinstance(slot_games[chat_id], SlotGame):
            del slot_games[chat_id]
            stopped.append("Игровой автомат")
        elif isinstance(slot_games[chat_id], dict) and "players" in slot_games[chat_id]:
            del slot_games[chat_id]
            stopped.append("Игровой автомат (ожидание)")

    if stopped:
        await message.answer(
            f"🛑 Игры остановлены: {', '.join(stopped)}.\n"
            "Можете начать новую через /start или /game."
        )
    else:
        await message.answer("Нет активных игр в этом чате.")

# ---------- КОМАНДА ДЛЯ FLAPPY BIRD ----------
@dp.message(Command("flappy"))
async def cmd_flappy(message: types.Message):
    await bot.send_game(
        chat_id=message.chat.id,
        game_short_name="FlappyBird"
    )

# Обработчик нажатия на кнопку "Play"
@dp.callback_query(lambda c: c.game_short_name is not None)
async def handle_game_callback(callback_query: types.CallbackQuery):
    await callback_query.answer(
        url="https://yanksss9.github.io/flappy-bird-game/"
    )

# ---------- ЗАПУСК ----------
if __name__ == "__main__":
    dp.run_polling(bot)
