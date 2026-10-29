# SECATOR · revue des connecteurs et de Higgsfield Katana

24 octobre 2026

## Résumé

Les connecteurs Higgsfield ne fournissent rien qu'on doive brancher dans SECATOR : ils sont cloud et payants en crédits, et SECATOR est local et gratuit. Leur vraie valeur est ailleurs : le mode d'emploi de Katana contient des idées de méthode à reprendre, et deux outils servent à publier la démo.

- **Katana, ce qu'il apporte :** une méthode de travail (analyse de la référence image par image, mesure de l'énergie, contrôle qualité), pas du code à copier. Deux idées sont directement utiles : contrôler que les plans de décor générés ne contiennent pas de personne, et mesurer le rythme des flashs et des secousses d'une vidéo de référence.
- **Une différence de fond à écrire dans le README :** Katana refait un nouveau montage dans le langage de la référence, sans le copier plan par plan ; notre mode Remix garde les coupes et remplace le sujet. Les modes Texte et Musique sont plus proches de l'esprit Katana.
- **Outils utiles pour la démo :** les connecteurs TikTok et la liste des musiques libres de TikTok, la miniature de la démo, et Calendar pour poser les rappels avant le 30 octobre.
- **À ne pas faire sans décision de l'auteur :** enregistrer un résultat sur Higgsfield, entrer dans un concours avec un lien, envoyer une vidéo à un outil d'analyse en ligne, dépenser des crédits. Aucun n'a été fait.
- **Un gain immédiat :** deux connecteurs Higgsfield sont branchés en même temps. Katana lui-même note que cela double le chargement des outils dans la conversation. Un seul suffit pour ce projet.

## Connecteurs de la session

Six serveurs sont connectés à la session ; seuls les deux Higgsfield touchent au sujet du projet.

| Connecteur | Outils | À quoi il sert au projet | Verdict |
| --- | --- | --- | --- |
| Higgsfield (le grand) | 150 | Katana, génération image et vidéo, analyse de vidéo, TikTok, sites web, modèles | Garder pour lire la doc de Katana et publier ; ne rien générer |
| Higgsfield AI (le petit) | 7 | Solde, liste des modèles, espaces de travail, import d'un mouvement depuis une URL | Doublon du grand : le désactiver |
| Claude Docs | 8 | Documents partagés | Utile |
| Google Drive | 8 | Ranger la démo, la liste des médias libres, les pièces du dossier de candidature | Utile si tout doit être au même endroit |
| Google Calendar | 9 | Rappels : enregistrement de la démo, publication, date limite du 30 octobre, 17 h à Paris | Utile, sur demande |
| scheduled-tasks | 6 | Tâches planifiées de la session | Pas nécessaire |

Le navigateur intégré de l'application sert à exporter les templates depuis ComfyUI et à tester l'interface. L'état de Claude in Chrome n'a pas été vérifié.

## Higgsfield Katana, point par point

Katana prend une vidéo de référence et des images du sujet, et rend un nouveau montage dans le langage de la référence. Tout tourne dans le bac à sable cloud de Higgsfield, avec ses propres scripts et des crédits payants. Lus : le mode d'emploi et quatre fiches de référence (qualité créative et design de mouvement en entier, montage et routage en partie). Non lus : les scripts, que le mode d'emploi interdit de recopier. Aucune génération n'a été lancée.

