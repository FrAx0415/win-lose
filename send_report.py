import os
import json
from telegram import Bot
import requests
from datetime import date, timedelta

BOT_TOKEN = os.environ["BOT_TOKEN"]
ID_CANAL = int(os.environ["ID_CANAL"])

TOTALI_FILE = "stats_totali.json"
SETTIMANALI_FILE = "stats_settimanali.json"
players = ["Fra", "Dani", "Salvo", "Dennis", "Joel", "Luca"]

def get_week_key():
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%d/%m/%y")

def load_settimanali():
    with open(SETTIMANALI_FILE, "r") as f:
        return json.load(f)

# Carica stats settimanali
stats_settimanali = load_settimanali()
week_key = get_week_key()
stats_week = stats_settimanali.get(week_key, {p: {"win": 0, "lose": 0} for p in players})

lines = []
for p in players:
    w_sett = stats_week.get(p, {"win": 0, "lose": 0})["win"]
    l_sett = stats_week.get(p, {"win": 0, "lose": 0})["lose"]
    lines.append(f"{p}: {w_sett} vittorie, {l_sett} sconfitte")
report = "Statistiche settimanali:\n" + "\n".join(lines)

print(f"[DEBUG] Invio report su Telegram...\n{report}")
bot = Bot(BOT_TOKEN)
msg = bot.send_message(chat_id=ID_CANAL, text=report)
print("[DEBUG] Report Telegram inviato!")

# PIN message via Telegram Bot API
def pin_message(token, chat_id, message_id):
    print(f"[DEBUG] Pinning message_id {message_id} in chat {chat_id}")
    r = requests.post(
        f"https://api.telegram.org/bot{token}/pinChatMessage",
        data={
            "chat_id": chat_id,
            "message_id": message_id,
            "disable_notification": True
        }
    )
    if r.status_code == 200:
        print("[DEBUG] Messaggio fissato con successo!")
    else:
        print(f"[ERROR] Pin fallito: {r.text}")

pin_message(BOT_TOKEN, ID_CANAL, msg.message_id)
