from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Defaults
from telegram import Update
import re
import asyncio
import json
import os
import nest_asyncio
import datetime
from datetime import time
import pytz
from zoneinfo import ZoneInfo

# NUOVO IMPORT
from git_helper import git_auto_sync

nest_asyncio.apply()

BOT_TOKEN = "8025040575:AAFA5cw3YpjrnsdU58k9_wB9MNwLp0GJ9ds"
players = ["Fra", "Dani", "Salvo", "Dennis", "Joel", "Luca"]

ID_CANAL = -1003192950351

TOTALI_FILE = "stats_totali.json"
SETTIMANALI_FILE = "stats_settimanali.json"

def get_week_key():
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    return monday.strftime("%d/%m/%y")

# --- Caricamento Totali (invariato) ---
def load_totali():
    if os.path.exists(TOTALI_FILE):
        with open(TOTALI_FILE, "r") as f:
            data = json.load(f)
        for p in players:
            if p not in data:
                data[p] = {"win": 0, "lose": 0}
        return data
    else:
        return {p: {"win": 0, "lose": 0} for p in players}

# --- MODIFICATO: Salvataggio Totali con Git ---
def save_totali(data):
    """Salva totali e committa su Git"""
    with open(TOTALI_FILE, "w") as f:
        json.dump(data, f, indent=2)

    # Auto-sync con Git
    success = git_auto_sync(
        files=[TOTALI_FILE],
        commit_message=f"stats: aggiornamento totali {datetime.datetime.now().isoformat()}"
    )
    if not success:
        print(f"⚠️ ATTENZIONE: Salvataggio locale OK ma sync Git fallito per {TOTALI_FILE}")

# --- Caricamento Settimanali (invariato) ---
def load_settimanali():
    if os.path.exists(SETTIMANALI_FILE):
        with open(SETTIMANALI_FILE, "r") as f:
            return json.load(f)
    else:
        return {}

# --- MODIFICATO: Salvataggio Settimanali con Git ---
def save_settimanali(data):
    """Salva settimanali e committa su Git"""
    with open(SETTIMANALI_FILE, "w") as f:
        json.dump(data, f, indent=2)

    # Auto-sync con Git
    success = git_auto_sync(
        files=[SETTIMANALI_FILE],
        commit_message=f"stats: aggiornamento settimanali {datetime.datetime.now().isoformat()}"
    )
    if not success:
        print(f"⚠️ ATTENZIONE: Salvataggio locale OK ma sync Git fallito per {SETTIMANALI_FILE}")

def load_stats_settimana_corrente(stats_settimanali):
    week_key = get_week_key()
    if week_key in stats_settimanali:
        week_stats = stats_settimanali[week_key]
        for p in players:
            if p not in week_stats:
                week_stats[p] = {"win": 0, "lose": 0}
        return week_stats
    else:
        empty = {p: {"win": 0, "lose": 0} for p in players}
        stats_settimanali[week_key] = empty
        save_settimanali(stats_settimanali)
        return empty

def save_stats_week(stats_settimanali, stats_corrente):
    week_key = get_week_key()
    stats_settimanali[week_key] = stats_corrente
    save_settimanali(stats_settimanali)

# --- Inizio logica ---
totali = load_totali()
settimanali = load_settimanali()
stats_week = load_stats_settimana_corrente(settimanali)

def normalize_name(name: str):
    name = name.strip()
    for p in players:
        if p.lower() == name.lower():
            return p
    return None

def parse_args(text: str):
    parts = text.split()
    if len(parts) < 2:
        return None, 1
    name = normalize_name(parts[1])
    qty = 1
    if len(parts) >= 3 and re.fullmatch(r"\d+", parts[2]):
        qty = int(parts[2])
    return name, max(1, qty)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "Comandi disponibili:\n"
        "/win <nome> [qta] - aggiungi una o più vittorie\n"
        "/lose <nome> [qta] - aggiungi una o più sconfitte\n"
        "/totali - mostra i totali attuali\n"
        "/nomi - mostra la lista giocatori\n"
        "/reset <password> - azzera settimana (password richiesta)\n"
        "/help - mostra questo messaggio"
    )
    await update.message.reply_text(msg)

