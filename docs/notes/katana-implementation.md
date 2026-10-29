# Améliorations inspirées de la revue Katana

## Fonctions

- **Plates** : Text/Music contrôle l'image du lieu avec le modèle de vision local déjà utilisé par le workflow. Seul `clear`, accompagné d'une justification, autorise son utilisation. Personne visible ou réponse illisible : plate ignorée, sans nouvelle génération en boucle. Cette décision automatique reste faillible ; la relecture du résultat reste nécessaire.
- **Énergie** : densités de coupes, flashs, secousses, punchs, whips et mouvements de poussée mesurées dans la référence et le résultat. Une référence non mesurée reste inconnue, jamais assimilée à zéro. Ces heuristiques ne mesurent ni la qualité artistique ni la fidélité d'identité.
- **Relecture** : bouton « Relire le résultat » dans la timeline, vignettes toutes les 0,5 seconde et accès à l'instant choisi. Visage, vêtements, mots et voix sont à vérifier par une personne. Les contrôles techniques ne les certifient pas.
- **Sources économiques** : option Text/Music pour demander au planificateur des cartes, images fixes ou vidéos fournies lorsque cela convient. Les plans correspondants sont rendus par FFmpeg/Pillow, avec un budget H3 nul pour ces plans. Le planificateur peut toujours choisir une génération.
- **Référence de montage** : option Text/Music qui demande d'étudier le rythme, les durées relatives, la palette et le vocabulaire des transitions pour construire un nouveau montage. Les médias fournis restent locaux. Un rapport compare aussi l'énergie de cette référence au résultat.
- **Finition** : couches `effect` supplémentaires : `grain`, `vignette`, `light_leak`, `pan`, `roll`, `handheld`. Rendu déterministe ; amplitude nulle sans modification. Exemple : `[{"type":"effect","kind":"grain","amount":0.2}]` dans les couches de motion graphics.
- **Audio** : mesure du true peak décodé avec FFmpeg EBU R128. Le limiteur historique contrôle les échantillons ; le rapport true peak signale séparément un dépassement de −1 dBTP. Il ne promet pas un mastering automatique sous ce seuil.

## Sources locales dans un plan

Chaque shot accepte un `render_source` optionnel :

```json
{"kind":"generated"}
{"kind":"graphic","color":"#101018","text":"Texte autorisé"}
{"kind":"still","asset":"ref1"}
{"kind":"provided","asset":"ref_video"}
```

Sans champ, le comportement reste la génération habituelle. Les images doivent correspondre aux références 1 à 5 ; une vidéo fournie est la vidéo de référence. Aucun chemin ni code du plan n'est exécuté. Un asset absent provoque une erreur explicite.

## Banque SFX facultative

Indiquer un dossier local contenant `manifest.json` et des WAV PCM 16 bits mono/stéréo. Les fréquences sont converties en 48 kHz. Le manifeste associe les cues `impact`, `hit`, `whoosh`, `swell`, `shutter`, `glitch` à une attribution :

```json
{"hit":{"file":"hit.wav","license":"Votre licence vérifiée","source":"Origine du fichier"}}
```

Les chemins doivent rester dans le dossier. Une attribution renseignée n'est pas une validation juridique de la licence. Aucun son tiers n'est livré ni téléchargé. Les cues absentes utilisent la synthèse procédurale existante. Le cache inclut le contenu des fichiers.

## Vérification et démonstration

Les tests `tests/real` sont facultatifs et ne se lancent qu'avec `--real`, `SECATOR_TEST_MEDIA_DIR` et un Studio local. Ils enregistrent les empreintes des médias, l'état du job, les caractéristiques de l'export et les contrôles humains restant à faire. Ils couvrent produit, création 20 secondes, musique, paysage, voix et personnage. Un test absent ou non exécuté ne constitue pas une validation.

Pour une démonstration : ouvrir un résultat, montrer le budget de génération, les plans et leurs prises, les rapports d'énergie/audio, les vignettes de relecture, puis refaire un plan ciblé. Conserver les originaux et utiliser des médias dont les autorisations de présentation sont établies. Aucune publication n'est automatisée.

## Comparaison Katana

La documentation du connecteur Higgsfield `/katana`, consultée en lecture seule le 24 octobre 2026, décrit également des remakes plan par plan. L'opposition « Katana ne fait jamais de shot-for-shot » du document de départ ne peut donc pas être reprise comme un fait général. Les différences à montrer sont les fonctions observables de cette installation SECATOR : exécution locale, plans et prises éditables, sources de rendu explicites, diagnostic et relecture. Aucun rendu Higgsfield payant n'a été lancé pour cette comparaison.

Les vrais fondus entre deux clips, un moteur HTML séparé et le tracking facial avancé restent des extensions conditionnelles du plan ; ils ne sont pas nécessaires aux fonctions ci-dessus.
