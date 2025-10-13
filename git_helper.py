import subprocess
import sys
from typing import Optional
import asyncio
import concurrent.futures

class GitSyncError(Exception):
    """Eccezione personalizzata per errori Git"""
    pass

def run_git_command(command: list[str], cwd: str = ".") -> tuple[bool, str]:
    """
    Esegue comando Git e restituisce (success, output/error).
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
    Workflow con gestione pre-commit hook auto-fix.
    Eseguito in background thread per non bloccare bot.
    """
    print(f"[GIT] Sync automatico per {len(files)} file...")

    max_attempts = 2

    for attempt in range(max_attempts):
        # Add file
        for f in files:
            success, _ = run_git_command(["git", "add", f])
            if not success:
                print(f"[GIT] ⚠️ Add fallito per {f}")
                return False

        # Tentativo commit
        success, output = run_git_command(["git", "commit", "-m", commit_message])

        if success:
            break

        if "files were modified by this hook" in output:
            if attempt < max_attempts - 1:
                print(f"[GIT] ℹ️ Hook ha modificato file, tentativo {attempt + 2}/{max_attempts}...")
                continue
            else:
                print("[GIT] ❌ Troppi tentativi, hook continua a modificare file")
                return False

        if "nothing to commit" in output.lower():
            print("[GIT] ℹ️ Nessuna modifica da committare")
            break

        print(f"[GIT] ❌ Commit fallito: {output}")
        return False

    # Pull
    success, output = run_git_command(["git", "pull", "--no-rebase"])
    if not success and "already up to date" not in output.lower():
        print(f"[GIT] ⚠️ Pull fallito: {output}")

    # Push
    success, output = run_git_command(["git", "push"])
    if not success:
        print(f"[GIT] ❌ Push fallito: {output}")
        return False

    print("[GIT] ✅ Sync completato")
    return True

async def git_auto_sync_async(files: list[str], commit_message: str) -> bool:
    """
    Esegue git sync in un thread separato per non bloccare il bot.
    Ritorna immediatamente, commit avviene in background.
    """
    loop = asyncio.get_running_loop()

    # Esegui git_sync_and_commit in un executor thread
    with concurrent.futures.ThreadPoolExecutor() as pool:
        try:
            # run_in_executor esegue funzione sincrona in thread separato
            result = await loop.run_in_executor(
                pool,
                git_sync_and_commit,
                files,
                commit_message
            )
            return result
        except Exception as e:
            print(f"[GIT] ❌ Errore async: {e}")
            return False


def git_auto_sync(files: list[str], commit_message: str) -> bool:
    """Versione sincrona (deprecata, usa git_auto_sync_async)"""
    return git_sync_and_commit(files, commit_message)
