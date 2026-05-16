# ROADMAP — voltapeak

Évolutions planifiées, regroupées en **vagues de priorité**. L'ordre des vagues est indicatif : un item peut être avancé si une demande utilisateur le rend prioritaire. Aucun item n'a de date d'engagement — le projet reste en usage interne GROUPE TRACE et avance par opportunité.

> Cette feuille de route est partagée entre les trois projets [`voltapeak`](https://github.com/scadinot/voltapeak), [`voltapeak_batch`](https://github.com/scadinot/voltapeak_batch) et [`voltapeak_loops`](https://github.com/scadinot/voltapeak_loops) : les items marqués **(commun)** s'appliquent aux trois et bénéficieront idéalement de la même implémentation (cf. Vague 6 — mutualisation du noyau scientifique).

---

## Table des matières

1. [Vague 1 — Hygiène & robustesse](#vague-1--hygiène--robustesse)
2. [Vague 2 — Configurabilité](#vague-2--configurabilité)
3. [Vague 3 — Fonctionnalités utilisateur](#vague-3--fonctionnalités-utilisateur)
4. [Vague 4 — Qualité logicielle](#vague-4--qualité-logicielle)
5. [Vague 5 — Distribution](#vague-5--distribution)
6. [Vague 6 — Extensions scientifiques](#vague-6--extensions-scientifiques)
7. [Contribuer](#contribuer)

---

## Vague 1 — Hygiène & robustesse

Items qui éliminent des pièges connus ou des limitations documentées dans le [`README`](README.md).

- **Encodage configurable** *(commun)* — l'encodage de lecture est aujourd'hui figé à `latin-1`. Exposer dans l'UI une bascule `latin-1 / utf-8 / utf-8-sig`, avec auto-détection optionnelle (`chardet`).
- **Support du pic anodique** *(commun)* — `processData` inverse systématiquement le signe du courant. Ajouter une case à cocher *« Pic en courant positif (anodique) »* qui désactive l'inversion.
- **Garde-fou explicite sur le nombre de points** *(commun)* — message d'erreur explicite si le signal est trop court pour le lissage (actuellement : exception générique remontée en boîte de dialogue).
- **Polices du graphique trop petites** *(spécifique voltapeak)* — `fontsize=4` est lisible une fois la figure exportée mais difficile à l'écran. Passer à une taille adaptée à la fenêtre Tk (par défaut `fontsize=10`) et conserver l'option fine pour les exports PDF / publication.

---

## Vague 2 — Configurabilité

Exposer dans l'UI ce qui est aujourd'hui codé en dur.

- **Exposition des hyperparamètres** *(commun)* — panneau « Paramètres avancés » repliable, avec les sliders / champs numériques pour :
  - `window_length` (Savitzky-Golay)
  - `polyorder`
  - `marginRatio`
  - `maxSlope`
  - `exclusionWidthRatio`
  - `lambdaFactor`
- **Profils de paramètres** *(commun)* — sauvegarde / rechargement de jeux de paramètres nommés (JSON dans `~/.voltapeak/profiles/`), pour basculer rapidement entre différentes campagnes.

---

## Vague 3 — Fonctionnalités utilisateur

- **Export automatique de la figure** — case à cocher pour enregistrer automatiquement un PNG à côté du fichier d'entrée, sans passer par la barre d'outils matplotlib.
- **Comparaison de plusieurs fichiers superposés** — sélectionner 2 à 5 fichiers et tracer leurs signaux corrigés sur le même axe pour comparer (sans pipeline batch complet).
- **Affichage des coordonnées du curseur** — annotation interactive au survol pour lire facilement (V, A) à n'importe quel point de la courbe.

---

## Vague 4 — Qualité logicielle

- **Tests automatisés** *(commun)* — couverture `pytest` sur les fonctions pures (`readFile`, `processData`, `smoothSignal`, `getPeakValue`, `calculateSignalBaseLine`) avec jeux de données synthétiques (gaussienne + baseline + bruit).
- **CI GitHub Actions** *(commun)* — workflow qui lance `ruff`, `mypy`, `pyright`, `pylint` et `pytest` à chaque push / PR.
- **Type-checking strict** *(commun)* — passer `mypy --strict` proprement (aujourd'hui plusieurs `# type: ignore` ou imports non typés pour `pybaselines`, `scipy`).

---

## Vague 5 — Distribution

- **Packaging PyInstaller** *(commun)* — exécutable autonome `voltapeak.exe` pour utilisateurs non-développeurs (`freeze_support()` déjà en place côté batch / loops).
- **Découpage en modules** *(commun)* — éclater `__main__.py` en `io.py`, `processing.py`, `plotting.py`, `gui.py`, `cli.py`. Pré-requis pour la mutualisation (Vague 6).
- **Mode CLI** *(commun)* — sous-commande `python -m voltapeak --file <path>` qui fait tourner le pipeline et produit le PNG sans GUI (utile pour scripts batch externes).

---

## Vague 6 — Extensions scientifiques

- **Mutualisation du noyau scientifique** *(commun)* — extraire `readFile`, `processData`, `smoothSignal`, `getPeakValue`, `calculateSignalBaseLine` dans un package partagé `voltapeak_core`, importé par les trois projets. Élimine la duplication actuelle et garantit que les correctifs scientifiques se propagent.
- **Détection multi-pics** — repérer plusieurs maxima locaux significatifs et tous les annoter, au lieu du seul maximum global.
- **Métriques de qualité du fit** — afficher SNR, résidus baseline, FWHM du pic, pour qualifier objectivement la détection.
- **Support d'autres techniques voltammétriques** — DPV (*Differential Pulse Voltammetry*), CV (*Cyclic Voltammetry*) : pipelines adaptés mais réutilisant le noyau de lissage / baseline.

---

## Contribuer

- Pour proposer une évolution non listée : ouvrir une *issue* sur le dépôt avec le label `enhancement`.
- Pour signaler un bug : ouvrir une *issue* avec le label `bug` et joindre un fichier `.txt` reproductible si possible.
- Les contributions externes (pull requests) sont les bienvenues — préférer une discussion préalable en issue pour les changements architecturaux.
