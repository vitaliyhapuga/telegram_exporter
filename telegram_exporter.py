from telethon.sync import TelegramClient
from telethon.tl.types import (
    MessageMediaPhoto,
    MessageMediaDocument,
    DocumentAttributeAudio,
    PeerUser,
    PeerChat,
    PeerChannel
)
from tqdm import tqdm
import os
import html

# API_ID = REPLACE WITH YOURS
# API_HASH = 'REPLACE WITH YOURS'
session_name = 'tg_session'

MEDIA_DIRS = {
    "voice": "media/voice",
    "photo": "media/photo",
    "video": "media/video",
    "document": "media/document"
}
for folder in MEDIA_DIRS.values():
    os.makedirs(folder, exist_ok=True)

client = TelegramClient(session_name, API_ID, API_HASH)

HTML_HEADER = '''
<html><head><meta charset="utf-8">
<style>
body { font-family: sans-serif; background: #f5f5f5; padding: 20px; }
.msg { background: #fff; border-radius: 8px; padding: 12px 16px; margin: 10px 0; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
.sender { font-weight: bold; }
.meta { font-size: 12px; color: #666; margin-bottom: 6px; }
.forwarded { background: #e6f2ff; padding: 4px 8px; border-left: 4px solid #3399ff; margin-top: 4px; }
.reply { font-size: 12px; color: #555; margin-top: 4px; padding-left: 10px; border-left: 2px solid #ccc; }
.media { margin-top: 8px; }
img, video, audio { max-width: 300px; display: block; margin-top: 5px; }
</style></head><body>
<h1>Chat history</h1>
'''

async def get_forwarded_from_name(client, fwd):
    if getattr(fwd, 'from_name', None):
        return fwd.from_name.title
    from_id = getattr(fwd, 'from_id', None)
    if from_id is None:
        return "Unknown"
    try:
        if isinstance(from_id, PeerUser):
            user = await client.get_entity(from_id.user_id)
            return user.first_name or "Unknown"
        elif isinstance(from_id, PeerChat):
            chat = await client.get_entity(from_id.chat_id)
            return chat.title or "Unknown"
        elif isinstance(from_id, PeerChannel):
            channel = await client.get_entity(from_id.channel_id)
            return channel.title or "Unknown"
    except:
        return "Unknown"
    return "Unknown"

async def main():
    await client.connect()
    if not await client.is_user_authorized():
        phone = input("Your phone number for auth: ")
        await client.send_code_request(phone)
        code = input("Telegram code: ")
        await client.sign_in(phone, code)

    dialogs = await client.get_dialogs()
    for i, d in enumerate(dialogs):
        print(f"[{i}] {d.name} (ID: {d.id})")

    chat_index = int(input("Chat number to export: "))
    chat = dialogs[chat_index].entity

    messages = []
    async for message in client.iter_messages(chat, reverse=True):
        messages.append(message)

    msg_dict = {m.id: m for m in messages}

    print(f"🔄 Messages to be downloaded: {len(messages)}")

    html_lines = [HTML_HEADER]

    for message in tqdm(messages):
        sender = await message.get_sender()
        name = html.escape(sender.first_name) if sender and sender.first_name else "Неизвестный"
        date = message.date.strftime("%Y-%m-%d %H:%M:%S")
        text = html.escape(message.text or "")
        msg_id = message.id

        block = f'<div class="msg" id="msg{msg_id}">'
        block += f'<div class="meta">🕒 {date} | 🆔 ID: {msg_id}</div>'
        block += f'<div class="sender">{name}</div>'

        if message.forward:
            from_name = await get_forwarded_from_name(client, message.forward)
            from_name = html.escape(str(from_name))
            block += f'<div class="forwarded">🔁 Forwarded from: {from_name}</div>'

        if hasattr(message, "reply_to") and hasattr(message.reply_to, "reply_to_msg_id"):
            reply_id = message.reply_to.reply_to_msg_id
            reply_msg = msg_dict.get(reply_id)
            if reply_msg:
                reply_sender = await reply_msg.get_sender()
                reply_name_raw = (reply_sender.first_name if reply_sender and reply_sender.first_name else "Невідомий")
                reply_name = html.escape(reply_name_raw)
                reply_text = html.escape(reply_msg.text or "")
                short_text = (reply_text[:100] + '...') if len(reply_text) > 100 else reply_text
                block += (
                    f'<div class="reply">💬 Reply to '
                    f'<a href="#msg{reply_id}">message {reply_id}</a> from <b>{reply_name}</b>:<br>'
                    f'<i>{short_text}</i></div>'
                )
            else:
                block += f'<div class="reply">💬 Reply to message with ID: {reply_id}</div>'

        if text:
            block += f'<div class="text">{text}</div>'

        if message.media:
            media_block = '<div class="media">'
            if isinstance(message.media, MessageMediaPhoto):
                file_path = await message.download_media(file=MEDIA_DIRS["photo"])
                if file_path:
                    rel_path = os.path.relpath(file_path)
                    media_block += f'<img src="{rel_path}">'
                else:
                    media_block += '[❌ Unable to download a photo]'
            elif isinstance(message.media, MessageMediaDocument):
                doc = getattr(message.media, 'document', None)
                if doc:
                    attrs = doc.attributes
                    is_voice = any(isinstance(a, DocumentAttributeAudio) and a.voice for a in attrs)
                    mime = doc.mime_type or ""
                    file_name = message.file.name or "file"

                    folder = "voice" if is_voice else (
                        "video" if mime.startswith("video") else "document"
                    )
                    file_path = await message.download_media(file=MEDIA_DIRS[folder])
                    if file_path:
                        rel_path = os.path.relpath(file_path)
                        if folder == "voice":
                            media_block += f'🎤 <b>{file_name}</b><br><audio controls src="{rel_path}"></audio>'
                        elif folder == "video":
                            media_block += f'🎥 <b>{file_name}</b><br><video controls src="{rel_path}"></video>'
                        else:
                            media_block += f'📎 <a href="{rel_path}">{file_name}</a>'
                    else:
                        media_block += '[❌ Unable to download media]'
            media_block += '</div>'
            block += media_block

        block += '</div>'
        html_lines.append(block)

    html_lines.append('</body></html>')

    with open("chat_export.html", "w", encoding="utf-8") as f:
        f.write("\n".join(html_lines))

    print("✅ I'm done: chat_export.html")

with client:
    client.loop.run_until_complete(main())