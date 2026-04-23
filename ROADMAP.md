# Feuille de route — voltapeak

Ce document présente les évolutions prévues pour [voltapeak.py](voltapeak.py), organisées en **six vagues de priorité**. Chaque vague est indépendante : on peut la livrer en une fois ou la fractionner selon les ressources disponibles.

Chaque évolution est caractérisée par :

- **Motivation** : ce que cela corrige ou apporte par rapport à l'existant.
- **Complexité estimée** : **S** (≤ ½ journée), **M** (1 à 3 jours), **L** (> 3 jours).
- **Fichiers impactés** : modules à créer ou modifier.

---

## Table des vagues

| Vague | Thème                       | Horizon           | Nb d'items |
|-------|-----------------------------|-------------------|-----------|
| 1     | Hygiène projet              | Court terme       | 5         |
| 2     | Robustesse                  | Court / moyen     | 5         |
| 3     | Fonctionnalités utilisateur | Moyen terme       | 5         |
| 4     | Qualité logicielle          | Moyen / long      | 4         |
| 5     | Distribution                | Long terme        | 3         |
| 6     | Extensions scientifiques    | Long terme        | 4         |

---

## Vague 1 — Hygiène projet

L'objectif est de poser les fondations minimales attendues de tout projet Python livré : verrou de dépendances, nettoyage du code, licence explicite.

### 1.1 Créer `requirements.txt` et / ou `pyproject.toml` ✅ *(partiellement fait)*

- **Motivation** : aujourd'hui l'installation repose sur un `pip install` manuel sans version figée — risque de régression si une des bibliothèques (notamment `pybaselines`, en évolution active) change de comportement.
- **Livrable** :
  - ✅ [pyproject.toml](pyproject.toml) créé (PEP 621) avec section `[project]` et dépendances listées.
  - ⏳ Reste à faire : figer les versions minimales / maximales (`numpy>=1.24,<3`, etc.) après validation en production.
  - ⏳ Reste à faire : générer un `requirements.txt` verrouillé via `pip freeze` dans un environnement de référence.
- **Complexité** : **S**.
- **Fichiers impactés** : [pyproject.toml](pyproject.toml), `requirements.txt` (à créer).

### 1.2 Ajouter un `.gitignore` standard Python

- **Motivation** : éviter le suivi accidentel de `__pycache__/`, `.venv/`, `*.pyc`, fichiers IDE, exports matplotlib, etc.
- **Complexité** : **S**.
- **Fichiers impactés** : `.gitignore` (nouveau).

### 1.3 Supprimer les imports inutilisés ✅ *(fait)*

- **Motivation** : [voltapeak.py](voltapeak.py) importait `re`, `platform` et `subprocess` sans les utiliser. Ces imports déclenchaient 3 warnings `F401` sur tous les linters.
- **Statut** : ✅ Retirés du fichier. Warnings `F401` résolus.
- **Complexité** : **S**.
- **Fichiers impactés** : [voltapeak.py](voltapeak.py).

### 1.4 Ajouter un fichier `LICENSE`

- **Motivation** : sans licence explicite, le code est par défaut « tous droits réservés », ce qui bloque toute réutilisation et contribution. Nécessite un arbitrage avec le GROUPE TRACE sur la licence cible (propriétaire interne, MIT, Apache 2.0, etc.).
- **Complexité** : **S**.
- **Fichiers impactés** : `LICENSE` (nouveau), en-tête éventuel à ajouter dans [voltapeak.py](voltapeak.py).

### 1.5 Corriger l'annotation de retour de `readFile` ✅ *(fait)*

- **Motivation** : la signature d'origine
  ```python
  def readFile(filePath, sep, decimal) -> (pd.DataFrame|None):
  ```
  utilisait des parenthèses superflues autour du type d'union. Syntaxiquement valide (Python parse `(X)` comme une expression), mais atypique.
