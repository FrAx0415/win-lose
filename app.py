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
import matplotlib.pyplot as plt

from dotenv import load_dotenv
load_dotenv()

from git_helper import git_auto_sync_async

nest_asyncio.apply()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ID_CANAL = int(os.getenv("CHANNEL_ID"))
RESET_PASSWORD = os.getenv("RESET_PASSWORD", "ciao")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN non trovato nel file .env!")

players = ["Fra", "Dani", "Salvo", "Dennis", "Joel", "Luca"]

TOTALI_FILE = "stats_totali.json"
SETTIMANALI_FILE = "stats_settimanali.json"


def get_week_key():
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    return monday.strftime("%d/%m/%y")


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


def save_totali(data):
    """Salva totali (solo file locale, commit in background)"""
    with open(TOTALI_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_settimanali():
    if os.path.exists(SETTIMANALI_FILE):
        with open(SETTIMANALI_FILE, "r") as f:
            return json.load(f)
    else:
        return {}


def save_settimanali(data):
    """Salva settimanali (solo file locale, commit in background)"""
    with open(SETTIMANALI_FILE, "w") as f:
        json.dump(data, f, indent=2)


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


def add_player_to_file(name: str) -> bool:
    """
    Aggiunge un nuovo giocatore ai file di stats.
    Ritorna True se successo, False se già esistente.
    """
    global players, totali, stats_week

    # Normalizza nome (prima lettera maiuscola)
    name = name.strip().capitalize()

    # Controlla se esiste già
    if name in players:
        return False

    # Aggiungi alla lista
    players.append(name)

    # Aggiungi a totali
    totali[name] = {"win": 0, "lose": 0}
    save_totali(totali)

    # Aggiungi a stats settimana corrente
    stats_week[name] = {"win": 0, "lose": 0}
    save_stats_week(settimanali, stats_week)

    return True


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🎮 *CALCETTO STATS BOT* ⚽️\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📊 *Comandi Disponibili:*\n\n"
        "🏆 `/win <nome> [quantità]`\n"
        "   _Aggiungi vittoria/e_\n"
        "   _Es: /win Fra 2_\n\n"
        "❌ `/lose <nome> [quantità]`\n"
        "   _Aggiungi sconfitta/e_\n"
        "   _Es: /lose Joel_\n\n"
        "➕ `/add <nome>`\n"
        "   _Aggiungi nuovo giocatore_\n"
        "   _Es: /add Marco_\n\n"
        "📈 `/totali`\n"
        "   _Visualizza statistiche complete_\n\n"
        "👥 `/nomi`\n"
        "   _Lista giocatori registrati_\n\n"
        "📋 `/report`\n"
        "   _Genera report settimanale_\n\n"
        "🔄 `/reset <password>`\n"
        "   _Azzera contatori settimanali_\n\n"
        "📊 `/storico <nome>`\n"
        "   _Mostra trend vittorie settimanali con grafico PNG_\n"
        "   _Es: /storico Fra_\n\n"

        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_add_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_chat.send_message(
            "⚠️ Questo comando funziona solo con messaggi testuali.",
            parse_mode="Markdown"
        )
        return

    parts = update.message.text.split()
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ *Formato non valido*\n\n"
            "📝 Uso corretto:\n"
            "`/add <nome_giocatore>`\n\n"
            "💡 Esempio:\n"
            "• `/add Marco`",
            parse_mode="Markdown"
        )
        return

    player_name = parts[1].strip().capitalize()

    # Valida nome (solo lettere)
    if not player_name.isalpha():
        await update.message.reply_text(
            "❌ *Nome non valido*\n\n"
            "⚠️ Il nome deve contenere solo lettere\n\n"
            "💡 Riprova con un nome valido",
            parse_mode="Markdown"
        )
        return

    # Tenta aggiunta
    success = add_player_to_file(player_name)

    if not success:
        await update.message.reply_text(
            f"⚠️ *Giocatore già esistente*\n\n"
            f"👤 *{player_name}* è già registrato\n\n"
            f"📋 Usa `/nomi` per vedere tutti i giocatori",
            parse_mode="Markdown"
        )
        return

    # RISPOSTA IMMEDIATA all'utente
    await update.message.reply_text(
        f"✅ *Giocatore Aggiunto!*\n\n"
        f"👤 Nome: *{player_name}*\n"
        f"📊 Stats inizializzate a 0\n\n"
        f"🎮 Totale giocatori: *{len(players)}*\n\n"
        f"💡 Puoi iniziare a tracciare le sue\n"
        f"   partite con `/win {player_name}`",
        parse_mode="Markdown"
    )

    # Commit Git in BACKGROUND (non blocca)
    asyncio.create_task(
        git_auto_sync_async(
            files=[TOTALI_FILE, SETTIMANALI_FILE],
            commit_message=f"player: aggiunto {player_name}"
        )
    )


