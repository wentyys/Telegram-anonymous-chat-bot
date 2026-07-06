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
            await update.message.reply_text('Anda sudah dalam sesi chat. Kirim /skip untuk mencari pengguna baru atau /endchat untuk mengakhiri.')
            return
        elif user_id in waiting_users.get(user_data[user_id]['gender'], []):
            await update.message.reply_text('Anda sudah dalam antrian. Menunggu pengguna lain...')
            return

    keyboard = [
        [InlineKeyboardButton("Laki-laki", callback_data='male')],
        [InlineKeyboardButton("Perempuan", callback_data='female')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        'Selamat datang di bot chat anonim! Silakan pilih gender Anda untuk memulai.',
        reply_markup=reply_markup
    )

async def set_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    gender = query.data
    
    if user_id in user_data:
        await query.edit_message_text('Anda sudah memilih gender. Kirim /skip untuk mencari pengguna baru atau /endchat untuk mengakhiri.')
        return

    nickname = get_new_nickname()
    user_data[user_id] = {'gender': gender, 'nickname': nickname, 'interests': set()}
    
    await query.edit_message_text(
        f'Terima kasih telah memilih. Nama samaran Anda adalah **{nickname}**. '
        f'Anda juga bisa menambahkan minat dengan perintah /interests [minat1, minat2]. '
        'Sekarang, bot akan mulai mencari pasangan chat untuk Anda...'
    )
    
    waiting_users[gender].append(user_id)
    await find_chat_partner(user_id, context)

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id in active_chats:
        partner_id = active_chats.pop(user_id, None)
        if partner_id:
            active_chats.pop(partner_id, None)
            await context.bot.send_message(chat_id=partner_id, text="Pasangan chat Anda telah mengakhiri sesi chat.")
        await update.message.reply_text('Sesi chat telah diakhiri. Kirim /start untuk memulai lagi.')
        await remove_from_waiting(user_id)
    else:
        await remove_from_waiting(user_id)
        await update.message.reply_text('Anda tidak sedang dalam sesi chat. Kirim /start untuk memulai.')

async def skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    
    if user_id in active_chats:
        partner_id = active_chats.pop(user_id, None)
        if partner_id:
            active_chats.pop(partner_id, None)
            await context.bot.send_message(
                chat_id=partner_id,
                text="Pasangan chat Anda telah melewati sesi. Mencari pasangan baru..."
            )
            
            waiting_users[user_data[partner_id]['gender']].append(partner_id)
            await find_chat_partner(partner_id, context)
        
        await update.message.reply_text('Anda telah melewati sesi chat. Mencari pengguna lain...')
        waiting_users[user_data[user_id]['gender']].append(user_id)
        await find_chat_partner(user_id, context)
    else:
        await remove_from_waiting(user_id)
        await update.message.reply_text('Anda tidak dalam sesi chat. Mencari pengguna lain...')
        waiting_users[user_data[user_id]['gender']].append(user_id)
        await find_chat_partner(user_id, context)

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id in active_chats:
        partner_id = active_chats.get(user_id)
        if partner_id:
            await context.bot.send_message(
                chat_id=user_id,
                text="Laporan Anda telah diterima. Kami akan meninjau percakapan ini. Sesi chat akan diakhiri."
            )
            
            await end_chat(update, context)
    else:
        await update.message.reply_text('Anda hanya bisa melaporkan pengguna saat sedang dalam sesi chat.')

async def set_interests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    if user_id not in user_data:
        await update.message.reply_text('Anda harus memilih gender terlebih dahulu dengan /start.')
        return
    
    if not context.args:
        await update.message.reply_text('Sertakan minat Anda. Contoh: `/interests membaca, film, olahraga`')
        return
        
    interests_list = [interest.strip().lower() for interest in ' '.join(context.args).split(',')]
    user_data[user_id]['interests'] = set(interests_list)
    await update.message.reply_text(f'Minat Anda telah disimpan: {", ".join(user_data[user_id]["interests"])}.')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user_message = update.message.text
    
    if contains_forbidden_words(user_message):
        await update.message.reply_text('Pesan Anda mengandung kata-kata terlarang dan tidak akan dikirim. Mohon gunakan bahasa yang sopan.')
        return
        
    if user_id in active_chats:
        partner_id = active_chats.get(user_id)
        if partner_id:
            nickname = user_data[user_id]['nickname']
            await context.bot.send_message(chat_id=partner_id, text=f'{nickname}: {user_message}')
        else:
            await update.message.reply_text('Pasangan chat Anda tidak ditemukan. Kirim /endchat untuk mengakhiri sesi.')
    else:
        await update.message.reply_text('Anda tidak sedang terhubung dengan pengguna lain. Kirim /start untuk memulai chat baru.')

async def find_chat_partner(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_info = user_data.get(user_id)
    if not user_info:
        return

    user_gender = user_info['gender']
    opposite_gender = 'male' if user_gender == 'female' else 'female'
    
    if not waiting_users[opposite_gender]:
        await context.bot.send_message(
            chat_id=user_id,
            text="Tidak ada pengguna lawan jenis yang tersedia. Menunggu pengguna lain..."
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
        interests_message = f"\nKalian berdua memiliki minat yang sama: {', '.join(common_interests)}."

    await context.bot.send_message(
        chat_id=user_id,
        text=f"Anda terhubung dengan **{user_data[partner_id]['nickname']}**! Mulailah mengirim pesan.{interests_message}"
    )
    await context.bot.send_message(
        chat_id=partner_id,
        text=f"Anda terhubung dengan **{user_data[user_id]['nickname']}**! Mulailah mengirim pesan.{interests_message}"
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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
