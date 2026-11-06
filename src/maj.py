# -*- coding: utf-8 -*-
"""Mise à jour du programme depuis GitHub, sans tout réinstaller.

Les versions publiées sont les étiquettes vX.Y du dépôt public (publier.sh). L'application demande la dernière
(derniere_version : un seul appel à GitHub, quand on clique, rien n'est envoyé), puis lance ce module à part :

    .venv/bin/python -I -X utf8 src/maj.py --appliquer 1.4 --attendre <pid de l'application>

Il attend que l'application soit fermée (sous Windows, un programme ouvert garde ses fichiers), télécharge
l'archive de la version, met l'ancien programme de côté dans .ancien-programme/, pose le nouveau, réinstalle les
bibliothèques seulement si requirements.txt a changé, vérifie que le nouveau programme se charge, sinon remet
l'ancien, puis rouvre Bridge Coach. Le dossier .venv/ et les fichiers de l'utilisateur (ailleurs) ne sont jamais
touchés. Un dossier qui est un dépôt Git ne se met pas à jour ici : c'est git pull.

Seulement la bibliothèque standard : ce module doit marcher même si le reste a changé.
"""
import io, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.request, zipfile

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPOT = "wfisk/bridge-coach"
GARDER = {".venv", ".git", ".claude", ".ancien-programme"}   # jamais remplacés
JOURNAL = "derniere-mise-a-jour.txt"


def version_locale(racine=RACINE):
    try:
        return open(os.path.join(racine, "VERSION"), encoding="utf-8").read().strip()
    except OSError:
        return "0"


def cle(v):
    """« 1.10 » après « 1.9 » : les nombres, pas les lettres."""
    return tuple(int(x) for x in re.findall(r"\d+", v)) or (0,)


def plus_recente(etiquettes):
    """La plus haute des étiquettes « vX.Y », sans le v ; None s'il n'y en a pas."""
    vs = [e[1:] for e in etiquettes if re.fullmatch(r"v\d+(\.\d+)*", e)]
    return max(vs, key=cle) if vs else None


def lire(url, delai=20):
    r = urllib.request.Request(url, headers={"User-Agent": "Bridge-Coach"})
    with urllib.request.urlopen(r, timeout=delai) as f:
        return f.read()


def derniere_version():
    """La dernière version publiée sur GitHub, ou None. Lève OSError sans connexion."""
    return plus_recente([t["name"] for t in json.loads(lire(f"https://api.github.com/repos/{DEPOT}/tags?per_page=100"))])


def est_depot_git(racine=RACINE):
    return os.path.isdir(os.path.join(racine, ".git"))


def attendre(pid, delai=120):
    """Attend la fin du processus pid (l'application), au plus delai secondes."""
    fin = time.time() + delai
    while time.time() < fin:
        if os.name == "nt":
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)   # SYNCHRONIZE
            if not h: return
            r = ctypes.windll.kernel32.WaitForSingleObject(h, 1000); ctypes.windll.kernel32.CloseHandle(h)
            if r == 0: return
        else:
            try: os.kill(pid, 0)
            except OSError: return
            time.sleep(0.5)