| Point | Ce que fait Katana | SECATOR aujourd'hui | À reprendre ? |
| --- | --- | --- | --- |
| Entrée | Une référence et des images suffisent, sans texte | Remix : une vidéo et des images ; Texte et Musique : une idée | Déjà équivalent |
| Sens du remix | Un nouveau montage dans l'esprit de la référence, jamais plan pour plan | Remix garde les coupes et change le sujet | Dire la différence dans le README |
| Lecture de la référence | Image par image, avec un journal de preuves | Détection des plans, puis Gemma lit les images de chaque plan | Suffisant pour la démo |
| Énergie de la référence | Mesure le nombre de coupes, flashs, secousses et mouvements de caméra par seconde, et le reporte dans le résultat | Les effets du plan sont écrits par le planificateur, rien ne mesure ceux de la référence | Oui, idée simple et utile |
| Contrat de la tâche | Liste ce qui est verrouillé et ce qui est libre avant de commencer | Deux réglages (fidélité, liberté) et le prompt | Non, trop lourd |
| Plans de décor | Un plan de lieu sans personne, vérifié à la main : le modèle y a dessiné une personne dans 6 plans sur 8 malgré « sans personne » | Même principe (FLUX.2 klein), sans aucun contrôle | Oui, ajouter un contrôle de personne |
| Identité | La photo du sujet telle quelle, jamais une image régénérée ; la tenue de la photo dans toutes les scènes | REF 1 gardée telle quelle, tenue conservée | Déjà équivalent |
| Visages | Jamais retouchés par du code | Aucun code ne touche aux visages | Déjà équivalent |
| Musique et bruitages | Uniquement des enregistrements réels, jamais fabriqués par du code ; une bibliothèque de bruitages libres de droits | Les bruitages automatiques sont fabriqués par le code | À étudier, après la démo |
| Texte | Dessiné à part, par-dessus le montage fini | Motion Graphics, même principe | Déjà équivalent |
| Contrôle final | Trois relectures du mouvement, une inspection par seconde | Take Check par plan (noir, blanc, bruit) | Une relecture manuelle suffit |
| Coût | Plafond de crédits, devis avant chaque génération | Gratuit, temps estimé par plan | Sans objet : c'est notre argument |

Deux apports de Katana valent le travail avant le 30 octobre : le contrôle des plans de décor et la mesure de l'énergie. Katana raconte aussi que ses montages paraissaient plats quand le mouvement de caméra tombait à un tiers de celui de la référence : nos effets de montage compensent déjà en partie, mais rien ne le mesure.

## Comment Katana fait le montage, les effets et le motion graphics

Katana ne génère que des plans de vidéo ; tout le reste (coupes, effets, texte, son) est du code de composition qui tourne dans son bac à sable, comme chez nous avec Shot Assemble et Motion Graphics. Il choisit un moteur selon le type de référence : un moteur canvas pour les plans générés avec calques, un moteur ffmpeg pour les images réelles, et une page HTML dessinée image par image pour le motion design pur.

| Étape | Comment Katana la fait | Chez SECATOR | À reprendre ? |
| --- | --- | --- | --- |
| Choix de la source de chaque plan | Un routeur décide plan par plan : code (carton, flash, noir, titre), garder une séquence fournie, image fixe, générer avec Seedance 2.5, ou refaire une performance par transfert de mouvement | H3 génère chaque plan ; en Remix on remplace le sujet du plan source | Oui, une idée : un plan de simple flash ou de titre n'a pas besoin de H3 |
| Génération | Un seul job produit plusieurs plans de 2 s écrits avec leurs minutages ; marge de ×2 car le modèle ralentit les gestes ; les points d'entrée se choisissent sur une planche-contact, pas sur les minutages promis | Un plan est une génération, la densité vient des sous-coupes | Déjà équivalent (peu de générations, beaucoup de coupes) |
| Liste de montage | Un fichier JSON décrit plans, caméra, looks, calques, transitions, texte, autocollants ; Chrome sans fenêtre dessine les images en parallèle, puis encodage x264 | Le plan JSON du planificateur, rendu par Shot Assemble | Déjà équivalent |
| Caméra | crop, zoom, push, punch, ladder, pan, roll, handheld, shake, speed ; ralenti avec interpolation d'images | zoom, focus, flip, rampes de vitesse | Ajouter handheld, pan et roll aux effets du plan, si le temps le permet |
| Looks | xerox, duotone, négatif, niveaux, seuil, grade, filtre | look du plan (mono, négatif...) | Non pour la démo |
| Calques | Gros texte, contour, lueur, éclat, doodles, mot, graffiti, slash, étincelles, noir et blanc, bandes de cinéma, teinte, inversion, séparation RVB, stroboscope, fuite de lumière, vignette, grain, poussière, bordure | Motion Graphics : texte, boîte, angles, emoji, contour, effets (aberration, glitch, grille, points, lignes de balayage), suivi | Ajouter grain, vignette et fuite de lumière, utiles pour le look VHS du preset rêve ralenti |
| Visage | Des calques suivent le visage (joues, oreilles, croc, blush...) ; le code mesure seulement la position, il ne touche jamais au visage | Des points suivent le sujet par masque | Non |
| Transitions | flashlight, mosaic, magenta, glitch, flou, blanc, flash, fondu au noir | flash, whip, punch, glitch, shake, strobe, inversion, flou, fondus | Déjà équivalent |
| Texte | Écrit dans le plan avant la génération, dessiné après le montage ; la police est choisie par la forme des lettres et vérifiée chargée | Texte du planificateur dessiné par l'assemblage | Déjà équivalent |
| Motion design pur | Une page HTML dont chaque image se calcule à partir du temps, sans hasard ni minuterie | Aucun équivalent, Motion Graphics dessine sur un montage | Non, hors sujet |
| Son | La musique source est copiée sans réencodage ; une bibliothèque de 338 bruitages libres de droits en 18 catégories (boom, hit, flash, crack, riser, glitch, whoosh...) est mixée sur les moments d'effet ; un limiteur ramène la crête vraie sous −1 dBTP | Bruitages automatiques fabriqués par le code, musique en ducking | À étudier : un pack de bruitages libres et un limiteur de crête vraie |
| Contrôle | Compare le résultat à la référence aux mêmes minutages, planches toutes les 0,5 s | Take Check par plan | Non |