async def cmd_win(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Questo comando funziona solo sui messaggi testuali.")
        return
    name, qty = parse_args(update.message.text)
    if not name:
        await update.message.reply_text("Uso: /win <nome> [qta]\nEsempio: /win Fra 2")
        return
    totali[name]["win"] += qty
    stats_week[name]["win"] += qty
    save_totali(totali)
    save_stats_week(settimanali, stats_week)
    await update.message.reply_text(f"Vittorie {name}: questa settimana {stats_week[name]['win']} (+{qty}), totali {totali[name]['win']}")

async def cmd_lose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Questo comando funziona solo sui messaggi testuali.")
        return
    name, qty = parse_args(update.message.text)
    if not name:
        await update.message.reply_text("Uso: /lose <nome> [qta]\nEsempio: /lose Joel")
        return
    totali[name]["lose"] += qty
    stats_week[name]["lose"] += qty
    save_totali(totali)
    save_stats_week(settimanali, stats_week)
    await update.message.reply_text(f"Sconfitte {name}: questa settimana {stats_week[name]['lose']} (+{qty}), totali {totali[name]['lose']}")

async def cmd_totali(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        await update.effective_chat.send_message("Comando non gestito su questa tipologia di messaggio.")
        return
    lines = []
    for p in players:
        w_tot = totali[p]["win"]
        l_tot = totali[p]["lose"]
        w_sett = stats_week[p]["win"]
        l_sett = stats_week[p]["lose"]
        lines.append(f"{p}: TOT - {w_tot} vittorie, {l_tot} sconfitte | Settimana - {w_sett} vittorie, {l_sett} sconfitte")
    await update.message.reply_text("\n".join(lines))

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Comando non gestito su questa tipologia di messaggio.")
        return
    parts = update.message.text.split()
    if len(parts) < 2 or parts[1] != "ciao":
        await update.message.reply_text("Password errata! Per resettare serve /reset ciao")
        return
    week_key = get_week_key()
    settimanali[week_key] = stats_week.copy()
    save_settimanali(settimanali)
    stats_week.clear()
    for p in players:
        stats_week[p] = {"win": 0, "lose": 0}
    save_stats_week(settimanali, stats_week)
    await update.message.reply_text("Contatori settimanali azzerati.")

async def cmd_nomi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        await update.effective_chat.send_message("Comando non gestito su questa tipologia di messaggio.")
        return
    elenco = "\n".join(players)
    await update.message.reply_text(f"Giocatori:\n{elenco}")

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        await update.effective_chat.send_message("Comando non gestito su questa tipologia di messaggio.")
        return
    try:
        await send_and_pin_week_report(context)
        await update.message.reply_text("Report inviato e fissato nel canale!")
    except Exception as e:
        await update.message.reply_text(f"Errore nell'invio: {e}")

async def send_and_pin_week_report(context: ContextTypes.DEFAULT_TYPE):
    print(f"[JOB] Invio report automatico alle {datetime.datetime.now()}")
    lines = []
    for p in players:
        w_sett = stats_week[p]["win"]
        l_sett = stats_week[p]["lose"]
        lines.append(f"{p}: {w_sett} vittorie, {l_sett} sconfitte")
    report = "Statistiche settimanali:\n" + "\n".join(lines)
    try:
        msg = await context.bot.send_message(chat_id=ID_CANAL, text=report)
        await context.bot.pin_chat_message(chat_id=ID_CANAL, message_id=msg.message_id, disable_notification=True)
        print("Messaggio fissato con successo!")
    except Exception as e:
        print(f"ERRORE nell'invio o pin: {e}")

async def error_handler(update, context):
    msg = "Si è verificato un errore imprevisto."
    chat_id = (update.effective_chat.id if update and update.effective_chat else None)
    if chat_id:
        await context.bot.send_message(chat_id=chat_id, text=msg)
    print(f"Errore: {context.error}")

def main():
    print("Avvio bot...")
    tz_italia = ZoneInfo("Europe/Rome")
    defaults = Defaults(tzinfo=tz_italia)

    print("Build Application...")
    app = ApplicationBuilder().token(BOT_TOKEN).defaults(defaults).build()

    print("Aggancio handlers...")
    app.add_handler(CommandHandler("win", cmd_win))
    app.add_handler(CommandHandler("lose", cmd_lose))
    app.add_handler(CommandHandler("totali", cmd_totali))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("nomi", cmd_nomi))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("report", cmd_report))

    print("Registro error handler...")
    app.add_error_handler(error_handler)

    print("Avvio polling... (il bot ora è pronto!)")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(app.run_polling())

if __name__ == "__main__":
    main()
