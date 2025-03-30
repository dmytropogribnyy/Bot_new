from aiogram import types
from aiogram.dispatcher import Dispatcher
from config import ALLOWED_USER_ID
from trader import get_open_positions


def register_handlers(dp: Dispatcher):
    @dp.message_handler(commands=['positions'])
    async def show_positions(message: types.Message):
        if message.from_user.id != ALLOWED_USER_ID:
            return

        positions = get_open_positions()
        if not positions:
            await message.reply("No open positions.")
        else:
            msg = "\ud83d\udcca *Open Positions:*\n"
            for pos in positions:
                value = round(pos['size'] * pos['entry_price'], 2)
                side_label = "BUY (long)" if pos['side'] == 'LONG' else "SELL (short)"
                msg += f"\u2022 {pos['symbol']} | {side_label} | {pos['size']} @ {pos['entry_price']} \u2248 ${value}\n"
            await message.reply(msg, parse_mode="Markdown")