Ces moyens sont livrés sous forme de scripts que Katana appelle dans son bac à sable : analyze_ref (lecture de la référence), energy (rythme des coupes, flashs, secousses), viewproof (preuve de lecture image par image), style (recensement du style dessiné), faces (détection et suivi de visage), matte (découpes), edl (liste de montage), render et page_render (rendu), sfx et audio (bruitages et alignement audio), frames et compare (planches et comparaisons), prodcheck (vérifications), ledger (plafond de crédits), deliver (fichier final). Leur rôle est déduit de la documentation, aucun script n'a été lu.

### Les trois moteurs de rendu, en détail

Ce qui suit vient de la documentation de Katana ; aucun script n'a été lu, c'est le principe décrit, pas le code.

**1. Le moteur canvas (plans générés avec calques)**

1. Une liste de montage en JSON décrit chaque plan : la séquence, la caméra, le look, les calques, les transitions, le texte.
2. Les séquences sont découpées en images JPEG, une par image (`plates/<clip>/00000.jpg…`). Les découpes du sujet (masques) le sont en PNG.
3. Une page web charge la bibliothèque d'effets (Canvas2D, sans dépendance) et la liste de montage, et expose `renderFrame(i)` : elle dessine l'image `i` avec la séquence, la caméra, le look, les calques et le texte.
4. Un petit serveur local lance plusieurs Chrome sans fenêtre en parallèle ; chacun calcule une tranche d'images et la renvoie au serveur.
5. ffmpeg assemble les images en H.264 avec le nombre d'images exact, ajoute la musique et les bruitages, puis un limiteur règle le niveau.

**2. Le moteur ffmpeg (images réelles)**

1. Le montage est une liste de tranches : nombre d'images, fichier, point de départ, vitesse, zoom, recadrage, flip, grade, effets, calques à superposer.
2. Chaque tranche est rendue par ffmpeg avec ses filtres et un nombre d'images exact ; le ralenti utilise l'interpolation d'images.
3. Les tranches sont mises bout à bout sans réencodage, puis une dernière passe applique la finition globale et ajoute le son. C'est le plus rapide quand il y a peu de graphismes.

**3. La page HTML calculée image par image (motion design pur)**

1. Une page unique définit `render(t)` : pour un temps `t`, elle dessine l'image correspondante.
2. Tout se calcule à partir de `t` seul : pas d'état gardé d'une image à l'autre, pas de minuterie, pas d'animation CSS qui court, pas de hasard (un générateur à graine fixe le remplace).
3. Texte et chiffres sont en HTML, CSS et SVG, les particules en Canvas. Polices et images sont des fichiers locaux ; le rendu n'ouvre aucune connexion réseau.
4. Un script vérifie ces règles, puis plusieurs Chrome prennent une capture de la page pour chaque image, et le tout est encodé avec le son.

**Pourquoi trois moteurs.** Le moteur canvas garantit qu'aucun code ne touche au visage (il vient du modèle), ffmpeg est le plus rapide pour des images réelles, et la page HTML donne des lettres et des tracés exacts que les modèles vidéo brouillent.

