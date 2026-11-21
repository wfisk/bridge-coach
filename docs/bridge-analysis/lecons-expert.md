# Pièges de l'expert : leçons des analyses passées

One line per mistake the user caught in an expert analysis (date, deal, the rule). Read before every expert
analysis; add a line each time the user corrects one. « Préparer pour l'expert » sends this file to Claude on the web
(documents « lecons-expert.md »). A lesson that is a system rule also goes into regles.yaml / entames.yaml when the
bench allows it; a lesson stays here until then.

- 2026-11-20, deal 1: after 1♦ – 2♣, opener's 2♥ is a **bicolore cher (17+ HL)** in our system
  (regles.yaml « 1K - 2T »); with 14 H, 2SA. With only 12 H and 4♥ + 5♣, the simple 1♦ – 1♥ – 2♥ – 4♥ beats the
  2♣ route: the fit is found at once.
- 2026-11-20, deal 1: **a doubleton of honours facing the ace's suit gives one trick fewer**: ♦R965 opposite ♦DV
  makes two tricks, not three (the ace takes one honour of the doubleton, a hold-up does not change it). So 3SA
  needed the ♥D finesse.
- 2026-11-20, deal 2: the SEF **fit différé** may be bid in a three-card minor (1♥ – 2♦ on ♦986 with 13+ and a
  heart fit). It is systemic; do not call it misleading. Prefer a real five-card major only as a « Décision
  serrée ».
- 2026-11-20, deals 9 and 22: **never lead away from an ace against a suit contract.** entames.yaml's card rule
  gives ♠V from AV9763 (the leader's own long suit): the expert leads ♠A and says so (gap logged for entames.yaml).
