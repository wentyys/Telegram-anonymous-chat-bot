import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler
)
import re
import random

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

TOKEN = '8881587409:AAFMufuE-61ihZqfuOF8JTOg-Lt54lHq-do'

user_data = {}
waiting_users = {'male': [], 'female': []}
active_chats = {}

FORBIDDEN_WORDS = [
    
]

NICKNAMES = [
    'Анонимный Пользователь'
]

def contains_forbidden_words(text: str) -> bool:
    pattern = r'\b(' + '|'.join(FORBIDDEN_WORDS) + r')\b'
    return re.search(pattern, text, re.IGNORECASE) is not None

def get_new_nickname():
    used_nicknames = {data['nickname'] for data in user_data.values()}
    available_nicknames = [n for n in NICKNAMES if n not in used_nicknames]
    if not available_nicknames:
        return random.choice(NICKNAMES)
    return random.choice(available_nicknames)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    
    if user_id in user_data:
        if user_id in active_chats:
            await update.message.reply_text('Вы уже общаетесь в чате. Отправьте /skip, чтобы найти нового собеседника, или /endchat для завершения диалога.')
            return
        elif user_id in waiting_users.get(user_data[user_id]['gender'], []):
            await update.message.reply_text('Вы уже находитесь в очереди поиска. Ожидайте собеседника...')
            return

    keyboard = [
        [InlineKeyboardButton("Парень", callback_data='male')],
        [InlineKeyboardButton("Девушка", callback_data='female')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        'Добро пожаловать в анонимный чат-бот! Пожалуйста, выберите ваш пол для начала работы.',
        reply_markup=reply_markup
    )

async def set_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    gender = query.data
    
    if user_id in user_data:
        await query.edit_message_text('Вы уже выбрали пол. Отправьте /skip, чтобы найти нового собеседника, или /endchat для завершения диалога.')
        return

    nickname = get_new_nickname()
    user_data[user_id] = {'gender': gender, 'nickname': nickname, 'interests': set()}
    
    await query.edit_message_text(
        f'Спасибо за выбор! Ваш псевдоним — **{nickname}**. '
        f'Вы также можете добавить свои интересы с помощью команды /interests [интерес1, интерес2]. '
        'Сейчас бот начинает поиск собеседника для вас...'
    )
    
    waiting_users[gender].append(user_id)
    await find_chat_partner(user_id, context)

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id in active_chats:
        partner_id = active_chats.pop(user_id, None)
        if partner_id:
            active_chats.pop(partner_id, None)
            await context.bot.send_message(chat_id=partner_id, text="Ваш собеседник завершил текущую сессию чата.")
        await update.message.reply_text('Сессия чата завершена. Отправьте /start, чтобы начать заново.')
        await remove_from_waiting(user_id)
    else:
        await remove_from_waiting(user_id)
        await update.message.reply_text('Вы сейчас не находитесь в чате. Отправьте /start, чтобы запустить поиск.')

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    
    if user_id in active_chats:
        partner_id = active_chats.pop(user_id, None)
        if partner_id:
            active_chats.pop(partner_id, None)
            await context.bot.send_message(
                chat_id=partner_id,
                text="Ваш собеседник переключился на другой чат. Ищем для вас нового партнера..."
            )
            
            waiting_users[user_data[partner_id]['gender']].append(partner_id)
            await find_chat_partner(partner_id, context)
        
        await update.message.reply_text('Вы пропустили этот чат. Ищем другого пользователя...')
        waiting_users[user_data[user_id]['gender']].append(user_id)
        await find_chat_partner(user_id, context)
    else:
        await remove_from_waiting(user_id)
        await update.message.reply_text('Вы не находились в чате. Ищем свободного пользователя...')
        waiting_users[user_data[user_id]['gender']].append(user_id)
        await find_chat_partner(user_id, context)

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id in active_chats:
        partner_id = active_chats.get(user_id)
        if partner_id:
            await context.bot.send_message(
                chat_id=user_id,
                text="Ваша жалоба принята. Мы проверим данный диалог. Сессия чата будет завершена."
            )
            
            await end_chat(update, context)
    else:
        await update.message.reply_text('Вы можете отправить жалобу на пользователя только во время активного диалога.')

async def set_interests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_data:
        await update.message.reply_text('Сначала вам необходимо выбрать свой пол с помощью команды /start.')
        return
    
    if not context.args:
        await update.message.reply_text('Пожалуйста, укажите ваши интересы через запятую. Пример: `/interests игры, кино, спорт`')
        return
        
    interests_list = [interest.strip().lower() for interest in ' '.join(context.args).split(',')]
    user_data[user_id]['interests'] = set(interests_list)
    await update.message.reply_text(f'Ваши интересы успешно сохранены: {", ".join(user_data[user_id]["interests"])}.')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    
    if user_id in active_chats:
        partner_id = active_chats.get(user_id)
        if partner_id:
            nickname = user_data[user_id]['nickname']
            
            # 1. Если отправили ТЕКСТ
            if update.message.text:
                await context.bot.send_message(chat_id=partner_id, text=f'{nickname}: {update.message.text}')
            
            # 2. Если отправили ФОТО (с подписью или без)
            elif update.message.photo:
                caption = f"{nickname}: {update.message.caption}" if update.message.caption else f"{nickname} отправил(а) фото"
                await context.bot.send_photo(chat_id=partner_id, photo=update.message.photo[-1].file_id, caption=caption)
            
            # 3. Если отправили ВИДЕО
            elif update.message.video:
                caption = f"{nickname}: {update.message.caption}" if update.message.caption else f"{nickname} отправил(а) видео"
                await context.bot.send_video(chat_id=partner_id, video=update.message.video.file_id, caption=caption)
            
            # 4. Если отправили СТИКЕР
            elif update.message.sticker:
                # Сначала предупреждаем от кого стикер, а затем шлем его
                await context.bot.send_message(chat_id=partner_id, text=f'{nickname} отправил(а) стикер:')
                await context.bot.send_sticker(chat_id=partner_id, sticker=update.message.sticker.file_id)
        else:
            await update.message.reply_text('Ваш собеседник не найден. Отправьте /endchat, чтобы завершить сессию.')
    else:
        await update.message.reply_text('Вы сейчас ни с кем не связаны. Отправьте /start, чтобы начать новый чат.')

async def find_chat_partner(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_info = user_data.get(user_id)
    if not user_info:
        return

    user_gender = user_info['gender']
    opposite_gender = 'male' if user_gender == 'female' else 'female'
    
    if not waiting_users[opposite_gender]:
        await context.bot.send_message(
            chat_id=user_id,
            text="В данный момент нет доступных пользователей противоположного пола. Ожидайте других участников..."
        )
        return

    best_match_id = None
    max_match_score = -1

    for partner_id in waiting_users[opposite_gender]:
        partner_info = user_data.get(partner_id)
        if not partner_info:
            continue
        
        common_interests = user_info['interests'].intersection(partner_info['interests'])
        match_score = len(common_interests)
        
        if match_score > max_match_score:
            best_match_id = partner_id
            max_match_score = match_score

    if best_match_id:
        partner_id = best_match_id
        waiting_users[opposite_gender].remove(partner_id)
    else:
        partner_id = waiting_users[opposite_gender].pop(0)

    active_chats[user_id] = partner_id
    active_chats[partner_id] = user_id
    
    common_interests = user_info['interests'].intersection(user_data[partner_id]['interests'])
    interests_message = ''
    if common_interests:
        interests_message = f"\nУ вас обоих схожие интересы: {', '.join(common_interests)}."

    await context.bot.send_message(
        chat_id=user_id,
        text=f"Вы подключены к пользователю **{user_data[partner_id]['nickname']}**! Можете начинать общение.{interests_message}"
    )
    await context.bot.send_message(
        chat_id=partner_id,
        text=f"Вы подключены к пользователю **{user_data[user_id]['nickname']}**! Можете начинать общение.{interests_message}"
    )

async def remove_from_waiting(user_id: int) -> None:
    gender = user_data.get(user_id, {}).get('gender')
    if gender and user_id in waiting_users[gender]:
        waiting_users[gender].remove(user_id)

def main() -> None:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('endchat', end_chat))
    application.add_handler(CommandHandler('skip', skip))
    application.add_handler(CommandHandler('report', report))
    application.add_handler(CommandHandler('interests', set_interests))
    application.add_handler(CallbackQueryHandler(set_gender))
    
    # Расширенный фильтр: теперь бот принимает текст, фото, видео и стикеры
    media_filter = filters.TEXT | filters.PHOTO | filters.VIDEO | filters.STICKER
    application.add_handler(MessageHandler(media_filter & ~filters.COMMAND, handle_message))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
    
