# -*- coding: utf-8 -*-
"""La mise à jour sur une copie du programme : une bonne version se pose, une version abîmée est retirée."""
import io, os, subprocess, sys, tempfile, zipfile
ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ICI, "src"))
import maj

assert maj.plus_recente(["v1.9", "v1.10", "essai", "v1.2"]) == "1.10" and maj.plus_recente(["essai"]) is None
assert maj.cle("1.10") > maj.cle("1.9")
sommes = "ab12  bridge-coach-1.5.zip\ncd34 *Bridge-Coach.pkg\n"
assert maj.empreinte_de(sommes, "bridge-coach-1.5.zip") == "ab12" and maj.empreinte_de(sommes, "Bridge-Coach.pkg") == "cd34"
assert maj.empreinte_de(sommes, "autre.zip") is None
import hashlib
maj.verifier(b"x", hashlib.sha256(b"x").hexdigest(), "x")
try: maj.verifier(b"y", hashlib.sha256(b"x").hexdigest(), "y"); raise AssertionError("empreinte fausse acceptée")
except ValueError: pass

fichiers = subprocess.run(["git", "ls-files"], cwd=ICI, capture_output=True, text=True).stdout.split()
python = os.path.join(ICI, ".venv", "bin", "python") if os.name != "nt" else os.path.join(ICI, ".venv", "Scripts", "python.exe")


def archive(version, abimer=False):
    """Une archive comme celles de GitHub : un dossier bridge-coach-<version>/ avec le programme."""
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for f in fichiers:
            texte = open(os.path.join(ICI, f), "rb").read()
            if f == "src/rapport.py" and abimer: texte += b"\n)\n"
            z.writestr(f"bridge-coach-{version}/{f}", texte)
        z.writestr(f"bridge-coach-{version}/VERSION", version + "\n")
    return b.getvalue()


def copie():
    r = tempfile.mkdtemp(prefix="essai-maj-")
    for f in fichiers:
        os.makedirs(os.path.dirname(os.path.join(r, f)) or r, exist_ok=True)
        open(os.path.join(r, f), "wb").write(open(os.path.join(ICI, f), "rb").read())
    open(os.path.join(r, "VERSION"), "w").write("1.0\n")
    os.makedirs(os.path.join(r, ".venv")); open(os.path.join(r, ".venv", "temoin"), "w").write("x")
    return r


r = copie()
assert maj.poser(archive("1.1"), r, python=python, journal=lambda t: None)
assert maj.version_locale(r) == "1.1" and os.path.exists(os.path.join(r, ".venv", "temoin"))
assert not os.path.exists(os.path.join(r, ".ancien-programme"))

r = copie()
assert not maj.poser(archive("1.2", abimer=True), r, python=python, journal=lambda t: None)
assert maj.version_locale(r) == "1.0" and os.path.exists(os.path.join(r, ".venv", "temoin"))
assert b"\n)\n" not in open(os.path.join(r, "src", "rapport.py"), "rb").read()
print("ok")