**Chez nous.** Shot Assemble joue les deux premiers rôles en une seule passe, et Motion Graphics couvre en partie le troisième, mais sur un montage existant. Aucun des trois n'est à copier avant le 30 octobre.

## Le catalogue de presets

Le catalogue que renvoie le connecteur compte 63 recettes, 45 pour des images et 18 pour des vidéos, et toutes tournent autour du produit : packshot, plan en main, déballage, mouvements de caméra (pull back, push in, whip pan, crane reveal, product spin). Aucune ne crée un montage viral avec des coupes sur le rythme.

- **Ce que ça implique :** nos six presets (changement de tenue, montée vers la révélation, produit, micro-émotion, drop hype, rêve ralenti) ne font pas double emploi avec ce catalogue.
- **Une idée à prendre :** les mouvements de caméra du catalogue (push in, whip pan, pull back, crane reveal) sont une liste de mots clairs pour le champ « Camera look » de l'application.
- **Une limite de lecture :** le catalogue des presets Katana de la communauté (les montages) ne s'ouvre que dans une fenêtre d'interface, il n'a pas été parcouru.

## Autres workflows et outils Higgsfield

Sur treize workflows livrés avec le connecteur, trois peuvent servir autour de SECATOR ; aucun ne remplace un morceau du projet. Aucun n'a été lancé.

| Outil ou workflow | Ce qu'il fait | Utile au projet ? | Remarque |
| --- | --- | --- | --- |
| character-sheet | Fiche de personnage en plusieurs vues, avec prompt prêt à copier | Oui, pour fabriquer un sujet de référence | Vérifier le contenu des images avant de les utiliser comme référence |
| thumbnail-generation | Miniature de vidéo YouTube ou Instagram | Oui, pour la miniature de la démo | Génération payante en crédits |
| video-montage | Assemble des clips, change la bande-son, incruste des sous-titres | Peut-être, pour sous-titrer la démo | Notre montage final fait déjà le reste |
| video-editing (Higgsedit) | Édition et motion graphics dans l'outil de Higgsfield | Non | Équivalent de notre nœud Motion Graphics |
| Application Match Cut + Tracelab | 28 actions : raccord de plans, suivi d'objets, effets CRT, VHS, glitch, thermique | Non | Recoupe nos effets VHS et glitch ; à regarder pour des idées de look |
| motion_control (Kling 3.0) | Anime une image avec le mouvement d'une vidéo | Non | Notre Remix fait ça avec H3 et le contrôle de pose, en local |
| video_analysis_create | Analyse plan par plan d'une vidéo ou d'un lien YouTube, 3 à 5 minutes | Pour la recherche de références | Envoie la vidéo à un tiers ; plus la vidéo est longue, moins l'analyse est fiable |
| virality_predictor | Prédit l'accroche et la rétention d'une vidéo | Option, sur la démo finie | Envoie la vidéo à un tiers ; crédits possibles |
| tiktok_music_trending | Pistes tendance sous licence commerciale de TikTok | Oui, pour les presets Musique | Demande un compte TikTok connecté |
| tiktok_prepare_publish | Prépare la publication d'une vidéo sur TikTok | Oui, pour poster la démo | Le formulaire est validé par l'auteur ; la vidéo doit être hébergée par Higgsfield |
| ad-multiplier, ads-studio, brand-asset-creation, faceless-video, narration, product-photoshoot, ugc-video, website-builder-flow | Publicité, marque, narration, sites web | Non | Hors sujet |

La liste des modèles (models_explore) montre ce que propose Higgsfield, mais SECATOR n'en utilise aucun : tout tourne sur H3, Gemma 4, ACE-Step 1.5 et FLUX.2 klein en local.

## Autres connecteurs

Trois connecteurs génériques aident le dossier de candidature sans toucher à la technique.

- **Claude Docs :** documents partagés. On peut y ajouter la fiche de présentation du projet, le script de la démo et les paroles de la chanson, avec commentaires et partage.
- **Google Drive :** un dossier pour la démo finale, la liste des vidéos et musiques libres de droits (Pexels, Pixabay) et les captures d'écran. Rien n'y est envoyé sans demande.
- **Google Calendar :** poser les étapes avant la date limite du 30 octobre, 9 h à San Francisco, soit 17 h à Paris : enregistrer la démo, la monter, publier, déposer le dossier. Créer un événement est visible dans l'agenda : seulement sur demande.
- **scheduled-tasks :** inutile ici ; moins de six jours et chaque étape se fait à la main.

