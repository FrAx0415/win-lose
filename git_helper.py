import subprocess
import sys
from typing import Optional

class GitSyncError(Exception):
    """Eccezione personalizzata per errori Git"""
    pass

def run_git_command(command: list[str], cwd: str = ".") -> tuple[bool, str]:
    """
    Esegue comando Git e restituisce (success, output/error).

    Args:
        command: Lista di argomenti comando (es. ['git', 'pull', '--rebase'])
        cwd: Directory di lavoro

    Returns:
        (True, output) se successo, (False, stderr) se errore
    """
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout: operazione Git durata oltre 30 secondi"
    except Exception as e:
        return False, str(e)

def git_sync_and_commit(files: list[str], commit_message: str) -> bool:
    """
    Workflow semplificato: commit locale → pull → push.
    Evita problemi di rebase con modifiche non committate.
    """
    print(f"[GIT] Sync automatico per {len(files)} file...")

    # STEP 1: Committa le modifiche locali subito
    for f in files:
        success, output = run_git_command(["git", "add", f])
        if not success:
            print(f"[GIT] ⚠️ Add fallito per {f}: {output}")
            return False

    success, output = run_git_command(["git", "commit", "-m", commit_message])
    if not success:
        if "nothing to commit" in output.lower():
            print("[GIT] ℹ️ Nessuna modifica da committare")
            # Continua comunque con pull per allinearsi
        else:
            print(f"[GIT] ❌ Commit fallito: {output}")
            return False

    # STEP 2: Pull con merge (NON rebase) per semplicità
    success, output = run_git_command(["git", "pull", "--no-rebase"])
    if not success:
        if "already up to date" in output.lower():
            print("[GIT] ℹ️ Già aggiornato con remoto")
        else:
            print(f"[GIT] ⚠️ Pull fallito: {output}")
            # Non blocchiamo, proviamo comunque a pushare

    # STEP 3: Push
    success, output = run_git_command(["git", "push"])
    if not success:
        print(f"[GIT] ❌ Push fallito: {output}")
        return False

    print("[GIT] ✅ Sync completato")
    return True


def git_commit_and_push(files: list[str], message: str) -> bool:
    """
    Commit e push dei file specificati.

    Args:
        files: Lista di path file da committare
        message: Messaggio di commit

    Returns:
        True se commit+push riusciti, False altrimenti
    """
    print(f"[GIT] Commit e push di {len(files)} file...")

    # Add dei file
    for f in files:
        success, output = run_git_command(["git", "add", f])
        if not success:
            print(f"[GIT] ⚠️ Add fallito per {f}: {output}")
            return False

    # Commit (potrebbe non esserci nulla da committare)
    success, output = run_git_command(["git", "commit", "-m", message])
    if not success:
        if "nothing to commit" in output.lower():
            print("[GIT] ℹ️ Nessuna modifica da committare")
            return True
        print(f"[GIT] ❌ Commit fallito: {output}")
        return False

    # Push
    success, output = run_git_command(["git", "push", "origin", "main"])
    if not success:
        print(f"[GIT] ❌ Push fallito: {output}")
        return False

    print("[GIT] ✅ Commit e push completati")
    return True

def git_auto_sync(files: list[str], commit_message: str) -> bool:
    """Alias per compatibilità con il codice esistente"""
    return git_sync_and_commit(files, commit_message)
