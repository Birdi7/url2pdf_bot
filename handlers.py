import asyncio
import logging
from typing import Optional
from aiogram import Bot, Dispatcher, executor, types
from aiogram.utils.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardMarkup, InputFile
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
import config
from mMiddlewares import mLoggingMiddleware, mUpdateUserMiddleware
import url_downloader
from states import *
import texts
import mDecorators
import db_models
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler

loop = asyncio.get_event_loop()
bot = Bot(config.BOT_TOKEN, loop=loop)

dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(mLoggingMiddleware())
dp.middleware.setup(mUpdateUserMiddleware())


scheduler = AsyncIOScheduler()
# todo add persistent storage if you plan to save smth important in the scheduler
scheduler.start()

logging.basicConfig(format="[%(asctime)s] %(levelname)s : %(name)s : %(message)s",
                    level=logging.DEBUG, datefmt="%d-%m-%y %H:%M:%S")
# logging.getLogger('aiogram').setLevel(logging.INFO)
# logging.getLogger('apscheduler').setLevel(logging.CRITICAL)


@dp.message_handler(state='*', commands=['cancel'])
@dp.message_handler(lambda msg: msg.text.lower() == 'cancel', state='*')
async def cancel_handler(msg: types.Message, state: FSMContext, raw_state: Optional[str] = None):
    if raw_state is None:
        return None
    await state.finish()
    await bot.send_message(msg.from_user.id, 'Cancelled')


@dp.message_handler(commands=['start'], state='*')
async def start_command_handler(msg: types.Message):
    await bot.send_message(msg.chat.id, f"{texts.start_command}\n{texts.list_of_commands}")


@dp.message_handler(commands=['help'], state='*')
async def help_command_handler(msg: types.Message):
    await bot.send_message(msg.chat.id, f"{texts.help_command}\n{texts.list_of_commands}")


@dp.message_handler(commands=['url'], state='*')
async def url_command_handler(msg: types.Message):
    await bot.send_message(msg.chat.id, texts.url_command)
    await LinkDialog.first()


@dp.message_handler(commands=['feedback'], state='*')
async def feedback_command_handler(msg: types.Message):
    await bot.send_message(msg.chat.id, texts.feedback_command)
    await FeedbackDialog.first()


@mDecorators.admin
@dp.message_handler(commands=['send_to_everyone'], func=lambda msg: msg.from_user.id in config.admin_ids)
async def send_to_everyone_command_handler(msg: types.Message):
    await bot.send_message(msg.chat.id, 'Отправьте сообщение')
    await SendToEveryoneDialog.first()


async def send_pdf_file(msg):
    await msg.reply('Обрабатываю...')
    out_file_name = 'out_data/out{}.pdf'.format(msg.chat.id)

    if db_models.Url.objects(url=msg.text).count() > 0:
        urlobj = db_models.Url.objects.get(url=msg.text)
    else:
        urlobj = db_models.Url(url=msg.text)

    urlobj.amount += 1
    urlobj.save()

    try:
        url_downloader.download_url_weasyprint(msg.text, out_file_name)
        await bot.send_document(msg.chat.id, InputFile(out_file_name))
    except Exception as e:
        logging.critical("Weasyprint didn't convert. Trying weasyprint")
        try:
            url_downloader.download_url_wkhtmltopdf(msg.text, out_file_name)
            await bot.send_document(msg.chat.id, InputFile(out_file_name))
        except Exception as e:
            await bot.send_message(msg.chat.id, 'Не вышло:( Попробуйте еще раз или сообщите разработчику о проблеме')
            raise e


@dp.message_handler(state=LinkDialog.enter_url)
async def enter_url_handler(msg: types.Message, state: FSMContext):
    await state.finish()
    await send_pdf_file(msg)


@dp.message_handler(state=FeedbackDialog.enter_feedback)
async def enter_feedback_handler(msg: types.Message, state: FSMContext):
    await msg.reply(texts.got)
    await state.finish()

    for admin in config.admin_ids:
        try:
            await bot.send_message(admin, f"[@{msg.from_user.username} ID: {msg.from_user.id} MESSAGE_ID: {msg.message_id}] пишет:\n{msg.text}")
        except:
            pass


@mDecorators.admin
@dp.message_handler(lambda msg: msg.reply_to_message is not None and msg.from_user.id in config.admin_ids)
async def feedback_response_handler(msg: types.Message):
    txt = msg.reply_to_message.text
    user_info = txt[txt.find('['): txt.find(']')][1:]
    chat_id = int(user_info[user_info.find('ID:')+len('ID:')+1:user_info.find('MESSAGE_ID')])
    msg_id = int(user_info[user_info.find('MESSAGE_ID:')+len('MESSAGE_ID:')+1:])

    try:
        await bot.send_message(chat_id, f'Разработчик ответил следующее:\n{msg.text}', reply_to_message_id=msg_id)
    except Exception:
        pass


@dp.message_handler(state=SendToEveryoneDialog.enter_message)
async def enter_send_to_everyone_handler(msg: types.Message):
    await bot.send_message(msg.chat.id, 'Получено')
    scheduler.add_job(send_to_everyone, args=[msg.text])


async def send_to_everyone(txt):
    for u in db_models.User.objects():
        try:
            await bot.send_message(u.chat_id, txt)
        except TelegramAPIError:
            pass
        time.sleep(.5)


async def on_shutdown(dispatcher: Dispatcher):
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()


@dp.message_handler()
async def echo_handler(msg: types.Message):
    if not msg.text.startswith('/'):
        await send_pdf_file(msg)


if __name__ == '__main__':
    executor.start_polling(dp, on_shutdown=on_shutdown, skip_updates=True)
