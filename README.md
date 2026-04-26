# voltapeak

Application Python / Tkinter d'analyse de **voltampérogrammes SWV** (*Square Wave Voltammetry* — voltampérométrie à ondes carrées) avec **correction automatique de la ligne de base** par l'algorithme **asPLS** et détection robuste du pic anodique.

L'outil lit un fichier texte à deux colonnes (potentiel, courant), lisse le signal, estime la ligne de base en excluant la zone du pic, puis affiche l'ensemble (brut, lissé, baseline, corrigé, pic) dans une fenêtre matplotlib interactive.

---

## Table des matières

1. [Aperçu fonctionnel](#aperçu-fonctionnel)
2. [Fonctionnalités](#fonctionnalités)
3. [Prérequis](#prérequis)
4. [Installation](#installation)
5. [Utilisation](#utilisation)
6. [Format d'entrée attendu](#format-dentrée-attendu)
7. [Pipeline de traitement](#pipeline-de-traitement)
8. [Architecture du code](#architecture-du-code)
9. [Paramètres scientifiques](#paramètres-scientifiques)
10. [Limitations connues](#limitations-connues)
11. [Dépannage](#dépannage)
12. [Feuille de route](#feuille-de-route)
13. [Licence et auteurs](#licence-et-auteurs)

---

## Aperçu fonctionnel

Au lancement, une fenêtre unique s'ouvre. Elle contient :

- Un bandeau supérieur avec le chemin du fichier sélectionné et un bouton **Parcourir**.
- Un cadre **Paramètres de lecture** permettant de choisir le séparateur de colonnes (Tabulation / Virgule / Point-virgule / Espace) et le séparateur décimal (Point / Virgule).
- Une zone centrale affichant la figure matplotlib une fois l'analyse effectuée, avec la barre d'outils standard (zoom, pan, sauvegarde PNG/PDF).

Un clic sur **Parcourir** ouvre la boîte de dialogue de sélection de fichier ; dès qu'un fichier est validé, l'analyse s'exécute et le graphique est mis à jour.

---

## Fonctionnalités

- Lecture de fichiers texte SWV à **2 colonnes** (potentiel V / courant A).
- **Séparateur de colonnes** et **séparateur décimal** configurables via l'interface.
- **Lissage** du signal par filtre de Savitzky-Golay (fenêtre adaptative, polynôme d'ordre 2).
- **Détection de pic robuste** avec exclusion des bords du scan et filtre de pente (évite les fronts parasites).
- **Estimation de ligne de base** par asPLS (*Adaptive Smoothness Penalized Least Squares*) avec zone d'exclusion centrée sur le pic.
- **Signal corrigé** = signal lissé − baseline, redétection du pic corrigé.
- **Visualisation interactive** matplotlib embarquée dans Tkinter : zoom, déplacement, export PNG/PDF/SVG via la barre d'outils.
- **Tolérance aux erreurs** : toute exception du pipeline est remontée dans une boîte de dialogue, l'interface ne plante pas.

---

## Prérequis

- **Python** ≥ 3.10 (requis pour la syntaxe d'annotation `pd.DataFrame | None`).
- **Tkinter** livré avec la distribution standard CPython sous Windows et macOS ; sous Linux, installer le paquet système (`python3-tk` sur Debian/Ubuntu, `python3-tkinter` sur Fedora).
- Système testé : Windows 11. Aucune dépendance spécifique à Windows, le code reste portable.

---

## Installation

### 1. Créer et activer un environnement virtuel (recommandé)

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

> [requirements.txt](requirements.txt) verrouille les versions au niveau patch (`~=X.Y.Z`) — reproductibilité garantie sur les correctifs de sécurité, sans casse possible sur un changement mineur ou majeur. La déclaration abstraite reste dans [pyproject.toml](pyproject.toml) ; le passage à des bornes `>=,<` dans ce dernier reste prévu (cf. [ROADMAP](ROADMAP.md) item 1.1).

### 3. Vérifier l'installation

```bash
python -c "import pybaselines, scipy, matplotlib, pandas, numpy"
```

Aucune sortie = installation correcte.

---

## Utilisation

Depuis le dossier contenant [voltapeak.py](voltapeak.py) :

```bash
python voltapeak.py
```

Puis dans l'interface :

1. **Sélectionner le séparateur de colonnes** correspondant à votre fichier (tabulation par défaut, ce qui couvre la plupart des exports Autolab / VersaSTAT).
2. **Sélectionner le séparateur décimal** (point pour les exports anglo-saxons, virgule pour les exports francophones).
3. Cliquer sur **Parcourir** — la boîte de dialogue s'ouvre filtrée sur `*.txt`.
4. Choisir votre fichier. L'analyse se lance **automatiquement** et le graphique s'affiche.
5. Utiliser la barre d'outils matplotlib pour zoomer, déplacer la vue ou **exporter** l'image (icône disquette).

Pour analyser un autre fichier : recliquer sur **Parcourir** — l'analyse précédente est remplacée.

---

## Format d'entrée attendu

| Caractéristique       | Valeur                                                   |
|-----------------------|----------------------------------------------------------|
| Extension             | `.txt`                                                   |
| Encodage              | `latin-1` (figé — cf. [Limitations](#limitations-connues)) |
| Nombre de colonnes    | ≥ 2 (seules les 2 premières sont lues)                   |
| Première ligne        | En-tête — **ignorée** (`skiprows=1`)                     |
| Colonne 1             | Potentiel en volts (float)                               |
| Colonne 2             | Courant en ampères (float, signe indifférent)            |
| Séparateur colonnes   | Configurable : tab / virgule / point-virgule / espace    |
| Séparateur décimal    | Configurable : point / virgule                           |
| Nombre minimal de lignes | 5 (pour permettre le lissage)                         |

### Exemple minimal (tabulation, point décimal)

```
Potential	Current
-0.500	-1.2e-6
-0.490	-1.1e-6
-0.480	-0.9e-6
 ...	 ...
```

### Exemple minimal (point-virgule, virgule décimale)

```
Potentiel;Courant
-0,500;-1,2e-6
-0,490;-1,1e-6
 ...   ; ...
```

---

## Pipeline de traitement

```
 ┌──────────────────┐
 │  Fichier .txt    │
 └────────┬─────────┘
          │ readFile (pandas.read_csv, latin-1, skiprows=1, 2 colonnes)
          ▼
 ┌──────────────────────────────┐
 │ DataFrame [Potential, Current] │
 └────────┬─────────────────────┘
          │ processData
          │   · filtrage Current != 0
          │   · tri par Potential croissant
          │   · inversion du signe (−Current)
          ▼
 ┌──────────────────────────────┐
 │ potentialValues, signalValues │
 └────────┬─────────────────────┘
          │ smoothSignal (Savitzky-Golay, window≤11, polyorder=2)
          ▼
 ┌────────────────┐
 │ signalSmoothed │
 └────────┬───────┘
          │ getPeakValue (margin=10%, maxSlope=500)
          ▼
 ┌───────────────┐
 │  xPeakVoltage │ (pic brut, sert uniquement à caler l'exclusion)
 └────────┬──────┘
          │ calculateSignalBaseLine (asPLS, exclusion ±3% autour du pic)
          ▼
 ┌───────────┐
 │ baseline  │
 └────────┬──┘
          │ signalSmoothed − baseline
          ▼
 ┌─────────────────┐
 │ signalCorrected │
 └────────┬────────┘
          │ getPeakValue (margin=10%, maxSlope=500)
          ▼
 ┌───────────────────────────────────┐
 │ xCorrectedVoltage, yCorrectedCurrent │
 └────────┬──────────────────────────┘
          │ plotSignalAnalysis + canvas.draw()
          ▼
 ┌─────────────────────┐
 │ Graphique affiché   │
 └─────────────────────┘
```

---

## Architecture du code

Tout le code tient dans un unique module [voltapeak.py](voltapeak.py).

| Fonction                                                     | Rôle                                                                   |
|--------------------------------------------------------------|------------------------------------------------------------------------|
| [`readFile`](voltapeak.py#L83)                              | Charge le fichier texte en DataFrame (encodage latin-1, 2 colonnes).   |
| [`processData`](voltapeak.py#L138)                          | Filtre, trie, inverse le signe du courant.                             |
| [`smoothSignal`](voltapeak.py#L180)                         | Lissage Savitzky-Golay avec fenêtre adaptative.                        |
| [`getPeakValue`](voltapeak.py#L232)                         | Détecte le maximum avec marge de bords + filtre de pente.              |
| [`calculateSignalBaseLine`](voltapeak.py#L298)              | Estime la ligne de base par asPLS avec exclusion autour du pic.        |
| [`plotSignalAnalysis`](voltapeak.py#L390)                   | Trace brut / lissé / baseline / corrigé / pic sur un axe matplotlib.   |
| [`processAndPlotSingleFile`](voltapeak.py#L477)             | Orchestre tout le pipeline et rafraîchit le canvas Tk.                 |
| [`launch_gui`](voltapeak.py#L593)                           | Construit la fenêtre Tk et sa boucle d'événements.                     |
| [`main`](voltapeak.py#L760)                                 | Point d'entrée — délègue à `launch_gui`.                               |

> Les numéros de ligne sont indicatifs et peuvent évoluer au fil des modifications.

---

## Paramètres scientifiques

Les hyperparamètres sont actuellement **figés dans le code** (leur exposition dans l'UI est prévue en Vague 3 du [ROADMAP](ROADMAP.md)).

| Paramètre               | Fonction                        | Valeur par défaut | Rôle                                                                                             | Impact qualitatif                                                                   |
|-------------------------|---------------------------------|-------------------|--------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|
| `window_length`         | `smoothSignal`                  | 11 (ou `n` si plus court, impair) | Largeur de la fenêtre glissante de Savitzky-Golay.                                               | ↑ → plus de lissage, pics élargis. ↓ → plus de bruit résiduel.                      |
| `polyorder`             | `smoothSignal`                  | 2                 | Ordre du polynôme local ajusté à la fenêtre.                                                     | 2 = parabole, préserve bien la forme d'un pic gaussien/lorentzien.                  |
| `marginRatio`           | `getPeakValue`                  | 0.10 (10 %)       | Fraction du signal à exclure à chaque bord avant recherche du pic.                               | ↑ → moins d'artefacts de bord, mais pics en extrémité ignorés.                      |
| `maxSlope`              | `getPeakValue`                  | 500               | Pente maximale (|ds/dV|) tolérée au point candidat.                                              | ↑ → plus permissif, accepte des fronts. ↓ → plus strict, peut rejeter tout.          |
| `exclusionWidthRatio`   | `calculateSignalBaseLine`       | 0.03 (3 %)        | Demi-largeur de la zone d'exclusion autour du pic, en fraction de l'étendue de potentiel.        | ↑ → protège mieux le pic mais baseline moins contrainte autour.                     |
| `lambdaFactor`          | `calculateSignalBaseLine`       | 1e3               | Facteur λ d'asPLS, multiplié par `n²` en interne.                                                | ↑ → baseline plus lisse (peut couper sous un pic large). ↓ → baseline plus flexible. |
| `tol`                   | `calculateSignalBaseLine` → asPLS | 1e-2              | Tolérance de convergence d'asPLS.                                                                | Compromis précision / vitesse.                                                      |
| `max_iter`              | `calculateSignalBaseLine` → asPLS | 25                | Nombre maximal d'itérations d'asPLS.                                                             | Garde-fou contre les signaux pathologiques.                                         |

---

## Limitations connues

- **Un seul fichier à la fois.** Pas de traitement batch (prévu en Vague 3).
- **Aucun export des résultats numériques** : seul le graphique est visualisable et exportable via la barre d'outils matplotlib (prévu en Vague 3).
- **Hyperparamètres non exposés** dans l'UI : toute modification nécessite de retoucher le code source.
- **Encodage figé à `latin-1`** : les fichiers en UTF-8 contenant des caractères accentués en en-tête peuvent échouer à s'afficher correctement (bien que la ligne d'en-tête soit sautée, les éventuelles lignes de commentaires supplémentaires posent problème).
- **Détection mono-pic** : la fonction détecte le maximum global de la zone centrale, impossible d'extraire plusieurs pics en une seule passe.
- **Pas de tests automatisés** ni de CI (Vague 4).
- **Pas de packaging** (pas d'exécutable autonome pour utilisateurs non-développeurs — Vague 5).
- **Polices graphique très petites** (`fontsize=4`) — lisibles en figure complète mais incongrues à l'écran. À revoir.

---

## Dépannage

| Symptôme                                                     | Cause probable                                        | Correctif                                                                                             |
|--------------------------------------------------------------|-------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| Boîte d'erreur **« Trop peu de points pour lisser le signal. »** | Moins de 5 lignes de données après filtrage.          | Vérifier que le séparateur de colonnes est correct (sinon tout est lu comme une seule colonne).        |
| Le graphique affiche une ligne horizontale / pas de pic      | Colonne de courant toujours à 0 après lecture, ou mauvais séparateur décimal. | Vérifier le séparateur décimal ; ouvrir le fichier dans un éditeur pour confirmer la structure.        |
| **« Fichier invalide »** ou erreur de parsing                | Mauvais séparateur de colonnes.                       | Changer le bouton radio *Séparateur de colonnes* et refaire **Parcourir**.                            |
| Erreur `UnicodeDecodeError`                                  | Fichier en UTF-8 avec BOM ou caractères non latin-1.  | Temporairement : convertir le fichier en latin-1. À terme : encodage configurable (Vague 2).           |
| Le pic marqué est clairement décalé du sommet visible        | Filtre de pente `maxSlope=500` trop strict, fronts parasites détectés comme pic. | À court terme : vérifier la qualité du signal. À moyen terme : exposer `maxSlope` dans l'UI (Vague 3). |
| La fenêtre ne s'ouvre pas sous Linux                         | Tkinter non installé.                                 | `sudo apt install python3-tk` (Debian/Ubuntu).                                                        |

---

## Feuille de route

Voir [ROADMAP.md](ROADMAP.md) pour l'ensemble des évolutions prévues, organisées en vagues de priorité (hygiène, robustesse, fonctionnalités, qualité logicielle, distribution, extensions scientifiques).

---

## Licence et auteurs

- **Licence** : MIT — voir [LICENSE](LICENSE).
- **Auteur / mainteneur** : [@scadinot](https://github.com/scadinot).
- **Organisation** : GROUPE TRACE — usage interne.
- **Dépôt** : https://github.com/scadinot/voltapeak.

Pour toute question ou contribution, ouvrir une *issue* sur le dépôt GitHub ou contacter le mainteneur du projet.
