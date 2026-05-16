# voltapeak

Outil graphique (Tkinter) d'**analyse interactive d'un fichier de voltammétrie à vagues carrées** (SWV — *Square Wave Voltammetry*), avec correction automatique de ligne de base par l'algorithme **asPLS Whittaker** et détection robuste du pic anodique.

---

## Table des matières

1. [À quoi sert cet outil ?](#à-quoi-sert-cet-outil-)
2. [Fonctionnalités](#fonctionnalités)
3. [Prérequis](#prérequis)
4. [Installation](#installation)
5. [Lancement](#lancement)
6. [Format des fichiers d'entrée](#format-des-fichiers-dentrée)
7. [Utilisation — interface graphique](#utilisation--interface-graphique)
8. [Résultats produits](#résultats-produits)
9. [Chaîne de traitement par fichier](#chaîne-de-traitement-par-fichier)
10. [Paramètres algorithmiques](#paramètres-algorithmiques)
11. [Architecture du code](#architecture-du-code)
12. [Dépannage](#dépannage)
13. [Feuille de route](#feuille-de-route)
14. [Licence et auteur](#licence-et-auteur)

---

## À quoi sert cet outil ?

La **voltammétrie à vagues carrées** (Square Wave Voltammetry, SWV) est une technique électrochimique qui mesure le courant traversant une électrode en fonction d'un potentiel imposé. Le signal obtenu présente un **pic** caractéristique de l'espèce analysée, superposé à une **ligne de base** (*baseline*) qui dérive lentement avec le potentiel.

Pour exploiter le pic, il faut :

1. **lisser** le signal pour atténuer le bruit de mesure ;
2. **estimer puis soustraire** la ligne de base ;
3. **relever** les coordonnées (tension, courant) du pic corrigé.

`voltapeak` automatise ces trois étapes en s'appuyant sur :

- **Savitzky-Golay** pour le lissage (convolution polynomiale locale) ;
- **asPLS Whittaker** (*asymmetric Penalized Least Squares*, bibliothèque [`pybaselines`](https://pybaselines.readthedocs.io/)) pour l'estimation robuste de la baseline, avec une pondération réduite autour du pic afin d'éviter que la baseline ne « suive » et n'efface le pic.

`voltapeak` cible l'**exploration interactive d'un seul fichier** : la figure est affichée dans une fenêtre matplotlib zoomable, idéale pour qualifier visuellement un signal, régler l'œil sur la détection ou préparer une figure pour un rapport. Les traitements par lot sont assurés par les projets frères [`voltapeak_batch`](https://github.com/scadinot/voltapeak_batch) et [`voltapeak_loops`](https://github.com/scadinot/voltapeak_loops).

---

## Fonctionnalités

- Lecture d'**un fichier `.txt`** à deux colonnes (potentiel V, courant A).
- **Séparateur de colonnes** et **séparateur décimal** configurables dans l'interface.
- **Lissage** Savitzky-Golay (fenêtre 11, ordre 2, fenêtre adaptative en cas de signal court).
- **Détection de pic robuste** : exclusion des 10 % de bords du scan et filtre de pente (rejette les fronts parasites).
- **Estimation de ligne de base asPLS** avec zone d'exclusion ±3 % centrée sur le pic.
- **Signal corrigé** : `signalLissé − baseline`, suivi d'une re-détection du pic corrigé.
- **Visualisation interactive** matplotlib embarquée dans Tkinter : zoom, déplacement, export PNG/PDF/SVG via la barre d'outils.
- **Tolérance aux erreurs** : toute exception du pipeline est remontée dans une boîte de dialogue, l'interface ne plante pas.

---

## Prérequis

- **Python ≥ 3.10** — la syntaxe des annotations de type (`T | None`, `tuple[...]`) utilisée dans le code l'impose.
- **Systèmes supportés** : Windows, macOS, Linux.
- **Tkinter** — inclus dans la distribution standard de Python sous Windows et macOS ; sous Linux, installer au préalable le paquet système :

  ```bash
  sudo apt install python3-tk        # Debian / Ubuntu
  sudo dnf install python3-tkinter   # Fedora
  ```

---

## Installation

### 1. Créer et activer un environnement virtuel (recommandé)

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

> [`requirements.txt`](requirements.txt) verrouille les versions au niveau patch (`~=X.Y.Z`) — reproductibilité garantie sur les correctifs de sécurité, sans casse possible sur un changement mineur ou majeur. Le projet n'a pas de `pyproject.toml` : la configuration de chaque outil de lint / typecheck vit dans son fichier dédié ([`ruff.toml`](ruff.toml), [`.pylintrc`](.pylintrc), [`mypy.ini`](mypy.ini), [`pyrightconfig.json`](pyrightconfig.json)).

---

## Lancement

Depuis le **dossier parent** du dossier `voltapeak/` :

```bash
python -m voltapeak
```

---

## Format des fichiers d'entrée

| Caractéristique          | Valeur                                                       |
|--------------------------|--------------------------------------------------------------|
| Extension                | `.txt`                                                       |
| Encodage                 | `latin-1`                                                    |
| Nombre de colonnes       | ≥ 2 (seules les 2 premières sont lues)                       |
| Première ligne           | en-tête — **ignorée** (`skiprows=1`)                         |
| Colonne 1                | Potentiel en volts (float)                                   |
| Colonne 2                | Courant en ampères (float, signe indifférent)                |
| Séparateur de colonnes   | configurable : tabulation / virgule / point-virgule / espace |
| Séparateur décimal       | configurable : point / virgule                               |
| Nombre minimal de lignes | 5 (pour permettre le lissage)                                |

Exemple (tabulation, point décimal) :

```
Potential	Current
-0.500	-1.2e-6
-0.490	-1.1e-6
-0.480	-0.9e-6
...
```

---

## Utilisation — interface graphique

Au lancement, la fenêtre contient :

- un bandeau supérieur avec le chemin du fichier sélectionné et un bouton **Parcourir** ;
- un cadre **Paramètres de lecture** :
  - *Séparateur de colonnes* : `Tabulation` (défaut), `Virgule`, `Point-virgule`, `Espace` ;
  - *Séparateur décimal* : `Point` (défaut) ou `Virgule` ;
- une zone centrale qui affiche la figure matplotlib une fois l'analyse effectuée, avec la barre d'outils standard (zoom, pan, sauvegarde PNG/PDF/SVG).

Workflow :

1. Choisir le séparateur de colonnes correspondant au fichier (tabulation par défaut, ce qui couvre la plupart des exports Autolab / VersaSTAT).
2. Choisir le séparateur décimal (point pour les exports anglo-saxons, virgule pour les exports francophones).
3. Cliquer sur **Parcourir** — la boîte de dialogue s'ouvre filtrée sur `*.txt`.
4. Sélectionner le fichier. L'analyse **se lance automatiquement** et le graphique s'affiche.
5. Utiliser la barre d'outils matplotlib pour zoomer, déplacer la vue ou exporter l'image (icône disquette).

Pour analyser un autre fichier : recliquer sur **Parcourir** — l'analyse précédente est remplacée.

---

## Résultats produits

`voltapeak` ne produit **aucun fichier de sortie automatique**. La visualisation embarquée superpose :

- signal brut (courant inversé) ;
- signal lissé (Savitzky-Golay) ;
- baseline estimée (asPLS) ;
- signal corrigé (lissé − baseline) ;
- marqueur du pic corrigé.

L'utilisateur peut **exporter manuellement** la figure courante via la barre d'outils matplotlib (formats PNG, PDF, SVG, EPS, PS, RAW). Pour des exports automatisés par lot, utiliser [`voltapeak_batch`](https://github.com/scadinot/voltapeak_batch) ou [`voltapeak_loops`](https://github.com/scadinot/voltapeak_loops).

---

## Chaîne de traitement par fichier

```
┌──────────────────────────┐
│ Fichier *.txt (entrée)   │
└────────────┬─────────────┘
             │ readFile()       séparateur & décimale configurables
             ▼
┌──────────────────────────┐
│ DataFrame brut           │
└────────────┬─────────────┘
             │ processData()    courant=0 supprimé, tri sur potentiel, -I
             ▼
┌──────────────────────────┐
│ Signal nettoyé           │
└────────────┬─────────────┘
             │ smoothSignal()   Savitzky-Golay (w=11, ordre=2)
             ▼
┌──────────────────────────┐
│ Signal lissé             │
└────────────┬─────────────┘
             │ getPeakValue()   pic dans la zone centrale, filtre de pente
             ▼
┌───────────────────────────┐
│ (x_pic, y_pic) provisoires│
└────────────┬──────────────┘
             │ calculateSignalBaseLine()  asPLS, exclusion ±3 % autour du pic
             ▼
┌──────────────────────────┐
│ Baseline estimée         │
└────────────┬─────────────┘
             │ signal_corrigé = signal_lissé - baseline
             ▼
┌──────────────────────────┐
│ Signal corrigé           │
└────────────┬─────────────┘
             │ getPeakValue()   pic final
             ▼
┌──────────────────────────┐
│ (x_pic, y_pic) corrigés  │
└────────────┬─────────────┘
             │ plotSignalAnalysis() + canvas.draw()
             ▼
┌──────────────────────────┐
│ Figure interactive (Tk)  │
└──────────────────────────┘
```

---

## Paramètres algorithmiques

Les hyperparamètres sont actuellement **codés en dur** dans le script. Leur exposition dans l'interface graphique est prévue (voir [`ROADMAP.md`](ROADMAP.md)).

| Paramètre               | Valeur     | Rôle                                                                                         |
|-------------------------|------------|----------------------------------------------------------------------------------------------|
| `window_length`         | `11`       | Largeur de la fenêtre Savitzky-Golay (nombre impair de points).                              |
| `polyorder`             | `2`        | Ordre du polynôme ajusté localement par Savitzky-Golay.                                      |
| `marginRatio`           | `0.10`     | Fraction de points exclus aux deux bords lors de la recherche du pic.                        |
| `maxSlope`              | `500`      | Pente absolue maximale tolérée pour un candidat-pic (filtre les fronts).                     |
| `exclusionWidthRatio`   | `0.03`     | Demi-largeur (fraction de la plage de potentiel) de la zone protégée autour du pic.          |
| `lambdaFactor`          | `1e3`      | Facteur multiplicatif du paramètre de lissage Whittaker : `lam = lambdaFactor · n²`.         |
| `aspls.diff_order`      | `2`        | Ordre de différence dans l'ajustement Whittaker.                                             |
| `aspls.tol`             | `1e-2`     | Tolérance de convergence.                                                                    |
| `aspls.max_iter`        | `25`       | Nombre maximum d'itérations de réajustement des poids.                                       |

---

## Architecture du code

Le projet est un package Python minimal — deux fichiers seulement :

| Fichier                      | Rôle                                                                                            |
|------------------------------|-------------------------------------------------------------------------------------------------|
| [`__init__.py`](__init__.py) | Métadonnées du package (`__version__`) — marque le dossier comme package et permet `python -m voltapeak`. |
| [`__main__.py`](__main__.py) | Code applicatif complet (pipeline + GUI Tkinter + entry point `main()`).                        |

Chaînage des appels :

```
main()
 └── launch_gui()                    Tkinter — construit et affiche la fenêtre
      ├── (callback Parcourir)       sélection du fichier .txt
      └── processAndPlotSingleFile()
           ├── readFile()
           ├── processData()
           ├── smoothSignal()
           ├── getPeakValue()            (signal lissé)
           ├── calculateSignalBaseLine()
           ├── getPeakValue()            (signal corrigé)
           └── plotSignalAnalysis() → canvas.draw()
```

---

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| Boîte d'erreur **« Trop peu de points pour lisser le signal. »** | Moins de 5 lignes de données après filtrage. | Vérifier que le séparateur de colonnes est correct (sinon tout est lu comme une seule colonne). |
| Graphique affichant une ligne horizontale / pas de pic | Colonne de courant à 0 après lecture, ou mauvais séparateur décimal. | Vérifier le séparateur décimal ; ouvrir le fichier dans un éditeur pour confirmer la structure. |
| **« Fichier invalide »** ou erreur de parsing | Mauvais séparateur de colonnes. | Changer le bouton radio *Séparateur de colonnes* et refaire **Parcourir**. |
| Erreur `UnicodeDecodeError` | Fichier en UTF-8 avec BOM ou caractères non latin-1. | Convertir temporairement le fichier en latin-1. Encodage configurable prévu en feuille de route. |
| Pic marqué clairement décalé du sommet visible | Filtre de pente `maxSlope=500` trop strict, fronts détectés. | Vérifier la qualité du signal ; exposition de `maxSlope` dans l'UI prévue en feuille de route. |
| La fenêtre ne s'ouvre pas sous Linux | Tkinter non installé. | `sudo apt install python3-tk` (Debian / Ubuntu). |

---

## Feuille de route

Voir [`ROADMAP.md`](ROADMAP.md) pour l'ensemble des évolutions prévues.

---

## Licence et auteur

- **Auteur** : Stéphane Cadinot ([@scadinot](https://github.com/scadinot)).
- **Licence** : MIT — voir [`LICENSE`](LICENSE).

Pour toute question ou contribution, ouvrir une *issue* sur le dépôt GitHub.