def poser(archive, racine=RACINE, python=None, journal=print):
    """Remplace le programme de racine par celui de l'archive .zip (octets). Renvoie True si tout va bien ; sinon
    l'ancien programme est remis en place."""
    python = python or (os.path.join(racine, ".venv", "Scripts", "python.exe") if os.name == "nt"
                        else os.path.join(racine, ".venv", "bin", "python"))
    neuf = tempfile.mkdtemp(prefix="bridge-coach-maj-")
    with zipfile.ZipFile(io.BytesIO(archive)) as z: z.extractall(neuf)
    hauts = os.listdir(neuf)
    source = os.path.join(neuf, hauts[0]) if len(hauts) == 1 and os.path.isdir(os.path.join(neuf, hauts[0])) else neuf
    if not os.path.isdir(os.path.join(source, "src")): raise ValueError("l'archive ne contient pas le programme")
    ancien = os.path.join(racine, ".ancien-programme")
    shutil.rmtree(ancien, ignore_errors=True); os.makedirs(ancien)
    exig = lambda d: open(os.path.join(d, "requirements.txt"), encoding="utf-8").read() if os.path.exists(os.path.join(d, "requirements.txt")) else ""
    libs_avant = exig(racine); libs_changees = False
    for x in os.listdir(racine):                         # l'ancien programme de côté
        if x not in GARDER: shutil.move(os.path.join(racine, x), os.path.join(ancien, x))
    try:
        for x in os.listdir(source):
            if x not in GARDER: shutil.move(os.path.join(source, x), os.path.join(racine, x))
        if exig(racine) != libs_avant:
            journal("Bibliothèques : installation des versions nouvelles…"); libs_changees = True
            subprocess.run([python, "-m", "pip", "install", "-q", "-r", os.path.join(racine, "requirements.txt")], check=True)
        subprocess.run([python, "-I", "-X", "utf8", "-c", "import sys; sys.path.insert(0, 'src'); import rapport, donnes, edition"],
                       cwd=racine, check=True, capture_output=True)
    except Exception as ex:
        journal(f"Échec ({type(ex).__name__} : {ex}) : l'ancien programme est remis en place.")
        for x in os.listdir(racine):
            if x in GARDER: continue
            c = os.path.join(racine, x)
            shutil.rmtree(c, ignore_errors=True) if os.path.isdir(c) else os.remove(c)
        for x in os.listdir(ancien): shutil.move(os.path.join(ancien, x), os.path.join(racine, x))
        if libs_changees:                                 # les bibliothèques d'avant
            subprocess.run([python, "-m", "pip", "install", "-q", "-r", os.path.join(racine, "requirements.txt")])
        return False
    finally:
        shutil.rmtree(neuf, ignore_errors=True)
    shutil.rmtree(ancien, ignore_errors=True)
    return True


def rouvrir(racine=RACINE):
    """Rouvre Bridge Coach comme le fait son raccourci."""
    if os.name == "nt":
        subprocess.Popen(["cmd", "/c", "start", "", "/min", os.path.join(racine, "bridge-coach.bat")],
                         creationflags=0x00000008 | 0x00000200)   # DETACHED_PROCESS, NEW_PROCESS_GROUP
    elif sys.platform == "darwin" and os.path.isdir("/Applications/Bridge Coach.app"):
        for _ in range(20):                              # la petite application se ferme d'elle-même avec le programme
            if subprocess.run(["pgrep", "-f", "Bridge Coach.app"], capture_output=True).returncode: break
            time.sleep(0.5)
        subprocess.Popen(["open", "-a", "Bridge Coach"])
    else:
        subprocess.Popen([os.path.join(racine, "bridge-coach.sh")], start_new_session=True)


def main():
    args = sys.argv[1:]
    version = args[args.index("--appliquer") + 1]
    pid = int(args[args.index("--attendre") + 1]) if "--attendre" in args else None
    dossier = args[args.index("--journal") + 1] if "--journal" in args else tempfile.gettempdir()
    lignes = []
    journal = lambda t: (lignes.append(t), print(t, flush=True))
    try:
        if pid: attendre(pid)
        time.sleep(1)                                     # les derniers fichiers se ferment
        journal(f"Mise à jour de {version_locale()} vers {version}")
        ok = poser(lire(f"https://github.com/{DEPOT}/archive/refs/tags/v{version}.zip", 120), journal=journal)
        journal("Terminé." if ok else "Rien n'a changé.")
    except Exception as ex:
        journal(f"Échec : {type(ex).__name__} : {ex}. Le programme n'a pas changé.")
    try:
        os.makedirs(dossier, exist_ok=True)
        with open(os.path.join(dossier, JOURNAL), "w", encoding="utf-8") as f: f.write("\n".join(lignes) + "\n")
    except OSError:
        pass
    if "--sans-rouvrir" not in args: rouvrir()


if __name__ == "__main__":
    main()
