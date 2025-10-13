import os
import json
from datetime import date, timedelta
import matplotlib.pyplot as plt
import requests
import asyncio
from telegram import Bot

BOT_TOKEN = os.environ["BOT_TOKEN"]
ID_CANAL = int(os.environ["ID_CANAL"])
TOTALI_FILE = "stats_totali.json"
SETTIMANALI_FILE = "stats_settimanali.json"

def load_totali():
    with open(TOTALI_FILE, "r") as f:
        return json.load(f)

def load_settimanali():
    with open(SETTIMANALI_FILE, "r") as f:
        return json.load(f)

def get_week_key():
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%d/%m/%y")

def load_stats_week(stats_settimanali, players):
    week_key = get_week_key()
    stats_week = stats_settimanali.get(week_key, {})
    # Assicura che ogni player abbia la chiave win/lose (se manca)
    for p in players:
        if p not in stats_week:
            stats_week[p] = {"win": 0, "lose": 0}
    return stats_week, week_key

def build_weekly_report(stats_week, week_key, players):
    week_wins = [stats_week[p]["win"] for p in players]
    week_labels = []
    colors = []
    sorted_idx = sorted(range(len(players)), key=lambda i: week_wins[i], reverse=True)
    top_idxs = sorted_idx[:3]

    for i, p in enumerate(players):
        if i == top_idxs[0] and week_wins[top_idxs[0]] > 0:
            week_labels.append(f"🥇{p}")
            colors.append("#ffd700")
        elif i == top_idxs[1] and week_wins[top_idxs[1]] > 0:
            week_labels.append(f"🥈{p}")
            colors.append("#c0c0c0")
        elif i == top_idxs[2] and week_wins[top_idxs[2]] > 0:
            week_labels.append(f"🥉{p}")
            colors.append("#cd7f32")
        else:
            week_labels.append(p)
            colors.append("#2196f3")

    # --- PNG ---
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.barh(week_labels, week_wins, color=colors, height=0.6)
    ax.set_title(f"Vittorie nella settimana {week_key}\n", fontsize=16, fontweight='bold')
    ax.set_xlabel("Numero vittorie", fontsize=13)
    ax.set_xlim(left=0)
    ax.bar_label(bars, fmt='%d', label_type='edge', fontsize=13)
    ax.grid(True, alpha=0.12, axis='x')
    plt.tight_layout()
    img_path = f"report_week_{week_key.replace('/','-')}.png"
    fig.savefig(img_path, dpi=210, bbox_inches='tight')
    plt.close(fig)

    # --- Testo classifica ---
    report = (
        "📊 *REPORT SETTIMANALE* ⚽️\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 Settimana: *{week_key}*\n\n"
    )
    ordered = [players[i] for i in sorted_idx]
    for idx, p in enumerate(ordered, 1):
        w_sett = stats_week[p]["win"]
        l_sett = stats_week[p]["lose"]
        rank = ""
        if idx == 1 and w_sett > 0:
            rank = "👑"
        elif idx == 2:
            rank = "🥈"
        elif idx == 3:
            rank = "🥉"
        else:
            rank = f"{idx}."
        week_games = w_sett + l_sett
        week_rate = (w_sett / week_games * 100) if week_games > 0 else 0
        if week_games == 0:
            performance = "⚪️ _Non ha giocato_"
        elif week_rate >= 70:
            performance = "🔥 _In forma!_"
        elif week_rate >= 50:
            performance = "✅ _Buona settimana_"
        else:
            performance = "📉 _Può fare meglio_"
        report += (
            f"{rank} *{p}*\n"
            f"   🏆 {w_sett}W - ❌ {l_sett}L ({week_rate:.0f}%)\n"
            f"   {performance}\n\n"
        )
    report += (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎮 _Stats by Calcetto Bot_"
    )
    return report, img_path

async def main():
    totali = load_totali()
    # Prendi i player in modo DINAMICO dal file, in ordine di inserimento
    players = list(totali.keys())
    stats_settimanali = load_settimanali()
    stats_week, week_key = load_stats_week(stats_settimanali, players)
    report, img_path = build_weekly_report(stats_week, week_key, players)

    print(f"[DEBUG] Invio report PNG su Telegram...")
    bot = Bot(BOT_TOKEN)
    with open(img_path, "rb") as photo:
        msg = await bot.send_photo(chat_id=ID_CANAL, photo=photo, caption=report, parse_mode="Markdown")
    print("[DEBUG] Report PNG Telegram inviato!")
    if os.path.exists(img_path):
        os.remove(img_path)
    # PIN message via Telegram Bot API HTTP (sync: requests)
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

if __name__ == "__main__":
    asyncio.run(main())
