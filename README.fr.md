![HyperKut — Vos images. Votre direction.](docs/media/hero-fr.svg)

<p align="center"><b>Un studio vidéo IA local pour des montages que vous continuez à diriger.</b><br>Remixez une référence, partez d'une idée ou construisez autour de votre musique.</p>

<p align="center"><a href="README.md">English</a> · <a href="#exemples">Exemples</a> · <a href="#installation-windows">Installation</a> · <a href="LICENSES.md">Licences</a></p>

> **Bêta.** La finition (effets, titres, motion graphics, sound design) est expérimentale et désactivée par défaut.

Construit avec ComfyUI pour le [concours Comfy Open Source Higgsfield](https://comfy.org/open-source-higgsfield). Modèles open weights, exécutés sur votre machine.

## Démo

| Démo officielle · 1 min 51 | Présentation · 1 min 47 |
|:---:|:---:|
| <a href="docs/media/hyperkut-demo-official.mp4"><img src="docs/media/demo-official-preview.gif" width="220" alt="Démo officielle"></a> | <a href="docs/media/hyperkut-demo-readme.mp4"><img src="docs/media/demo-readme-preview.gif" width="480" alt="Présentation"></a> |

Aperçus muets : cliquez pour voir la vidéo complète avec le son. Toutes les personnes visibles sont générées par IA par l'auteur.

## Ce que fait HyperKut

| Vous partez de… | Mode | Vous obtenez… |
|---|---|---|
| Une vidéo et des photos de votre personnage ou produit | **Remix** | Le même montage, réinterprété avec votre sujet. |
| Une courte idée | **Texte** | Un plan de montage, des plans générés et une bande-son. |
| Votre musique et une idée | **Musique** | Un montage coupé sur les temps de votre morceau. |

**Idée → plan → génération des plans → choix des prises → découpe → export.**

- **Corrigez un plan, gardez le reste.** Modifiez le prompt d'un plan et régénérez seulement celui-là.
- **Montez après la génération.** Coupez, réordonnez et changez de prise sur une timeline.
- **Tout reste local.** Vos projets, vos modèles, du code MIT ouvert.

| Lancer un projet | Diriger chaque plan | Finaliser le montage |
|:---:|:---:|:---:|
| [![Accueil du Studio](docs/media/studio-home.jpg)](docs/media/studio-home.jpg) | [![Réglages des plans](docs/media/studio-project.jpg)](docs/media/studio-project.jpg) | [![Finition](docs/media/studio-finishing.jpg)](docs/media/studio-finishing.jpg) |

## Exemples

De vrais exports HyperKut. Cliquez sur un aperçu pour voir la vidéo avec le son.

| Mode · Remix | Lookbook · Remix | Mode · Musique | Sneaker · Musique |
|:---:|:---:|:---:|:---:|
| [<img src="docs/media/demos/hyperkut_26c4e181fe36.gif" width="200" alt="Montage mode">](docs/media/demos/hyperkut_26c4e181fe36.mp4) | [<img src="docs/media/demos/hyperkut_4eaec061ddbd.gif" width="200" alt="Lookbook personnage">](docs/media/demos/hyperkut_4eaec061ddbd.mp4) | [<img src="docs/media/demos/hyperkut_ac3723c049d9.gif" width="200" alt="Mode en mouvement">](docs/media/demos/hyperkut_ac3723c049d9.mp4) | [<img src="docs/media/demos/hyperkut_f54b09f850b2.gif" width="200" alt="Sneaker">](docs/media/demos/hyperkut_f54b09f850b2.mp4) |

| Produit · Texte | Personnage · Texte | Casque · Texte |
|:---:|:---:|:---:|
| [<img src="docs/media/demos/hyperkut_9e8e85878a3c.gif" width="200" alt="Produit sculptural">](docs/media/demos/hyperkut_9e8e85878a3c.mp4) | [<img src="docs/media/demos/hyperkut_e721126225dd.gif" width="200" alt="Personnage urbain">](docs/media/demos/hyperkut_e721126225dd.mp4) | [<img src="docs/media/demos/hyperkut_c9cdc7be3b8b.gif" width="200" alt="Casque">](docs/media/demos/hyperkut_c9cdc7be3b8b.mp4) |

La vidéo de référence du Remix mode appartient à [silver.muse](https://higgsfield.ai/@silver.muse). Merci pour l'inspiration.

## Comment ça marche

![Graphe nodal HyperKut : planifier et générer, puis monter et exporter](docs/media/how-it-works-fr.svg)

Le graphe ci-dessus est simplifié ; les workflows API ComfyUI de chaque mode sont dans [`workflows/`](workflows). Les nodes viennent de [Majoor VideoTools](https://github.com/MajoorWaldi/ComfyUI-Majoor-VideoTools).

**Comment les serveurs communiquent.** Le serveur remplit un workflow et l'envoie via le Comfy SDK officiel. `comfy-api-proxy` sert l'API Comfy en local, devant ComfyUI. La progression et les aperçus remontent jusqu'au navigateur ; ComfyUI et le Studio partagent le dossier de sortie.

![Communication des serveurs HyperKut : navigateur, FastAPI, Comfy SDK, comfy-api-proxy, ComfyUI](docs/media/server-flow-fr.svg)

## Par rapport à Katana et Genjutsu

| | HyperKut | Higgsfield Katana | Higgsfield Genjutsu |
|---|---|---|---|
| Idée | Créer et retravailler un montage multi-plans | Recréer un montage de référence avec vos éléments, via Claude | Transformer une vidéo : transfert de mouvement ou remplacement d'objet |
| Exécution | Votre PC, ComfyUI local | Cloud Higgsfield | Cloud Higgsfield |
| Vous dirigez | Prompt par plan, prises, timeline | Instructions dans Claude | Vidéo source et réglages |
| Code | Ouvert, MIT | Géré par le fournisseur | Géré par le fournisseur |

HyperKut ne reproduit pas exactement les montages Katana et n'égale pas la préservation ciblée de Genjutsu. Sources : [Katana](https://higgsfield.ai/blog/higgsfield-katana), [Genjutsu](https://higgsfield.ai/creator-hub/help-center/tools/how-do-i-use-genjutsu), consultées le 29 octobre 2026.

## Installation Windows

**Il faut :** un GPU NVIDIA, [ComfyUI](https://github.com/Comfy-Org/ComfyUI), Python 3.10+, Node.js 22+ et FFmpeg dans le PATH.

1. Dans `ComfyUI/custom_nodes`, installez [Majoor VideoTools](https://github.com/MajoorWaldi/ComfyUI-Majoor-VideoTools) et `comfyui_controlnet_aux` avec le Python de ComfyUI.
2. Téléchargez les modèles de [l'inventaire](https://github.com/MajoorWaldi/ComfyUI-Majoor-VideoTools/blob/main/docs/models-and-downloads.md).
3. Clonez ce dépôt dans le dossier VideoTools, sous le nom `ComfyUI-Majoor-VideoTools/HyperKut Studio`.
4. Dans PowerShell, depuis `HyperKut Studio` :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Push-Location frontend; npm ci; npm run build; Pop-Location
```

5. Lancez ComfyUI, puis `.\scripts\run_studio.ps1`, et ouvrez **http://127.0.0.1:8090/**.

Finition facultative, ports personnalisés et détails : [installation complète](docs/installation.md) · [guide d'utilisation](docs/usage.md) · [dépendances](docs/dependency-scopes.md).

## Licence

Code : **MIT**. Les modèles, dépendances et médias de démo gardent leurs propres conditions : voir [LICENSES.md](LICENSES.md) et les [mentions tierces](THIRD_PARTY_NOTICES.md). [Limites connues](docs/known-issues-and-roadmap.md) · [Roadmap](ROADMAP.md).

HyperKut est indépendant de Higgsfield.