- **Statut** : ✅ Remplacée par `-> pd.DataFrame | None`. Annotations `processData` et `getPeakValue` paramétrées en parallèle (`-> tuple[np.ndarray, np.ndarray]` et `-> tuple[float, float]`).
- **Complexité** : **S**.
- **Fichiers impactés** : [voltapeak.py](voltapeak.py).

### 1.6 Corriger la variable non utilisée `yPeakCurrent` ✅ *(fait)*

- **Motivation** : dans [`processAndPlotSingleFile`](voltapeak.py), l'appel à `getPeakValue` sur le signal brut unpacke `(xPeakVoltage, yPeakCurrent)` mais seule l'abscisse sert à la suite (calage de la zone d'exclusion). Déclenchait un warning `F841`.
- **Statut** : ✅ Remplacé par `xPeakVoltage, _ = getPeakValue(...)` avec commentaire explicatif.
- **Complexité** : **S**.
- **Fichiers impactés** : [voltapeak.py](voltapeak.py).

### 1.7 Configurer les linters pour tolérer le camelCase ✅ *(fait)*

- **Motivation** : le projet utilise volontairement le camelCase pour fonctions et variables (cohérence interne). Les règles `N802/N803/N806` (pep8-naming) et `C0103` (pylint) produisent alors des dizaines de faux positifs qui noient les vraies erreurs.
- **Statut** : ✅ Section `[tool.ruff]`, `[tool.pylint.main]` et `[tool.mypy]` ajoutées dans [pyproject.toml](pyproject.toml). Règles de nommage non sélectionnées (ruff) ou désactivées (pylint). `line-length` fixée à 120.
- **Complexité** : **S**.
- **Fichiers impactés** : [pyproject.toml](pyproject.toml).

---

## Vague 2 — Robustesse

Durcir l'application face aux fichiers mal formés, aux variantes locales et aux problèmes d'encodage.

### 2.1 Gestion fine des exceptions de lecture

- **Motivation** : [`readFile`](voltapeak.py) ne capture aucune exception. Un `FileNotFoundError`, un `UnicodeDecodeError` ou un `pandas.errors.ParserError` remonte jusqu'au `except Exception` global de [`processAndPlotSingleFile`](voltapeak.py), qui affiche un message générique peu informatif.
- **Livrable** : capture dédiée par type d'erreur, message utilisateur explicite (« fichier introuvable », « encodage non reconnu », « format de colonnes invalide »).
- **Complexité** : **S**.
- **Fichiers impactés** : [voltapeak.py](voltapeak.py).

### 2.2 Validation du DataFrame après lecture

- **Motivation** : [`readFile`](voltapeak.py) ne vérifie pas que les colonnes lues sont bien numériques ni que le DataFrame contient au moins N lignes. Un fichier à une seule colonne ou à colonnes textuelles produit une erreur tardive dans [`processData`](voltapeak.py) ou [`smoothSignal`](voltapeak.py).
- **Livrable** : après lecture, vérifier `len(df) >= 5`, vérifier `pd.api.types.is_numeric_dtype(df["Current"])`, etc. Message explicite en cas d'échec.
- **Complexité** : **S/M**.
- **Fichiers impactés** : [voltapeak.py](voltapeak.py).

### 2.3 Encodage configurable

- **Motivation** : l'encodage est figé à `latin1` dans [`readFile`](voltapeak.py). Les exports récents (notamment Autolab Nova 2.x) sont souvent en UTF-8. Un fichier UTF-8 avec BOM produit une lecture bancale silencieuse.
- **Livrable** : ajouter un bouton radio ou une liste déroulante (`latin-1`, `utf-8`, `utf-8-sig`, `cp1252`) dans le cadre *Paramètres de lecture*. Valeur par défaut : détection automatique via `charset-normalizer` ou repli sur `latin-1`.
- **Complexité** : **M**.
- **Fichiers impactés** : [voltapeak.py](voltapeak.py).

### 2.4 Détection automatique du séparateur et du décimal

- **Motivation** : l'utilisateur doit aujourd'hui deviner les bons séparateurs. Une erreur produit une erreur de parsing ou — pire — un parsing silencieux en une seule colonne.
- **Livrable** : fonction heuristique qui lit les 5 premières lignes, compte les occurrences de chaque séparateur candidat (tab, virgule, point-virgule, espace) et détecte le séparateur décimal par présence/absence de point ou virgule dans les premiers nombres. L'utilisateur conserve la possibilité de forcer un choix.
- **Complexité** : **M**.
- **Fichiers impactés** : [voltapeak.py](voltapeak.py).

### 2.5 Journalisation (`logging`)

- **Motivation** : impossible aujourd'hui de comprendre a posteriori ce qui s'est passé sur un fichier donné (fenêtre SG retenue, pic détecté, λ effectif, nombre d'itérations d'asPLS). `print` n'est pas utilisé non plus.
- **Livrable** : configurer le module `logging` standard, niveau `INFO` par défaut, fichier de log rotatif dans `%LOCALAPPDATA%/voltapeak/voltapeak.log` (ou équivalent Linux). Chaque étape du pipeline émet une ligne structurée.
- **Complexité** : **M**.
- **Fichiers impactés** : [voltapeak.py](voltapeak.py).

---

## Vague 3 — Fonctionnalités utilisateur

Enrichir le logiciel avec les fonctions les plus souvent demandées en usage réel.

### 3.1 Traitement batch d'un dossier

- **Motivation** : une campagne de mesure produit typiquement 20 à 200 fichiers SWV ; les traiter un par un via **Parcourir** est fastidieux.
- **Livrable** : bouton **Parcourir un dossier** → sélection d'un répertoire, traitement de tous les `.txt`, affichage dans un `ttk.Notebook` (onglets) ou dans une liste latérale cliquable. Export CSV consolidé (cf. 3.2).
- **Complexité** : **L**.
- **Fichiers impactés** : [voltapeak.py](voltapeak.py) — voire éclatement en plusieurs modules (cf. Vague 4).

### 3.2 Export des résultats numériques

- **Motivation** : aujourd'hui seule l'image matplotlib peut être exportée (via la toolbar). Impossible de récupérer les valeurs de pic ou les signaux retraités pour analyses ultérieures (Excel, Origin, Python).
- **Livrable** :
  - Bouton **Exporter CSV** → `<fichier>_analysis.csv` contenant 5 colonnes (`Potential`, `Raw`, `Smoothed`, `Baseline`, `Corrected`).
  - Bouton **Exporter résumé** → fichier unique agrégeant (fichier, pic V, pic mA, λ effectif) pour tous les fichiers d'un batch.
  - Bouton **Exporter PNG/PDF** raccourci (déjà possible via toolbar, mais un bouton dédié réduit le nombre de clics).
- **Complexité** : **M**.
- **Fichiers impactés** : [voltapeak.py](voltapeak.py).

### 3.3 Exposer les hyperparamètres dans l'UI

- **Motivation** : [`marginRatio`](voltapeak.py), [`maxSlope`](voltapeak.py), [`exclusionWidthRatio`](voltapeak.py), [`lambdaFactor`](voltapeak.py) sont figés dans le code. Tout scientifique qui veut ajuster doit éditer le source — non viable en production.
- **Livrable** : panneau rétractable *Paramètres avancés* contenant des `ttk.Spinbox` ou `ttk.Scale` pour chacun, avec rafraîchissement live du graphique. Sauvegarde des derniers réglages dans un fichier de configuration local.
- **Complexité** : **M**.
- **Fichiers impactés** : [voltapeak.py](voltapeak.py).

### 3.4 Détection multi-pics

- **Motivation** : [`getPeakValue`](voltapeak.py) ne détecte que le maximum global de la zone centrale. Les signaux SWV peuvent présenter **plusieurs espèces électroactives** → plusieurs pics d'intérêt.
- **Livrable** : remplacer / compléter par `scipy.signal.find_peaks` avec critères `height`, `distance`, `prominence`. Affichage de tous les pics trouvés avec une couleur par pic et une légende listant (V, mA) pour chacun.
- **Complexité** : **M**.
- **Fichiers impactés** : [voltapeak.py](voltapeak.py).

### 3.5 Superposition / comparaison de spectres

- **Motivation** : comparer visuellement 2 à 5 spectres (témoin vs. échantillon, série de concentrations) est un besoin récurrent.
- **Livrable** : mode **Superposition** activable, accumulation des tracés signalCorrected sur le même axe avec couleurs distinctes et légende par nom de fichier.
- **Complexité** : **M**.
- **Fichiers impactés** : [voltapeak.py](voltapeak.py).

---

## Vague 4 — Qualité logicielle

Rendre le code maintenable à moyen terme.

### 4.1 Séparation GUI / logique métier

- **Motivation** : [voltapeak.py](voltapeak.py) mélange aujourd'hui traitement scientifique (`readFile`, `processData`, `smoothSignal`, `getPeakValue`, `calculateSignalBaseLine`) et interface Tk (`launch_gui`). Cela bloque : (a) les tests unitaires, (b) l'usage sans interface (CLI batch), (c) un éventuel portage vers une autre UI (PyQt, web).
- **Livrable** :
  - `core.py` : pipeline scientifique pur, sans `tkinter` ni `matplotlib.pyplot`.
  - `plotting.py` : construction de figures matplotlib (sans backend Tk spécifique).
  - `gui.py` : couche Tk.
  - `__main__.py` : point d'entrée (`python -m voltapeak`).
- **Complexité** : **M/L**.
- **Fichiers impactés** : éclatement de [voltapeak.py](voltapeak.py).

### 4.2 Tests unitaires (`pytest`)

- **Motivation** : aucun garde-fou automatisé aujourd'hui. Une régression sur [`getPeakValue`](voltapeak.py) ou [`calculateSignalBaseLine`](voltapeak.py) passerait inaperçue.
- **Livrable** : jeux de données synthétiques (gaussienne + drift linéaire + bruit gaussien) avec pic théorique connu ; assertions sur la position du pic, l'aire de la baseline, l'invariance à la densité d'échantillonnage. Couverture cible ≥ 80 % sur `core.py`.
- **Complexité** : **M**.
- **Fichiers impactés** : `tests/` (nouveau), `pyproject.toml`.

### 4.3 Intégration continue

- **Motivation** : les tests et le lint doivent tourner automatiquement à chaque commit, sans reposer sur la discipline individuelle.
- **Livrable** : workflow GitHub Actions (ou GitLab CI / équivalent interne) exécutant `ruff check`, `mypy`, `pytest` sur Python 3.10 / 3.11 / 3.12.
- **Complexité** : **S/M**.
- **Fichiers impactés** : `.github/workflows/ci.yml` (ou équivalent).

### 4.4 Typage renforcé

- **Motivation** : les annotations actuelles sont partielles (`-> tuple` sans contenu, `-> (pd.DataFrame|None)` parenthèses superflues). Un typage strict permettrait à `mypy` de détecter des erreurs de type tôt.
- **Livrable** : typer toutes les signatures avec `tuple[np.ndarray, np.ndarray]`, `numpy.typing.NDArray[np.float64]`, etc. Ajouter un `py.typed` si le module devient installable.
- **Complexité** : **S/M**.
- **Fichiers impactés** : [voltapeak.py](voltapeak.py) (ou les modules issus de 4.1).

---

## Vague 5 — Distribution

Rendre le logiciel utilisable par des non-développeurs.

### 5.1 Exécutable Windows autonome (`pyinstaller`)

- **Motivation** : les utilisateurs finaux (chimistes, techniciens) n'ont pas Python installé et ne souhaitent pas gérer un environnement virtuel.
- **Livrable** : `pyinstaller --onefile --windowed voltapeak.py`, validation que l'exécutable se lance sur une machine Windows vierge, documentation du processus de build dans un `BUILD.md`. Intégration au workflow CI (Vague 4.3).
- **Complexité** : **M**.
- **Fichiers impactés** : `BUILD.md`, `voltapeak.spec`, CI.

### 5.2 Installateur / raccourci bureau

- **Motivation** : un `.exe` seul laisse l'utilisateur gérer sa copie, son icône, sa mise à jour.
- **Livrable** : installateur MSI ou NSIS avec raccourci menu Démarrer + bureau, association optionnelle `.txt` → voltapeak.
- **Complexité** : **M**.
- **Fichiers impactés** : scripts d'installation (nouveau).

### 5.3 Publication sur un dépôt interne ou PyPI

- **Motivation** : rendre l'installation possible via `pip install voltapeak` en interne GROUPE TRACE ou publiquement si l'arbitrage licence le permet.
- **Livrable** : pipeline de publication automatisé (version, tag, build wheel + sdist, push vers le dépôt ciblé).
- **Complexité** : **M**.
- **Fichiers impactés** : CI, `pyproject.toml`.

---

## Vague 6 — Extensions scientifiques

Évolutions fonctionnelles avancées motivées par l'usage.

### 6.1 Algorithmes de baseline alternatifs

- **Motivation** : asPLS est robuste mais pas universel. Pour des signaux très bruités ou très pentus, d'autres algorithmes (ALS, arPLS, IArPLS, rolling-ball, SNIP) peuvent donner de meilleurs résultats.
- **Livrable** : menu déroulant *Méthode de baseline* dans l'UI avec au moins 3 alternatives (tous disponibles dans `pybaselines`). Comparaison visuelle possible en superposant plusieurs baselines.
- **Complexité** : **M**.
- **Fichiers impactés** : `core.py` (post-Vague 4.1), UI.

### 6.2 Intégration de l'aire sous le pic

- **Motivation** : l'aire du pic est physiquement proportionnelle à la quantité d'analyte (loi de Faraday) — information plus robuste que la hauteur du pic pour la quantification.
- **Livrable** : intégration numérique (`scipy.integrate.simpson`) sur la zone centrée autour du pic, après soustraction de baseline. Affichage sur le graphique et dans l'export CSV.
- **Complexité** : **S/M**.
- **Fichiers impactés** : `core.py`.

### 6.3 Historique des analyses (base SQLite)

- **Motivation** : garder la trace de toutes les mesures traitées avec leurs paramètres et résultats, pour reproductibilité et tendance temporelle.
- **Livrable** : base SQLite locale, une table `analyses` (id, timestamp, chemin, paramètres, pic V, pic mA, aire, hash fichier). Interface de consultation / export.
- **Complexité** : **L**.
- **Fichiers impactés** : nouveau module `storage.py`, UI.

### 6.4 Internationalisation des libellés

- **Motivation** : si l'outil est partagé avec des partenaires non francophones, tous les libellés (boutons, labels, messages d'erreur) devront être traduisibles.
- **Livrable** : extraction des chaînes via `gettext`, fichiers `.po` pour `fr` et `en`, sélecteur de langue dans l'UI.
- **Complexité** : **M**.
- **Fichiers impactés** : ensemble du code UI.

---

## Synthèse priorisée

| Priorité | Items                             | Effort total   |
|----------|-----------------------------------|----------------|
| **P0**   | Vague 1 (1.1 → 1.5)               | ~1 jour        |
| **P1**   | Vague 2 (2.1, 2.2, 2.5)           | ~2-3 jours     |
| **P2**   | Vague 3 (3.2, 3.3)                | ~3-5 jours     |
| **P3**   | Vague 4 (4.1 → 4.4)               | ~1-2 semaines  |
| **P4**   | Vague 3 (3.1, 3.4, 3.5) + Vague 5 | ~2 semaines    |
| **P5**   | Vague 6                           | ~2-3 semaines  |

Cette priorisation est **indicative** — elle optimise le ratio valeur utilisateur / effort dans le contexte d'un outil interne GROUPE TRACE. Elle doit être réarbitrée selon les retours utilisateurs et les contraintes business.
