import os, sqlite3, uuid, logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ChatMemberHandler, ContextTypes
from telegram.constants import ChatMemberStatus

TOKEN = os.getenv("BOT_TOKEN")

conn = sqlite3.connect("federation.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS federations (fed_id TEXT PRIMARY KEY, fed_name TEXT, owner_id INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS fed_chats (chat_id INTEGER PRIMARY KEY, fed_id TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS fbans (fed_id TEXT, user_id INTEGER, reason TEXT)")
conn.commit()

def get_fed_by_chat(chat_id):
    cur.execute("SELECT fed_id FROM fed_chats WHERE chat_id=?", (chat_id,))
    r = cur.fetchone()
    return r[0] if r else None

def get_fed_by_owner(owner_id):
    cur.execute("SELECT fed_id FROM federations WHERE owner_id=?", (owner_id,))
    r = cur.fetchone()
    return r[0] if r else None

async def newfed(update, context):
    if get_fed_by_owner(update.effective_user.id):
        await update.message.reply_text("You already have a federation")
        return
    if not context.args:
        await update.message.reply_text("Usage: /newfed <name>")
        return
    fed_name = " ".join(context.args)
    fed_id = str(uuid.uuid4())[:8]
    cur.execute("INSERT INTO federations VALUES (?,?,?)", (fed_id, fed_name, update.effective_user.id))
    conn.commit()
    await update.message.reply_text(f"Federation Created!\nName: {fed_name}\nID: {fed_id}\n\nAdd group: /joinfed {fed_id}", parse_mode="Markdown")

async def joinfed(update, context):
    if update.effective_chat.type == "private":
        await update.message.reply_text("Use this inside a group")
        return
    if not context.args:
        await update.message.reply_text("Usage: /joinfed <ID>")
        return
    fed_id = context.args[0]
    cur.execute("INSERT OR REPLACE INTO fed_chats VALUES (?,?)", (update.effective_chat.id, fed_id))
    conn.commit()
    await update.message.reply_text(f"Group linked to {fed_id}")

async def fban(update, context):
    fed_id = get_fed_by_chat(update.effective_chat.id)
    if not fed_id: return
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else None
    if not target:
        await update.message.reply_text("Reply to a user to fban")
        return
    reason = " ".join(context.args) if context.args else "No reason"
    cur.execute("DELETE FROM fbans WHERE fed_id=? AND user_id=?", (fed_id, target.id))
    cur.execute("INSERT INTO fbans VALUES (?,?,?)", (fed_id, target.id, reason))
    conn.commit()
    cur.execute("SELECT chat_id FROM fed_chats WHERE fed_id=?", (fed_id,))
    count=0
    for (cid,) in cur.fetchall():
        try:
            await context.bot.ban_chat_member(cid, target.id)
            count+=1
        except: pass
    await update.message.reply_text(f"FedBan {target.id} in {count} chats. Reason: {reason}")

async def fedinfo(update, context):
    fed_id = get_fed_by_chat(update.effective_chat.id)
    if not fed_id:
        await update.message.reply_text("Not in federation")
        return
    await update.message.reply_text(f"Fed ID: {fed_id}")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("newfed", newfed))
app.add_handler(CommandHandler("joinfed", joinfed))
app.add_handler(CommandHandler("fban", fban))
app.add_handler(CommandHandler("fedinfo", fedinfo))
app.run_polling()