async def cmd_win(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_chat.send_message(
            "⚠️ Questo comando funziona solo con messaggi testuali.",
            parse_mode="Markdown"
        )
        return

    name, qty = parse_args(update.message.text)
    if not name:
        await update.message.reply_text(
            "❌ *Formato non valido*\n\n"
            "📝 Uso corretto:\n"
            "`/win <nome> [quantità]`\n\n"
            "💡 Esempi:\n"
            "• `/win Fra`\n"
            "• `/win Dani 3`",
            parse_mode="Markdown"
        )
        return

    # Aggiorna stats PRIMA della risposta
    totali[name]["win"] += qty
    stats_week[name]["win"] += qty

    # Salva localmente (veloce, no commit)
    save_totali(totali)
    save_stats_week(settimanali, stats_week)

    # RISPOSTA IMMEDIATA all'utente
    emoji = "🎉" if qty > 1 else "✅"
    msg = (
        f"{emoji} *Vittoria registrata!*\n\n"
        f"👤 Giocatore: *{name}*\n"
        f"➕ Aggiunte: *+{qty}*\n\n"
        f"📊 *Statistiche Aggiornate:*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📅 Questa settimana: *{stats_week[name]['win']}* 🏆\n"
        f"🏅 Totale carriera: *{totali[name]['win']}* 🏆"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

    # Commit Git in BACKGROUND (non blocca)
    asyncio.create_task(
        git_auto_sync_async(
            files=[TOTALI_FILE, SETTIMANALI_FILE],
            commit_message=f"win: {name} +{qty}"
        )
    )


async def cmd_lose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_chat.send_message(
            "⚠️ Questo comando funziona solo con messaggi testuali.",
            parse_mode="Markdown"
        )
        return

    name, qty = parse_args(update.message.text)
    if not name:
        await update.message.reply_text(
            "❌ *Formato non valido*\n\n"
            "📝 Uso corretto:\n"
            "`/lose <nome> [quantità]`\n\n"
            "💡 Esempi:\n"
            "• `/lose Joel`\n"
            "• `/lose Salvo 2`",
            parse_mode="Markdown"
        )
        return

    # Aggiorna stats
    totali[name]["lose"] += qty
    stats_week[name]["lose"] += qty

    # Salva localmente
    save_totali(totali)
    save_stats_week(settimanali, stats_week)

    # RISPOSTA IMMEDIATA
    emoji = "💔" if qty > 1 else "📉"
    msg = (
        f"{emoji} *Sconfitta registrata*\n\n"
        f"👤 Giocatore: *{name}*\n"
        f"➖ Aggiunte: *+{qty}*\n\n"
        f"📊 *Statistiche Aggiornate:*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📅 Questa settimana: *{stats_week[name]['lose']}* ❌\n"
        f"📊 Totale carriera: *{totali[name]['lose']}* ❌"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

    # Commit Git in BACKGROUND
    asyncio.create_task(
        git_auto_sync_async(
            files=[TOTALI_FILE, SETTIMANALI_FILE],
            commit_message=f"lose: {name} +{qty}"
        )
    )


async def cmd_totali(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        await update.effective_chat.send_message(
            "⚠️ Comando non disponibile per questo tipo di messaggio.",
            parse_mode="Markdown"
        )
        return

    msg = (
        "🏆 *CLASSIFICA GENERALE* ⚽️\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    sorted_players = sorted(
        players,
        key=lambda p: totali[p]["win"],
        reverse=True
    )

    for idx, p in enumerate(sorted_players, 1):
        w_tot = totali[p]["win"]
        l_tot = totali[p]["lose"]
        w_sett = stats_week[p]["win"]
        l_sett = stats_week[p]["lose"]

        if idx == 1:
            rank = "🥇"
        elif idx == 2:
            rank = "🥈"
        elif idx == 3:
            rank = "🥉"
        else:
            rank = f"{idx}."

        total_games = w_tot + l_tot
        win_rate = (w_tot / total_games * 100) if total_games > 0 else 0

        msg += (
            f"{rank} *{p}*\n"
            f"   🏅 Totali: {w_tot}W - {l_tot}L ({win_rate:.0f}%)\n"
            f"   📅 Settimana: {w_sett}W - {l_sett}L\n\n"
        )

    msg += (
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📆 Settimana: *{get_week_key()}*"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        await update.effective_chat.send_message(
            "⚠️ Comando non disponibile per questo tipo di messaggio.",
            parse_mode="Markdown"
        )
        return

    parts = update.message.text.split()
    if len(parts) < 2 or parts[1] != RESET_PASSWORD:
        await update.message.reply_text(
            "🔒 *Accesso Negato*\n\n"
            "❌ Password non corretta\n\n"
            "💡 Uso: `/reset <password>`",
            parse_mode="Markdown"
        )
        return

    week_key = get_week_key()
    settimanali[week_key] = stats_week.copy()
    save_settimanali(settimanali)
    stats_week.clear()
    for p in players:
        stats_week[p] = {"win": 0, "lose": 0}
    save_stats_week(settimanali, stats_week)

    await update.message.reply_text(
        "🔄 *Reset Completato!*\n\n"
        "✅ Contatori settimanali azzerati\n"
        f"📅 Settimana corrente: *{get_week_key()}*\n\n"
        "🎮 Buona fortuna per la nuova settimana!",
        parse_mode="Markdown"
    )

    # Commit Git in BACKGROUND
    asyncio.create_task(
        git_auto_sync_async(
            files=[SETTIMANALI_FILE],
            commit_message=f"reset: settimana {week_key}"
        )
    )


async def cmd_nomi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        await update.effective_chat.send_message(
            "⚠️ Comando non disponibile per questo tipo di messaggio.",
            parse_mode="Markdown"
        )
        return

    msg = (
        "👥 *GIOCATORI REGISTRATI* ⚽️\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    for idx, p in enumerate(players, 1):
        msg += f"{idx}. 👤 *{p}*\n"

    msg += (
        "\n━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Totale: *{len(players)}* giocatori"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        await update.effective_chat.send_message(
            "⚠️ Comando non disponibile per questo tipo di messaggio.",
            parse_mode="Markdown"
        )
        return

    try:
        await send_and_pin_week_report(context)
        await update.message.reply_text(
            "✅ *Report Generato!*\n\n"
            "📌 Il report settimanale è stato pubblicato\n"
            "   e fissato nel canale\n\n"
            "🎯 Controlla il messaggio pinnato!",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(
            "❌ *Errore durante l'invio*\n\n"
            f"⚠️ Dettaglio: `{str(e)}`\n\n"
            "🔧 Contatta l'amministratore",
            parse_mode="Markdown"
        )

async def cmd_storico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import matplotlib.pyplot as plt

    text = update.message.text
    parts = text.split()
    if len(parts) != 2:
        await update.message.reply_text(
            "❌ *Formato non valido.*\n\n"
            "📝 Uso corretto:\n"
            "`/storico <nome>`\n"
            "Esempio: `/storico Fra`",
            parse_mode="Markdown"
        )
        return

    player = normalize_name(parts[1])
    if not player:
        await update.message.reply_text("❌ *Giocatore non trovato.*", parse_mode="Markdown")
        return

    labels = []
    win_rates = []
    wins_data = []
    losses_data = []

    for week, week_stats in settimanali.items():
        wins = week_stats.get(player, {}).get('win', 0)
        losses = week_stats.get(player, {}).get('lose', 0)
        total_games = wins + losses
        win_rate = (wins / total_games * 100) if total_games > 0 else 0
        labels.append(week)  # formato date chiave tipo 13/10/25
        win_rates.append(win_rate)
        wins_data.append(wins)
        losses_data.append(losses)

    if not any(wins_data) and not any(losses_data):
        await update.message.reply_text(
            f"ℹ️ Nessuna partita registrata per *{player}*.",
            parse_mode="Markdown"
        )
        return

    # Trova la data della miglior/peggiore settimana
    best_week_idx = win_rates.index(max(win_rates)) if win_rates else None
    best_week_date = labels[best_week_idx] if best_week_idx is not None else "-"
    worst_week_idx = win_rates.index(min([r for r in win_rates if r > 0])) if any(win_rates) else None
    worst_week_date = labels[worst_week_idx] if worst_week_idx is not None else "-"

    # Converte data da "13/10/25" a "13/10/2025" (facoltativo)
    def convert_date(date_str):
        parts = date_str.split('/')
        if len(parts[-1]) == 2:
            # Es: "13/10/25" -> "13/10/2025"
            parts[-1] = "20" + parts[-1]
        return "/".join(parts)

    best_week_date = convert_date(best_week_date)
    worst_week_date = convert_date(worst_week_date)

    # Genera grafico PNG
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

    # Grafico 1: Win Rate percentuale
    ax1.plot(labels, win_rates, marker='o', color="#4caf50", linewidth=3, markersize=6)
    ax1.set_title(f"📊 Storico Performance - {player}", fontsize=16, fontweight='bold')
    ax1.set_ylabel("Win Rate (%)", fontsize=12)
    ax1.set_ylim(0, 100)
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis='x', rotation=45, labelsize=9)
    ax1.tick_params(axis='y', labelsize=10)
    ax1.axhline(y=50, color='gray', linestyle='--', alpha=0.7, label='50% Soglia')
    ax1.legend()

    # Grafico 2: Vittorie vs Sconfitte (barre)
    width = 0.35
    x_pos = range(len(labels))
    ax2.bar([x - width/2 for x in x_pos], wins_data, width, label='Vittorie 🏆', color='#4caf50', alpha=0.8)
    ax2.bar([x + width/2 for x in x_pos], losses_data, width, label='Sconfitte ❌', color='#f44336', alpha=0.8)

    ax2.set_xlabel("Settimana", fontsize=12)
    ax2.set_ylabel("Numero Partite", fontsize=12)
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(labels, rotation=45, fontsize=9)
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')

    img_path = f"storico_{player}.png"
    plt.tight_layout()
    fig.savefig(img_path, dpi=300, bbox_inches='tight')
    plt.close(fig)

    # Statistiche globali
    total_wins = totali[player]['win']
    total_losses = totali[player]['lose']
    total_games = total_wins + total_losses
    overall_win_rate = (total_wins / total_games * 100) if total_games > 0 else 0

    # Unico messaggio con dati richiesti
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=open(img_path, 'rb'),
        caption=(
            f"📊 *Analisi Performance - {player}*\n\n"
            f"🏅 **Statistiche Totali:**\n"
            f"• Vittorie: *{total_wins}* | Sconfitte: *{total_losses}*\n"
            f"• Win Rate: *{overall_win_rate:.1f}%*\n\n"
            f"📈 **Performance Settimanali:**\n"
            f"• Miglior settimana: *{best_week_date}*\n"
            f"• Settimana più difficile: *{worst_week_date}*"
        ),
        parse_mode="Markdown"
    )
    os.remove(img_path)



async def send_and_pin_week_report(context: ContextTypes.DEFAULT_TYPE):
    import matplotlib.pyplot as plt

    print(f"[JOB] Invio report automatico alle {datetime.datetime.now()}")

    week_key = get_week_key()
    # Dati giocatori e vittorie settimana
    week_wins = [stats_week[p]["win"] for p in players]
    week_losses = [stats_week[p]["lose"] for p in players]
    week_labels = []
    colors = []

    sorted_idx = sorted(range(len(players)), key=lambda i: week_wins[i], reverse=True)
    top_idxs = sorted_idx[:3]  # top 3 per medaglie

    for i, p in enumerate(players):
        # podio: oro, argento, bronzo, altri blu
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
            colors.append("#2196f3")  # blu

    # BAR PLOT PNG
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

    # Messaggio classifica testuale
    report = (
        "📊 *REPORT SETTIMANALE* ⚽️\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 Settimana: *{week_key}*\n\n"
    )
    # Ordina per vittorie (come il bar plot)
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

    try:
        # Invia PNG + testo
        msg_grafico = await context.bot.send_photo(
            chat_id=ID_CANAL,
            photo=open(img_path, 'rb'),
            caption=report,
            parse_mode="Markdown"
        )
        await context.bot.pin_chat_message(
            chat_id=ID_CANAL,
            message_id=msg_grafico.message_id,
            disable_notification=True
        )
        os.remove(img_path)
        print("✅ Report PNG e messaggio fissati con successo!")
    except Exception as e:
        print(f"❌ ERRORE nell'invio o pin: {e}")

    import matplotlib.pyplot as plt

    print(f"[JOB] Invio report automatico alle {datetime.datetime.now()}")

    week_key = get_week_key()
    # Dati giocatori e vittorie settimana
    week_wins = [stats_week[p]["win"] for p in players]
    week_losses = [stats_week[p]["lose"] for p in players]
    week_labels = []
    colors = []

    sorted_idx = sorted(range(len(players)), key=lambda i: week_wins[i], reverse=True)
    top_idxs = sorted_idx[:3]  # top 3 per medaglie

    for i, p in enumerate(players):
        # podio: oro, argento, bronzo, altri blu
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
            colors.append("#2196f3")  # blu

    # BAR PLOT PNG
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

    # Messaggio classifica testuale
    report = (
        "📊 *REPORT SETTIMANALE* ⚽️\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📅 Settimana: *{week_key}*\n\n"
    )
    # Ordina per vittorie (come il bar plot)
    ordered = [players[i] for i in sorted_idx]
    for idx, p in enumerate(ordered, 1):
        w_sett = stats_week[p]["win"]
        l_sett = stats_week[p]["lose"]
        rank = ""
        if idx == 1 and w_sett > 0:
            rank
        try:
        # Invia PNG + testo
        with open(img_path, 'rb') as photo_file:
            msg_grafico = await context.bot.send_photo(
                chat_id=ID_CANAL,
                photo=photo_file,
                caption=report,
                parse_mode="Markdown"
            )
        os.remove(img_path)  # ELIMINA SUBITO DOPO IL SEND

        await context.bot.pin_chat_message(
            chat_id=ID_CANAL,
            message_id=msg_grafico.message_id,
            disable_notification=True
        )
        print("✅ Report PNG e messaggio fissati con successo!")
    except Exception as e:
        # Nel caso di errore di invio, prova comunque a eliminare il file
        if os.path.exists(img_path):
            os.remove(img_path)
        print(f"❌ ERRORE nell'invio o pin: {e}")


async def error_handler(update, context):
    msg = (
        "⚠️ *Ops! Qualcosa è andato storto*\n\n"
        "🔧 Si è verificato un errore imprevisto.\n"
        "Riprova tra qualche istante.\n\n"
        "💡 Se il problema persiste, contatta\n"
        "   l'amministratore del bot."
    )
    chat_id = (update.effective_chat.id if update and update.effective_chat else None)
    if chat_id:
        await context.bot.send_message(
            chat_id=chat_id,
            text=msg,
            parse_mode="Markdown"
        )
    print(f"❌ Errore: {context.error}")


def main():
    print("🚀 Avvio bot...")
    tz_italia = ZoneInfo("Europe/Rome")
    defaults = Defaults(tzinfo=tz_italia)

    print("⚙️ Build Application...")
    app = ApplicationBuilder().token(BOT_TOKEN).defaults(defaults).build()

    print("🔗 Aggancio handlers...")
    app.add_handler(CommandHandler("win", cmd_win))
    app.add_handler(CommandHandler("lose", cmd_lose))
    app.add_handler(CommandHandler("add", cmd_add_player))
    app.add_handler(CommandHandler("totali", cmd_totali))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("nomi", cmd_nomi))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("storico", cmd_storico))


    print("🛡️ Registro error handler...")
    app.add_error_handler(error_handler)

    print("✅ Bot pronto e in ascolto!\n")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(app.run_polling())


if __name__ == "__main__":
    main()
