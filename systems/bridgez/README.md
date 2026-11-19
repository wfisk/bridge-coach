# BRIDGEZ (Université du Bridge)

Le système enseigné aux débutants par l'Université du Bridge (livre « BRIDGEZ »), aux enchères plus directes que le SEF.

## Comment il est fait
- Le SEF 2024 avec des conventions coupées : `sans: [Roudi, Drury, …]` dans `regles.yaml`, par leur nom dans le
  fichier du SEF (`nom:`). Les noms : Stayman, Texas, Roudi, Drury, Spoutnik, Bicolores, Landy, 4e couleur forcing,
  Blackwood. `tests/test_systemes.py` vérifie qu'une convention coupée n'est plus jouée.
- `regles.yaml` porte `base: sef-2024` : il n'écrit que ses différences. Une section (une séquence, comme `"1M"` ou
  `"1N - 1M - 1SA"`) écrite ici remplace celle du SEF ; le reste se joue comme le SEF 2024.
- Les entames et la signalisation : celles du SEF tant qu'il n'y a pas de `entames.yaml` ici.
- `pret: non` le cache aux joueurs ; on le passe à `oui` quand les différences sont écrites et vérifiées au banc.

## À faire, d'après le livre (photos des pages de résumé)
Rien n'est encore écrit : il faut le texte du livre, page par page, pour ne rien inventer. Les points à relever :
1. Les ouvertures : zones de points, majeure 5e ou 4e, 1SA (zone), deux faibles / deux forts, barrages.
2. Les réponses à 1 à la couleur (soutiens, nouvelles couleurs, SA), à 1SA (Stayman, texas ?), à 2SA.
3. Les redemandes de l'ouvreur et du répondant ; ce qui est forcing.
4. Les interventions, le contre d'appel, le réveil ; ce qu'on y enseigne en premier.
5. Le chelem (Blackwood à 4 ou 5 as ?), les conventions absentes (Roudi, Drury, Spoutnik… joués ou non).
6. Les entames et la signalisation.

Chaque différence écrite ici cite sa page (`source: BRIDGEZ p. N`).
