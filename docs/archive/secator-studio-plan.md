> Plan historique. État actuel : YuE2 a remplacé ACE-Step ; le Studio emploie HyperFrames et Tone.js. Ce plan ne certifie ni les licences ni la publication. Voir les README actuels et les documents LICENSES.md / installation.md correspondants.

# SECATOR Studio — plan de l'app pour le concours Open Source Higgsfield

Document de travail du 24 oct. 2026. Il décide d'un dépôt séparé, de l'architecture et du calendrier. Ce qui est vérifié est dit vérifié ; le reste est marqué **à vérifier**.

## 0. Positionnement : SECATOR est le Katana open source

Le but de l'app est de rendre **Katana** de Higgsfield open source et local. Ce que j'ai pu lire de Katana (instructions officielles de la commande `/katana`, lues le 24 oct. ; la page <https://higgsfield.ai/katana> ne contient que ses métadonnées : « Aura-farming machine by Higgsfield & Claude Opus 5.5 ») :

- **Cœur :** refaire la **vidéo de référence plan par plan avec les sujets de l'utilisateur** ; la vidéo de référence est obligatoire.
- **Aussi :** monter les médias fournis par l'utilisateur d'après son brief (« fais-en un montage sigma »), et un **catalogue de presets** (une vidéo de référence publiée + le prompt de son auteur), de la communauté ou de Higgsfield, en trois familles : éditions personnalisées, transfert de style, transfert de mouvement.
- **Comment :** un planificateur (Claude) analyse, planifie, génère les plans, assemble, vérifie et livre la vidéo.

| Katana | SECATOR (ce que VideoTools fait déjà) | Écart |
|---|---|---|
| Refaire une vidéo de référence avec ses sujets | **Remix** : la vidéo est le modèle (coupes, rythme, effets, caméra) ; 5 images de sujets ; tous les plans par H3 ; plans de groupe en pose seule ; texte redessiné | fait |
| Aura-farming | profil `viral_aura_farming` du planificateur ; énergie (flashs, secousses, punch-ins) mesurée et remise ; plaques de lieux ; le « truc » de la vidéo | fait |
| Montage à partir d'un brief | **Creative Text** (idée → musique ACE-Step → montage sur les temps), **Creative Music** (ta musique → montage) | fait (au-delà de Katana : la musique est générée et les coupes suivent le kick) |
| Planificateur : Claude Opus 5.5 | **Gemma 4 en local** (poids ouverts), aucun service | différence à mettre en avant |
| Catalogue de presets | rien | **à faire** : un preset = vidéo de référence + prompt + réglages, en fichier partageable ; l'app en embarque quelques-uns |
| Monter les médias fournis par l'utilisateur d'après un brief | rien (nous générons les plans, nous ne remontons pas des rushes) | **hors périmètre pour le 30 oct.**, à dire dans le README |
| Vérification avant livraison | Take Check (noir, blanc, bruit) ; juge optionnel dans Remix | partiel |

**Dans le README et la démo :** « une alternative open source et locale à Katana de Higgsfield » (le concours s'appelle Open Source Higgsfield), sans reprendre son interface, ses visuels ni ses presets, et avec la mention « non affilié à Higgsfield » (marque et image de marque : c'est à nous de ne pas prêter à confusion).

## 1. Le concours (page lue le 24 oct.)

Source : <https://comfy.org/open-source-higgsfield>

| | |
|---|---|
| Période | 15 → 30 oct. ; **dépôt le 30 oct. à 9 h PT** = 17 h à Paris (calcul : PDT = UTC-7, Paris en heure d'hiver depuis le 25 oct.) ; gagnants le 6 nov. |
| À rendre | le **formulaire** de la page, le **code de l'app sous licence open source avec instructions d'installation**, une **vidéo de démo** (pas besoin de soigner le montage : on juge le travail ; elle doit montrer l'app en action et expliquer comment elle est faite) |
| Modèles partenaires | autorisés, sauf dans la catégorie *Open Weights Only* |
| Catégories | Best Overall (10 000 $, tout le monde, automatiquement) ; Most Innovative, Most Viral, Open Weights Only (une RTX 5090 chacune) ; 10 Runner Ups ; bonus fournisseur : **Built with MiniMax H3** (1 000 $ de crédits API, **H3 doit être le modèle principal**), LTX, FLUX |
| Règle | une entrée peut gagner une catégorie principale et un bonus fournisseur |
| Les détails | « App requirements » et « Prepare your submission » sont des titres sans texte sur la page : **à vérifier** dans le formulaire avant de commencer la vidéo |

**Catégories visées :** Best Overall, Most Viral (l'interface et les presets partageables), Most Innovative (la vidéo sert de modèle de montage ; coupes sur le kick), **bonus MiniMax H3** (H3 génère tous les plans). *Open Weights Only* n'est atteignable que si tous les modèles sont à poids ouverts : H3, Gemma 4, ACE-Step, FLUX.2 klein, BiRefNet. **À vérifier modèle par modèle** (la licence de H3 en premier) ; je ne l'affirme pas.

## 2. Ce que montre la maquette

`F:\__WORKFLOWS\VT\SECATOR_Studio_Prototype_Interactif.html` : un seul fichier, JavaScript sans framework, **tout est simulé** (la fenêtre « Génération » ne lance aucun calcul ; les plans, les versions et le glisser des curseurs sont de la démonstration).

- En-tête : trois onglets **REMIX / TEXT / MUSIC**, GPU local, options avancées, **Générer**.
- Colonne gauche, cinq étapes : 1 vidéo source (modèle de montage) · 2 références (5 images) · 3 vidéo de référence (option) · 4 prompt (1000 caractères) · 5 musique · *Audio final* : Original / Nouveau son / Voix.
- Barre d'outils : durée (10 à 30 s), format (16:9, 9:16...), qualité, **structure %**, **créativité %**.
- Options avancées : conserver les coupes, préserver la caméra, Auto FX, seed, FPS.
- Centre : lecteur et **timeline de plans** avec un inspecteur par plan (prompt du plan, **variante v1, v2...**, **verrouiller**, **couper en deux**, supprimer, **régénérer**) ; 4 étapes en pied de page (analyse, plans, audio, finalisation) ; export de la configuration en JSON.

## 3. Ce que fait déjà VideoTools (et la correspondance avec la maquette)

| Maquette | Contrôle du workflow (`SECATOR …`) | État |
|---|---|---|
| Onglets REMIX / TEXT / MUSIC | `SECATOR Remix`, `SECATOR Creative Text`, `SECATOR Creative Music` | existe, testé plan par plan |
| Vidéo source | LoadVideo « VIDEO TO REMIX » (Remix) ; LoadAudio « YOUR MUSIC » (Music) | existe |
| 5 références | LoadImage REF 1 à 5 | existe |
| Vidéo de référence | LoadVideo (option) | existe |
| Prompt | « WHAT TO REPLACE » (Remix) / « YOUR IDEA » (Creative) | existe |
| Musique / Audio final | « REPLACE THE SOUND », « SOUND MOOD », « BPM », « VOICE ON », « DIALOGUE », « SOUND DESIGN », « SOUND EFFECTS » | existe |
| Durée | « EDIT LENGTH » (Creative) ; Remix = durée de la vidéo | existe |
| Format et qualité | « FORMAT AND QUALITY » (Resolution Selector de ComfyUI) ; Remix : « QUALITY » (plafond de mégapixels) | existe |
| Auto FX / effets | « EFFECTS », « TEXT », « MOTION GRAPHICS ON », `cut_snap` | existe |
| Structure %, créativité % | les cinq réglages du planificateur (`cut_density`, `transition_intensity`, `creative_freedom`...) | existe dans Edit Skills, **à brancher** |
| Seed, FPS | graine de H3 (fixe), fps de Create Timeline | existe |
| Timeline, versions, régénérer un plan | manifeste de plans, révisions, Apply Shot Metadata ; relancer le bloc d'un plan | existe côté nœuds ; **le flux « un plan » n'est pas automatisé** |
| Étapes (analyse, plans, audio, finalisation) | progression des nœuds par websocket | à écrire |

## 4. Dépôt séparé : oui

Je recommande un dépôt **`secator-studio`**, séparé de `ComfyUI-Majoor-VideoTools`.

- **Pourquoi.** VideoTools est un pack de nœuds généraliste (Manager, tests, CHANGELOG) ; l'app est un produit (interface, serveur, workflows, démo, installation guidée). Le concours juge un dépôt d'app avec sa licence et ses instructions : un dépôt à lui évite de mélanger les deux README. Le code reste MIT (même licence que VideoTools).
- **Ce qui reste dans VideoTools :** tous les nœuds, le cœur, les compétences (`skills/`), les tests. L'app **dépend** de lui (il fait la majorité du travail) : c'est dit dans son README et vérifié au démarrage.
- **Ce qui va dans `secator-studio` :** l'interface (`frontend/`), le serveur (`backend/`), les modèles de workflows au format API (`workflows/`), les presets (`presets/`), les scripts de lancement, les tests de l'app, la démo. Les trois graphes `SECATOR *.json` restent la source : le dépôt de l'app en garde une copie et les scripts d'export qui produisent les modèles API à partir d'eux.
- **Un nœud à ajouter dans VideoTools** (voir §5) : **Load Shot List** (relit la liste de plans d'un projet sur disque), pour que le montage final soit une exécution séparée.
- **Mise en place :** l'app se lance seule (`run_studio`, un serveur local) et parle à un ComfyUI déjà lancé ; ComfyUI doit avoir `ComfyUI-Majoor-VideoTools`, KJNodes, comfyui_controlnet_aux et easy-use. Un script vérifie les paquets et les modèles et affiche les liens manquants.

## 5. Architecture de l'app

### Ce que montre le dépôt cité (kevin9327, <https://github.com/kevin9327/OpenSourceHiggsfield>)

C'est **une autre entrée au concours**, pas la spécification : la page du concours ne détaille pas ce qu'on doit rendre, et ses affirmations (« open weights », « 13/13 tests ») sont les siennes, je ne les ai pas vérifiées. Elle donne la forme que prend une entrée complète :

- une **app web autonome** (`frontend/`, quatre onglets) avec un **serveur FastAPI** (`backend/server.py`, REST et événements en continu) qui parle à un **ComfyUI local** ; deux modes (`OPEN_WEIGHTS_LOCAL` par défaut, qui bloque les nœuds partenaires fermés, et `CLOUD_HYBRID`) ;
- des **workflows au format API** dans `workflows/` (six fichiers `.api.json`) ;
- un pack de nœuds personnalisés, un **serveur MCP** (six outils), **13 tests**, des scripts `run_studio.bat` et `.ps1`, des captures d'écran, un script qui construit la vidéo de démo ;
- une licence **MIT**, un README d'installation (`pip install -r requirements.txt`, tests, lancement sur le port 8090).

Elle utilise `comfy-sdk` et `comfy-api-proxy`. **Vérifié le 24 oct. (docs.comfy.org) : ce sont les SDK officiels de Comfy, mais la page du concours ne les mentionne pas** (elle ne nomme que ComfyUI ; « App requirements » et « Prepare your submission » sont des titres sans texte ; le pied de page renvoie vers Comfy CLI, MCP, Agent et Developer Platform sans description).

| | |
|---|---|
| Python | `pip install comfy-sdk` (Python 3.10+), clients `Comfy` et `AsyncComfy` ; dépôt Comfy-Org/comfy-python-sdk |
| TypeScript | `npm i @comfyorg/sdk` (**Node 22+**, asynchrone seulement : un SDK de serveur, pas du navigateur ; une clé d'API ne doit pas aller dans une page web) ; dépôt Comfy-Org/comfy-typescript-sdk |
| Version | 0.5.0, « première version », portée volontairement petite ; clients de l'API Comfy v2 |
| Utilisation | un workflow **au format API** (`workflows.from_file`), des fichiers d'entrée (`assets`), `run()` ou `submit()`, un flux d'événements (`Progress`, `Preview`, `OutputReady`, `StatusChange`), les sorties d'un nœud (`get_outputs`), annulation, erreurs typées |
| ComfyUI local | installer et lancer **`comfy-api-proxy`** (Comfy-Org/comfy-api-proxy) à côté de ComfyUI, puis `COMFY_BASE_URL=http://127.0.0.1:8189` |
| Pas pris en charge | paramètres de workflow nommés, introspection des nœuds, bibliothèque de modèles, nœuds personnalisés et extensions du frontend (« ces SDK pilotent ComfyUI de l'extérieur ») |

Conséquences pour nous : (1) **utiliser le SDK est cohérent** avec l'app autonome et les modèles API prévus ; (2) la partie qui parle au SDK doit être un **serveur** (Python `AsyncComfy`, pas le navigateur) ; (3) le SDK ne remplace pas la lecture du manifeste de Majoor ni les sorties « interface » de nos nœuds (liste des plans) : le serveur lit le manifeste sur le disque, comme je l'ai fait à la main ; (4) il n'y a pas de paramètres nommés : nos emplacements nommés restent à nous (`set_input(node_id, nom, valeur)`) ; (5) **non vérifié** : que `comfy-api-proxy` fasse passer nos nœuds personnalisés et la lecture des sorties de `SaveVideo` ; c'est le premier sondage du serveur.

### Changement de ma recommandation

J'avais proposé une extension de l'interface de ComfyUI. **Je ne la garde plus** : elle ressemblerait moins à une app, elle exige le navigateur de ComfyUI, et elle n'offre pas de mode sans interface. Je choisis **l'app autonome avec les workflows au format API**, et je résous le point dur (convertir nos graphes à sous-graphes en prompts API) **à l'avance, pas à l'exécution** :

1. **À la construction (une fois, avec les outils que j'utilise déjà).** J'exporte avec `graphToPrompt` trois modèles API par mode : *étape 1* (plan, musique, rythme), *un plan* (Select Shot → H3 → prise → Apply Shot Metadata, avec `shot_id` en paramètre) et *montage final* (assemblage, son, effets, masque, mouvement, sauvegarde). Chaque modèle a des **emplacements nommés** (les contrôles de l'interface). Ce sont les fichiers `workflows/*.api.json` du dépôt, comme dans l'entrée citée.
2. **À l'exécution.** Le serveur remplit les emplacements, soumet l'étape 1, lit le manifeste (nombre de plans, durées), soumet **un prompt par plan** puis le prompt final ; la progression vient du websocket de ComfyUI. Plus de « Create shots » ni de blocs clonés : c'est ce qui rend **la régénération d'un plan** simple (on resoumet un seul plan, puis le final).
3. **Pourquoi ça marche** (déjà fait à la main) : j'ai exécuté un plan seul en élaguant le prompt à ses ancêtres, et le cache de ComfyUI réutilise l'étape 1 d'un prompt à l'autre.
4. **Le nœud à ajouter :** **Load Shot List** (projet → liste de plans relue du manifeste) pour que le montage final puisse partir d'un projet dont les prises ont été enregistrées par les prompts de plans (Apply Shot Metadata écrit déjà les révisions sur disque).

Routes du serveur : lancer, état, annuler, régénérer un plan, verrouiller, couper un plan, lister les presets, vérifier l'installation. Les versions d'un plan sont les révisions du manifeste. *Verrouiller* = ne pas le relancer. *Couper en deux* = changer le plan JSON : **à concevoir**.

Erreurs : modèles absents (liste et liens), vidéo trop courte, mémoire ; un message clair, jamais une trace brute.

## 6. Calendrier (6 jours, dépôt le 30 oct. à 17 h)

| Jour | Contenu | Fini quand |
|---|---|---|
| **Sam. 24 / dim. 25** | Dépôt, licence, squelette (serveur, interface portée de la maquette). Nœud **Load Shot List** (+ test). **Export des modèles API** pour Remix et leur exécution par le serveur : étape 1, un plan par prompt, montage final. | un Remix complet lancé par le serveur depuis la page, avec la progression réelle |
| **Lun. 26** | Modes Text et Music (modèles exportés). Réglages (format, qualité, effets, son). Timeline réelle (vignettes, versions). | les trois modes génèrent depuis l'interface |
| **Mar. 27** | **Régénérer un plan**, verrouiller, structure % et créativité %. **Presets** (fichiers partageables, une demi-douzaine fournis). Gestion des erreurs, vérification de l'installation. Tests de l'app (aucune logique sans test). | un plan régénéré en moins de 2 minutes en brouillon, sans refaire les autres |
| **Mer. 28** | Génération des démos (une par mode, en pleine résolution : 15 à 25 minutes chacune). README (anglais), installation pas à pas depuis une machine propre. Correctifs. | le dépôt s'installe et tourne en suivant le README |
| **Jeu. 29** | Vidéo de démo (tu l'enregistres ; je prépare le script et les montages), formulaire, relecture. Tampon pour les bugs. | tout est prêt la veille au soir |
| **Ven. 30, matin** | Dépôt avant 17 h ; ne rien développer. | formulaire envoyé |

La génération est le goulot : une pub complète en pleine résolution a pris 20 minutes (9 plans, 768×1344), 8 minutes en brouillon. Les démos se lancent la nuit pendant que je développe.

## 7. Risques et questions ouvertes

1. **Export des modèles API** : le point dur est maintenant l'étape d'export (valeurs des contrôles bien nommées, éléments en pause, sous-graphes aplatis par `graphToPrompt`). Je le vérifie dès le premier jour sur Remix ; une mauvaise sortie se voit tout de suite (ComfyUI refuse le prompt).
2. **Aucun montage complet** n'a été relancé depuis les dernières modifications (sound design, bruitages, plan ré-essayé, calage sur les temps) : seuls des plans isolés ont tourné. À faire dès que le serveur est relancé.
3. **Open Weights Only** : à vérifier modèle par modèle (§1) ; l'app peut aussi, comme l'entrée citée, **refuser les nœuds partenaires fermés** par un mode `OPEN_WEIGHTS_LOCAL` (nos workflows n'en utilisent aucun).
4. **Les « plans déformés »** (un visage qui fond) ne sont pas détectés par Take Check : l'interface doit permettre de les régénérer en un clic.
5. **Décisions pour toi :** nom du dépôt (`secator-studio` ?), interface en anglais par défaut (la maquette est en français ; le concours est international) avec le français en option, qui enregistre la démo, et les vidéos de référence libres de droits pour les presets.