## Règles, droits et risques

| Risque | Pourquoi | Ce qu'on fait |
| --- | --- | --- |
| Confusion avec Higgsfield | SECATOR se présente comme l'alternative libre à Katana | Garder la mention « non affilié », aucun logo ni nom de marque dans l'interface |
| Code et sons de Katana | Les scripts et la bibliothèque de bruitages appartiennent à Higgsfield et ne se lisent que dans leur bac à sable | Reprendre les idées, jamais le code ni les fichiers ; chercher nos propres bruitages libres |
| Licence de H3 | Clause de territoire (UE, Royaume-Uni, Corée, États-Unis) déjà notée dans le README | Poser la question aux organisateurs avant le 30 octobre |
| Entrer dans le concours | L'outil du connecteur ne vaut que pour un site web publié sur Higgsfield, avec des liens de réseaux sociaux ; notre projet est un dépôt local | Ne pas l'utiliser ; confirmer auprès des organisateurs comment déposer le dossier |
| Enregistrer un résultat sur Higgsfield | register_katana_result relie une vidéo à un preset Katana d'un compte | Inutile pour SECATOR, qui ne produit pas un résultat Katana |
| Crédits et données | Toute génération dépense des crédits ; l'analyse et la prédiction envoient la vidéo à un service tiers | À ne faire que sur une vidéo libre de droits ou la démo finale |
| Droits des références | Une vidéo virale appartient à son auteur | Déjà écrit dans l'application et les presets : vidéo libre de droits ou la sienne |

## Plan d'action jusqu'au 30 octobre

Ce qui compte avant la date limite est une démo qui marche et un dossier propre ; les idées de Katana passent après. Les durées sont des estimations.

| # | Action | Qui | Durée | Pourquoi |
| --- | --- | --- | --- | --- |
| 1 | Finir les essais : Musique, Remix, Texte dense de 20 s, trois nouveaux styles, Music sync | Dev | 1 à 2 h de GPU | La démo doit passer dans les trois modes |
| 2 | Poser la question aux organisateurs : format du dépôt et clause de territoire de H3 | Auteur | Aujourd'hui | Peut changer ce qu'on livre |
| 3 | Désactiver le petit connecteur Higgsfield AI | Auteur | 1 minute | Moins d'outils chargés dans la conversation |
| 4 | Ajouter au README la différence avec Katana : local et gratuit, et Remix garde les coupes | Dev | 30 minutes | Position claire du projet |
| 5 | Enregistrer la démo avec une vidéo et une musique libres de droits | Auteur | Une demi-journée | Pièce principale du dossier |
| 6 | Contrôle de personne sur les plans de décor | Dev | Une demi-journée | Évite une personne parasite dans une scène |
| 7 | Publier la démo sur YouTube ou TikTok (formulaire TikTok préparé, validé par l'auteur) | Auteur, dev | 30 minutes | Lien à mettre dans le dossier |
| 8 | Poser les rappels dans Calendar, sur demande | Dev | 5 minutes | Éviter l'oubli de la date limite |
| 9 | Mesure de l'énergie de la référence en Remix | Dev | Une journée | Utile mais pas nécessaire pour la démo |

Les lignes 1 à 5 sont indispensables, les lignes 6 à 9 sont des plus.

Les idées de Katana qui ne tiennent pas avant le 30 octobre vont dans la feuille de route du dépôt ([known-issues-and-roadmap.md](../known-issues-and-roadmap.md)), version 0.2 :

- mesurer l'énergie d'une référence (coupes, flashs, secousses, mouvements de caméra par seconde) et la donner au planificateur ;
- nouveaux effets : mouvements handheld, pan et roll ; calques grain, vignette et fuite de lumière pour le look VHS ;
- un pack de bruitages enregistrés libres de droits à la place de ceux fabriqués par le code, et un limiteur de crête vraie à −1 dBTP ;
- un plan qui n'est qu'un flash, une couleur ou un titre dessiné par le code, sans appeler H3 ;
- plus tard : des calques qui suivent le visage, sans jamais le modifier.

Le contrôle de personne sur les plans de décor et la phrase du README sur la différence avec Katana sont déjà dans la liste « maintenant » du dépôt.
