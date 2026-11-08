#!/bin/sh
# Crée l'application « Bridge Coach » dans Applications et son lien sur le Bureau, puis propose de l'ajouter
# au Dock (--dock : sans demander). À relancer si le projet change de dossier.
# Une petite application AppleScript : un script shell dans un .app n'a pas le droit de lire Documents,
# et macOS ne lui demande rien.
set -e
ICI="$(cd "$(dirname "$0")" && pwd)"
APP="/Applications/Bridge Coach.app"
rm -rf "$APP"
# elle reste ouverte tant que le programme tourne : sinon macOS le signale comme tâche de fond ; un clic
# sur son icône remet la fenêtre devant. Le processus de la fenêtre se retire du Dock (src/app.py).
SCRIPT="$(mktemp)"
cat > "$SCRIPT" <<FIN
on run
	do shell script quoted form of "$ICI/bridge-coach.sh" & " > /dev/null 2>&1 &"
end run

on reopen
	do shell script "/usr/bin/curl -s -m 2 http://localhost:8123/devant > /dev/null 2>&1 || true"
end reopen

property demarre : false

on idle
	if not demarre then
		set demarre to true
		return 20
	end if
	try
		do shell script "/usr/bin/pgrep -f " & quoted form of "$ICI/src/app.py"
	on error
		quit
	end try
	return 5
end idle
FIN
osacompile -s -o "$APP" "$SCRIPT"
rm -f "$SCRIPT"
# l'icône de l'applet est aussi dans Assets.car, qui passe avant applet.icns : on le retire
rm -f "$APP/Contents/Resources/Assets.car"
/usr/libexec/PlistBuddy -c "Delete :CFBundleIconName" "$APP/Contents/Info.plist" 2>/dev/null || true
cp "$ICI/src/icone.icns" "$APP/Contents/Resources/applet.icns"
plutil -replace NSDocumentsFolderUsageDescription -string "Vos séances et vos rapports sont dans le dossier Documents." "$APP/Contents/Info.plist"
codesign --force --deep --sign - "$APP"
ln -sfn "$APP" "$HOME/Desktop/Bridge Coach"
touch "$APP"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP"
echo "Créée : $APP, avec son lien sur le Bureau."

# le Dock : seulement si l'utilisateur le veut, et une seule fois
dans_le_dock() { defaults read com.apple.dock persistent-apps 2>/dev/null | grep -q "Bridge%20Coach.app"; }
ajouter_dock() {
    if dans_le_dock; then echo "Bridge Coach est déjà dans le Dock."; return; fi
    defaults write com.apple.dock persistent-apps -array-add "<dict><key>tile-data</key><dict><key>file-data</key><dict>\
<key>_CFURLString</key><string>file:///Applications/Bridge%20Coach.app/</string>\
<key>_CFURLStringType</key><integer>15</integer></dict></dict></dict>"
    killall Dock
    echo "Bridge Coach est ajouté au Dock."
}
if [ "${1:-}" = "--dock" ]; then
    ajouter_dock
elif [ -t 0 ] && ! dans_le_dock; then
    printf "Ajouter aussi Bridge Coach au Dock ? [o/N] "
    read reponse || reponse=""
    case "$reponse" in o|O|oui|Oui|OUI) ajouter_dock ;; *) echo "Pour le Dock plus tard : ./raccourci-mac.sh --dock, ou glisser l'application depuis Applications." ;; esac
fi
