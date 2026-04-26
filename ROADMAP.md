# Feuille de route — voltapeak

Ce document recense les évolutions envisagées pour le projet, classées
par horizon (court / moyen / long terme) et par criticité. Chaque
entrée précise la **motivation** (pourquoi c'est utile) et, lorsque
pertinent, une **piste technique** (comment s'y prendre).

La liste est volontairement ouverte : ce ne sont pas toutes des
promesses, mais un réservoir d'idées à prioriser selon les besoins
réels des utilisateurs.

---

## Vue d'ensemble

| Horizon | Objectif principal | Effort estimé |
|---|---|---|
| [Court terme](#court-terme--qualité-de-base-du-projet) | Verrouiller les dépendances, structurer le code, tracer l'exécution | quelques heures à 1 journée |
| [Moyen terme](#moyen-terme--robustesse-et-configurabilité) | Robustesse aux données, configurabilité, tests | quelques jours |
| [Long terme](#long-terme--plate-forme-et-écosystème) | Distribution, batch, écosystème scientifique | plusieurs semaines |
| [Pistes exploratoires](#pistes-exploratoires) | Optimisations ponctuelles et UX avancée | à évaluer au cas par cas |

---

## Court terme — qualité de base du projet

### 1. Figer les versions de dépendances ✅ *(fait)*

**Motivation.** Le projet utilisait à l'origine `pip install` direct
sur les noms de paquets (`numpy`, `pandas`, `matplotlib`, `scipy`,
`pybaselines`) sans contraintes de version. Une mise à jour majeure
d'une bibliothèque — notamment `pybaselines`, en évolution active —
pouvait modifier silencieusement les résultats numériques d'une
exécution à l'autre.

**Statut.** ✅ [requirements.txt](requirements.txt) verrouille les 5
dépendances directes au niveau patch (`~=X.Y.Z`, PEP 440 compatible
release) à partir des versions installées en environnement de
référence — autorise les correctifs de sécurité (patch) mais bloque
les changements mineurs/majeurs susceptibles de casser les calculs.
L'installation se fait par `pip install -r requirements.txt`. Le
projet n'ayant plus de `pyproject.toml` (cf. item 2 sur la structure),
il n'y a plus de `[project] dependencies` à harmoniser.

### 2. Extraire le code en modules

**Motivation.** Les ~760 lignes de [__main__.py](__main__.py)
mélangent traitement scientifique (`readFile`, `processData`,
`smoothSignal`, `getPeakValue`, `calculateSignalBaseLine`), génération
de graphique (`plotSignalAnalysis`) et interface graphique
(`launch_gui`). Cette structure freine la réutilisation (impossible
d'importer l'algorithme sans lancer Tkinter) et rend les tests
difficiles.

**État actuel.** Le projet est déjà un mini-package
(`__init__.py` + `__main__.py`), exécutable par `python -m voltapeak`.
Le code n'est pas encore éclaté en sous-modules.

**Piste technique.** Éclater en :
```
voltapeak/
├── __init__.py    # version, ré-exports
├── core.py        # readFile, processData, smoothSignal,
│                  # getPeakValue, calculateSignalBaseLine
├── plotting.py    # plotSignalAnalysis (sans backend Tk)
├── gui.py         # launch_gui (Tkinter)
└── __main__.py    # délègue à gui.main / core.main
```

### 3. Remplacer les `messagebox` génériques par `logging`

**Motivation.** Toute exception du pipeline est aujourd'hui capturée
dans [`processAndPlotSingleFile`](__main__.py) et affichée dans une
boîte de dialogue Tk avec un message identique pour des causes très
différentes. Aucune trace n'est conservée — impossible de comprendre a
posteriori quels paramètres ont été appliqués (fenêtre Savitzky-Golay
retenue, position du pic brut, λ effectif d'asPLS, nombre d'itérations).

**Piste technique.** Utiliser `logging.getLogger(__name__)` dans les
modules ; un handler fichier rotatif dans
`%LOCALAPPDATA%/voltapeak/voltapeak.log` (ou équivalent Linux) pour
l'historique, un handler custom écrivant dans un widget `Text` de la
GUI pour le retour utilisateur immédiat.

---

## Moyen terme — robustesse et configurabilité

### 4. Gestion d'erreurs typée

**Motivation.** [`readFile`](__main__.py) ne capture aucune exception
spécifique. `FileNotFoundError`, `UnicodeDecodeError` et
`pandas.errors.ParserError` remontent jusqu'au `except Exception`
global de [`processAndPlotSingleFile`](__main__.py), qui affiche un
message générique. L'utilisateur ne sait pas si le problème vient du
chemin, de l'encodage ou du séparateur. De même, le DataFrame n'est
pas validé après lecture : un fichier à une seule colonne ou à
colonnes textuelles produit une erreur tardive et peu parlante dans
[`processData`](__main__.py) ou [`smoothSignal`](__main__.py).

**Piste technique.** Définir `InvalidSWVFileError`, `EncodingError`,
`PeakNotFoundError`, `BaselineEstimationError` héritant de `SWVError`.
Capture dédiée par type, message utilisateur explicite (« fichier
introuvable », « encodage non reconnu », « moins de 5 lignes
exploitables »). Après `pandas.read_csv`, vérifier `len(df) >= 5` et
`pd.api.types.is_numeric_dtype(df["Current"])`.

### 5. Détection automatique des séparateurs

**Motivation.** L'utilisateur doit aujourd'hui cocher manuellement le
bon séparateur de colonnes (tab / virgule / point-virgule / espace) et
le bon séparateur décimal (point / virgule). Source d'erreur fréquente
— pire, un mauvais séparateur de colonnes produit un parsing
silencieux en une seule colonne, sans erreur visible.

**Piste technique.** Utiliser `csv.Sniffer` sur les premières lignes
pour détecter le séparateur de colonnes. Pour le décimal, parser les
premiers nombres en `.` puis en `,` et retenir celui qui produit des
floats. La GUI conserve le choix manuel comme override.

### 6. Encodage configurable

**Motivation.** L'encodage est figé à `latin-1` dans
[`readFile`](__main__.py). Les exports récents (notamment Autolab
Nova 2.x) sont souvent en UTF-8. Un fichier UTF-8 avec BOM produit une
lecture bancale silencieuse — les caractères accentués mal lus, sans
erreur visible jusqu'à ce qu'une ligne de données contienne un
caractère non latin-1.

**Piste technique.** Liste déroulante dans le cadre *Paramètres de
lecture* (`latin-1`, `utf-8`, `utf-8-sig`, `cp1252`). Valeur par
défaut : détection automatique via `charset-normalizer` ou repli sur
`latin-1`.

### 7. Exposer les hyperparamètres dans l'UI

**Motivation.** [`marginRatio`](__main__.py),
[`maxSlope`](__main__.py), [`exclusionWidthRatio`](__main__.py),
[`lambdaFactor`](__main__.py), `window_length` et `polyorder` sont
figés dans le code. Tout scientifique qui veut adapter l'outil à une
nouvelle expérience doit éditer le source — non viable en production.

**Piste technique.** Deux options complémentaires :
- **GUI** : panneau rétractable *Paramètres avancés* avec
  `ttk.Spinbox` ou `ttk.Scale` pour chaque paramètre, rafraîchissement
  live du graphique.
- **Fichier** : `config.toml` à la racine, chargé au démarrage
  (`tomllib`, stdlib depuis Python 3.11), pour figer un jeu de
  paramètres par campagne.

### 8. Tests unitaires et de non-régression

**Motivation.** Aucun garde-fou automatisé aujourd'hui. Une régression
sur [`getPeakValue`](__main__.py) ou
[`calculateSignalBaseLine`](__main__.py) — par exemple lors d'une
mise à jour de `pybaselines` — passerait inaperçue jusqu'à la
prochaine analyse litigieuse.

**Piste technique.** `pytest` + un jeu de **données synthétiques**
(gaussienne + drift linéaire + bruit gaussien) avec pic théorique
connu : assertions `numpy.testing.assert_allclose` sur la position du
pic et l'aire sous la baseline ; vérification de l'invariance à la
densité d'échantillonnage. Couverture cible ≥ 80 % sur `core.py`
(post-item 2).

### 9. Typage renforcé

**Motivation.** Les annotations actuelles sont partielles. Un typage
strict permettrait à `mypy` de détecter des erreurs de type tôt et
d'améliorer l'autocomplétion IDE.

**Piste technique.** Typer toutes les signatures avec
`numpy.typing.NDArray[np.float64]`, `pd.DataFrame`,
`tuple[float, float]`, etc. Ajouter un marker `py.typed` si le module
devient installable (item 11).

---

## Long terme — plate-forme et écosystème

### 10. Traitement batch d'un dossier

**Motivation.** Une campagne de mesure produit typiquement 20 à 200
fichiers SWV ; les traiter un par un via **Parcourir** est fastidieux.
Le projet jumeau [voltapeak_batch](../voltapeak_batch/) couvre déjà
ce besoin, mais la duplication entre les deux projets devra être
résolue à terme — soit en fusionnant les dépôts, soit en factorisant
le `core` dans une bibliothèque commune.

**Piste technique.** Bouton **Parcourir un dossier** → sélection d'un
répertoire, traitement de tous les `.txt`, affichage dans un
`ttk.Notebook` (onglets) ou dans une liste latérale cliquable.
Récapitulatif Excel agrégé en sortie. Réutilisation directe de la
logique de [voltapeak_batch](../voltapeak_batch/voltapeak_batch.py).

### 11. Packaging distribuable

**Motivation.** Les utilisateurs finaux (chimistes, techniciens) n'ont
pas tous un environnement Python fonctionnel. Leur demander
d'installer Python + 5 dépendances + Tkinter sur Linux est un
obstacle à l'adoption.

**Piste technique.**
- **Exécutable Windows** via PyInstaller
  (`pyinstaller --onefile --windowed __main__.py`) : un seul `.exe`
  double-cliquable. Documentation du processus dans `BUILD.md`.
- **Installateur MSI/NSIS** avec raccourci menu Démarrer + bureau,
  association optionnelle `.txt` → voltapeak.
- **Paquet pip** sur PyPI (ou dépôt interne GROUPE TRACE) pour
  l'installation via `pip install voltapeak` ou
  `pipx install voltapeak`.

### 12. Export des résultats numériques

**Motivation.** Aujourd'hui seule l'image matplotlib peut être
exportée (via la toolbar). Impossible de récupérer les valeurs de pic
ou les signaux retraités pour analyses ultérieures (Excel, Origin,
Python).

**Piste technique.** Bouton **Exporter CSV** →
`<fichier>_analysis.csv` à 5 colonnes (`Potential`, `Raw`, `Smoothed`,
`Baseline`, `Corrected`). Bouton **Exporter résumé** → fichier unique
agrégeant (fichier, pic V, pic mA, λ effectif) pour tous les fichiers
d'un batch (cf. item 10).

### 13. Algorithmes alternatifs de baseline

**Motivation.** asPLS est robuste mais pas universel. Pour des signaux
très bruités, très pentus, ou présentant un drift non monotone,
d'autres algorithmes (ALS, arPLS, IArPLS, drPLS, rolling-ball, SNIP)
peuvent donner de meilleurs résultats.

**Piste technique.** La bibliothèque `pybaselines` expose déjà la
plupart de ces algorithmes. Ajouter un sélecteur *Méthode de baseline*
dans la GUI ; optionnellement, un **mode comparaison** qui trace les
baselines concurrentes côte à côte sur le PNG.

### 14. Détection multi-pics

**Motivation.** [`getPeakValue`](__main__.py) ne détecte que le
maximum global de la zone centrale. Les signaux SWV peuvent présenter
**plusieurs espèces électroactives** → plusieurs pics d'intérêt
(typiquement 2 à 4).

**Piste technique.** `scipy.signal.find_peaks` sur le signal corrigé
avec critères `height`, `distance`, `prominence`. Affichage de tous
les pics trouvés avec une couleur par pic et une légende listant
(V, mA) pour chacun. Ajustement gaussien ou lorentzien optionnel pour
l'intégration (cf. item 15).

### 15. Intégration de l'aire sous le pic

**Motivation.** L'aire du pic est physiquement proportionnelle à la
quantité d'analyte (loi de Faraday) — information plus robuste que la
hauteur du pic pour la quantification, en particulier quand la forme
du pic varie d'une mesure à l'autre.

**Piste technique.** Intégration numérique
(`scipy.integrate.simpson`) sur la zone centrée autour du pic, après
soustraction de baseline. Affichage sur le graphique (zone hachurée)
et dans l'export CSV (item 12). Compatibilité avec la détection
multi-pics (item 14).

### 16. Intégration continue

**Motivation.** Aucun garde-fou ne vérifie aujourd'hui qu'un commit
ne casse pas le code ou ne dégrade pas les résultats numériques.

**Piste technique.** GitHub Actions :
- `ruff check` pour le lint ;
- `ruff format --check` pour le formatage ;
- `mypy` pour le typage (item 9) ;
- `pytest` pour les tests (item 8), sur Python 3.10 / 3.11 / 3.12 ;
- build de l'exécutable PyInstaller (item 11) à chaque tag de release.

### 17. Historique des analyses

**Motivation.** Garder la trace de toutes les mesures traitées avec
leurs paramètres et résultats, pour reproductibilité et tendance
temporelle. Aujourd'hui chaque analyse est éphémère — une fois la
fenêtre fermée, tout est perdu.

**Piste technique.** SQLite local (ou PostgreSQL si multi-utilisateur),
table `analyses(id, timestamp, chemin, hash_source, paramètres, pic_V,
pic_mA, aire_C, méthode_baseline)`. Interface de consultation via un
nouvel onglet GUI ou une vue Streamlit séparée.

### 18. Internationalisation

**Motivation.** Les libellés de la GUI sont en français. Pour un usage
hors équipe francophone (publication open-source, partenariat
international), la traduction devient nécessaire.

**Piste technique.** `gettext` avec fichiers `.po` (fr, en, de…).
Détection automatique de la locale système au premier lancement,
sélecteur manuel dans un menu *Préférences*.

---

## Pistes exploratoires

Idées à évaluer au cas par cas, sans priorité ferme.

### Expérience utilisateur

- **Mode « inspection interactive »** : sliders matplotlib sur
  `lambdaFactor`, `exclusionWidthRatio` et `marginRatio` pour ajuster
  la baseline à l'œil sans relancer toute l'analyse.
- **Superposition / comparaison de spectres** : mode permettant
  d'accumuler 2 à 5 tracés `signalCorrected` sur le même axe avec
  couleurs distinctes et légende par nom de fichier (témoin vs.
  échantillon, série de concentrations).
- **Prévisualisation** avant analyse : afficher les 10 premières
  lignes du fichier sélectionné pour vérifier que les séparateurs
  sont corrects avant de lancer le pipeline.
- **Polices du graphique** : `fontsize=4` (codé dans
  [`plotSignalAnalysis`](__main__.py)) est lisible en figure
  exportée mais incongru à l'écran. Ajouter une option ou détecter le
  contexte (intégré GUI vs export PNG).

### Performance et architecture

- **Lazy-loading de matplotlib** : l'import top-level est lent et
  inutile tant que l'utilisateur n'a pas chargé un fichier. Déplacer
  l'import dans [`plotSignalAnalysis`](__main__.py).
- **Cache** : ne pas retraiter un fichier dont le hash SHA-256 n'a
  pas changé depuis la dernière exécution.

### Robustesse aux données

- **Gestion des balayages aller-retour** (cyclic SWV) : l'inversion
  systématique du signe (`-Current` dans
  [`processData`](__main__.py)) pourrait être mal adaptée si la
  première demi-vague est anodique.
- **Diagnostics de parsing plus fins** : aujourd'hui un
  `pandas.errors.ParserError` produit un message générique ; un
  diagnostic ligne par ligne (« ligne 47 : 3 colonnes attendues, 1
  trouvée ») guiderait mieux l'utilisateur.

---

## Contribuer à cette feuille de route

Les priorités évoluent avec les retours utilisateurs. Si une évolution
vous intéresse — ou si vous en voyez une qui manque — ouvrez une issue
sur le [dépôt GitHub](https://github.com/scadinot/voltapeak) ou
contactez le mainteneur.
