# HyperKut Studio — checklist de qualification et correctifs

État au 30 octobre 2026. Une case n'est cochée qu'après un correctif livré et
une vérification locale correspondante. Une réussite de tests simulés ne vaut
pas qualification GPU ni preuve de déploiement public.

## Bloquants

- [ ] **HK-01 — Clone public incomplet.**
  - [x] Les modules snapshot requis sont maintenant non ignorés; la CI contient
    un smoke test d'import, et les imports passent dans le checkout local.
  - [ ] Publier ces nouveaux fichiers puis réussir le smoke test depuis un
    clone Git propre; les fichiers sont encore non suivis dans ce worktree.
- [x] **HK-02 — Secours logiciel Text/Remix.** Le plan Text peut continuer sans
  musique facultative; Remix peut retomber sur l'audio source. Les tests de
  secours passent.
- [ ] **HK-02 — Qualification réelle.** Produire et inspecter des MP4 Text et
  Remix sur GPU réel; cette machine n'a pas exécuté ces générations.
- [ ] **HK-03 — Transport distant non reproductible.**
  - [x] Les modules de graphe/transfert requis et leurs tests sont non ignorés;
    les tests distants passent dans le checkout local.
  - [ ] Publier les fichiers non suivis et confirmer l'import depuis un clone
    propre. Les réglages et données privées restent exclus.

## Priorité P1

- [x] **HK-04 — Suppression des takes.** Journal persistant, mise en
  quarantaine, récupération au redémarrage et tests de reprise.
- [ ] **HK-05 — CI et dépendances.**
  - [x] Workflow GitHub Actions backend/frontend et smoke d'import ajoutés;
    `requirements.txt` applique les contraintes publiées.
  - [ ] Confirmer l'exécution GitHub et le smoke depuis le clone propre après
    inclusion des fichiers non suivis.
- [x] **HK-06 — Budget disque et GPU.** Prévision et réservation des jobs,
  limite par défaut à un job GPU actif, contrôles d'espace pour uploads et
  import/export; les tests de capacité passent.

## Priorité P2

- [x] Refuser avec HTTP 409 les presets dont le nom produit un slug déjà pris.
- [x] Réduire la mémoire de l'extraction de waveform en traitant les données
  audio par blocs.
- [x] Ajouter une reprise explicite à partir du plan sauvegardé; les prises
  terminées sont ignorées et la reprise est accessible depuis l'interface.
- [x] Ajouter l'import ZIP du projet avec validation des chemins, du manifeste,
  de la timeline et des médias; les IDs de projets et d'uploads sont remappés.
- [ ] Ajouter une non-régression de finishing pour les ratios pris en charge;
  la qualification GPU/média reste à confirmer.

## Priorité P3 et fiabilité de distribution

- [ ] Compléter la progression par des mesures de temps par étape et un budget
  restant. L'interface conserve actuellement son estimation globale; ce point
  reste à faire.
- [ ] Harmoniser progressivement les noms historiques sans casser les
  variables, données et workflows existants.
- [ ] Traiter le découpage de `server.py` et `runner.py` comme une évolution
  architecturale distincte; cette refactorisation n'a pas été mélangée aux
  correctifs de fiabilité.
- [ ] Confirmer l'installation depuis un clone propre et la matrice
  Studio–VideoTools–ComfyUI sur les versions réellement publiées.
- [ ] Qualifier séparément l'hébergement public et ses contrôles d'accès; le
  mode local/jury ne constitue pas une qualification d'exposition publique.

## Validation réelle GPU

- [ ] Music : répéter le cas documenté sur la révision publiée.
- [ ] Text : produire et inspecter un MP4 complet sur GPU.
- [ ] Remix : produire et inspecter un MP4 complet sur GPU, avec et sans
  génération musicale.
- [ ] Relever durée, VRAM maximale, espace temporaire et intégrité des exports.

## Résultats

Vérifications locales effectuées dans le worktree :

- `python -c "import backend.server, backend.project_import, backend.snapshot_schema, backend.remote_graph, backend.artifact_transfer"` : réussi.
- `.venv\Scripts\python.exe -m pytest -q` : **441 passed, 7 skipped**.
- `npm test` : **129 passed**; `npm run build` et `npm run lint` : réussis.
- Import/export ZIP testé en aller-retour, y compris timeline manuelle et
  remappage d'un média uploadé.

Les tests GPU réels sont les 7 tests ignorés sans l'option `--real`; aucun
résultat GPU ou CI GitHub n'est revendiqué. Les modules snapshot/remote et les
nouveaux changements restent à inclure dans un commit/publication pour
transformer le smoke test local en validation d'un clone public.
