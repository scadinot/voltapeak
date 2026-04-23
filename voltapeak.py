"""
voltapeak — Analyse de voltampérogrammes SWV (Square Wave Voltammetry).

Ce module fournit une petite application Tkinter permettant de :

1. Charger un fichier texte à deux colonnes (Potentiel, Courant) issu d'une
   mesure de voltampérométrie à ondes carrées (SWV).
2. Lisser le signal par filtre de Savitzky-Golay afin d'atténuer le bruit
   haute fréquence sans trop déformer les pics.
3. Détecter le pic anodique brut (maximum du signal lissé, avec protection
   des bords et filtre de pente pour éviter les artefacts).
4. Estimer la ligne de base (« baseline ») par l'algorithme asPLS fourni
   par la bibliothèque `pybaselines`, en excluant la zone du pic du calcul
   afin de ne pas biaiser l'estimation.
5. Soustraire la ligne de base pour obtenir un signal corrigé, puis
   redétecter le pic sur ce signal corrigé.
6. Afficher l'ensemble (signal brut, lissé, baseline, corrigé, pic) dans
   une fenêtre matplotlib intégrée à la fenêtre Tkinter, avec la barre
   d'outils de navigation (zoom, pan, export PNG/PDF).

Format d'entrée attendu
-----------------------
Fichier `.txt`, encodage latin-1, première ligne ignorée (en-tête),
deux colonnes numériques (Potentiel en volts, Courant en ampères).
Le séparateur de colonnes et le séparateur décimal sont configurables
via l'interface.

Dépendances
-----------
- numpy, pandas : manipulation des données.
- scipy.signal.savgol_filter : lissage Savitzky-Golay.
- pybaselines.whittaker.aspls : correction de ligne de base asPLS.
- matplotlib (backend tkagg) : visualisation intégrée.
- tkinter : interface graphique (livrée avec Python).

Point d'entrée
--------------
Exécuter directement le module :

    python voltapeak.py

Voir aussi
----------
README.md et ROADMAP.md pour la documentation utilisateur et la feuille
de route d'évolution.
"""

# ---------------------------------------------------------------------------
# Imports — ordonnés par ruff/isort :
#   1) Bibliothèque standard (stdlib)
#   2) Bibliothèques tierces
#   Dans chaque groupe : `import X` avant `from X import Y`, tri alphabétique.
# ---------------------------------------------------------------------------

# Bibliothèque standard.
import os  # Extraction du nom de fichier, vérification d'existence.
from tkinter import Button, Frame, Label, StringVar, Tk, filedialog, messagebox, ttk

# Bibliothèques tierces — `import X as Y` d'abord, puis les `from X import Y`.
import matplotlib.pyplot as plt  # API pyplot pour construire la figure.
import numpy as np  # Calcul vectoriel (gradient, argmax, etc.).
import pandas as pd  # Lecture CSV/TXT, tri, filtrage par colonne.

# Canvas et barre d'outils matplotlib spécifiques au backend Tkinter :
# FigureCanvasTkAgg embarque une Figure matplotlib dans un widget Tk,
# NavigationToolbar2Tk fournit les boutons zoom/pan/export.
# Note : Pyright signale `NavigationToolbar2Tk` comme import privé (il est
# re-exporté depuis `_backend_tk`) ; cette forme d'import est pourtant la
# forme officielle documentée par matplotlib — on ignore la règle via
# la config `[tool.pyright]` de pyproject.toml.
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

# asPLS (Adaptive Smoothness Penalized Least Squares) : algorithme robuste
# d'estimation de ligne de base pénalisant la dérivée seconde, avec ajustement
# itératif des poids selon le signe du résidu.
from pybaselines.whittaker import aspls

# Savitzky-Golay : lissage polynomial local préservant la forme des pics.
from scipy.signal import savgol_filter


def readFile(filePath, sep, decimal) -> pd.DataFrame | None:
    """
    Charge un fichier texte SWV dans un DataFrame à deux colonnes.

    Le fichier est supposé contenir une ligne d'en-tête (ignorée) puis
    des lignes de deux colonnes numériques : potentiel et courant.

    Paramètres
    ----------
    filePath : str
        Chemin absolu ou relatif vers le fichier `.txt` à charger.
    sep : str
        Séparateur de colonnes attendu dans le fichier (``"\\t"``, ``","``,
        ``";"`` ou ``" "``), choisi par l'utilisateur dans l'interface.
    decimal : str
        Séparateur décimal attendu (``"."`` ou ``","``).

    Retourne
    -------
    pandas.DataFrame | None
        DataFrame à deux colonnes nommées ``"Potential"`` et ``"Current"``.
        La valeur ``None`` n'est jamais explicitement renvoyée dans
        l'implémentation actuelle, mais le type de retour laisse la porte
        ouverte à une future gestion d'erreur silencieuse.

    Notes
    -----
    L'encodage est figé à ``latin1`` car les fichiers d'origine
    proviennent de potentiostats francophones (accents, caractères
    étendus). Rendre cet encodage configurable est prévu en Vague 2
    du ROADMAP.
    """
    # Ouverture explicite du flux avec encodage latin-1 — les appareils de
    # mesure produisent souvent des en-têtes contenant des caractères non
    # ASCII (°C, µA, etc.) que UTF-8 refuserait.
    with open(filePath, encoding="latin1") as fileStream:
        # Lecture CSV via pandas :
        #   - skiprows=1      : saute la ligne d'en-tête du potentiostat.
        #   - usecols=[0, 1]  : ne garde que les deux premières colonnes
        #                       (les fichiers peuvent contenir des colonnes
        #                       parasites : index, timestamp, etc.).
        #   - names=[...]     : renomme les colonnes — on n'utilise pas
        #                       l'en-tête fichier, déjà sauté.
        #   - decimal         : gère les nombres à virgule européens.
        dataFrame = pd.read_csv(
            fileStream,
            sep=sep,
            skiprows=1,
            usecols=[0, 1],
            names=["Potential", "Current"],
            decimal=decimal,
        )
    return dataFrame


def processData(dataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Nettoie et oriente les données brutes pour l'analyse.

    Trois opérations sont enchaînées :

    1. Suppression des lignes où le courant est nul (points parasites).
    2. Tri par potentiel croissant (le fichier peut être en scan retour).
    3. Inversion du signe du courant : en SWV cathodique le courant
       mesuré est négatif, on le rend positif pour que la détection
       de pic par ``argmax`` trouve bien le sommet.

    Paramètres
    ----------
    dataFrame : pandas.DataFrame
        DataFrame issu de :func:`readFile`, colonnes ``"Potential"``
        et ``"Current"``.

    Retourne
    -------
    tuple[numpy.ndarray, numpy.ndarray]
        ``(potentialValues, signalValues)`` — deux tableaux 1-D alignés,
        triés par potentiel croissant.
    """
    # Filtrage des points à courant nul (souvent des lignes de garde en
    # début/fin de fichier) puis tri par potentiel croissant. reset_index
    # redonne un index 0..N-1 contigu après filtrage + tri.
    dataFrame = (
        dataFrame[dataFrame["Current"] != 0]
        .sort_values("Potential")
        .reset_index(drop=True)
    )
    # Extraction des colonnes sous forme de ndarray — plus efficace pour
    # les calculs numpy qui suivent et évite les accès pandas répétés.
    potentialValues = dataFrame["Potential"].values
    # Inversion de signe : convention SWV cathodique où le pic est un
    # minimum local ; on le transforme en maximum pour simplifier les
    # traitements aval (argmax, détection par seuil positif, etc.).
    signalValues = -dataFrame["Current"].values
    return potentialValues, signalValues


def smoothSignal(signalValues) -> np.ndarray:
    """
    Lisse le signal par filtre de Savitzky-Golay.

    Le lissage SG ajuste localement un polynôme de degré ``polyorder``
    sur une fenêtre glissante de largeur ``window_length``, ce qui
    atténue le bruit haute fréquence tout en préservant l'amplitude
    et la position des pics — contrairement à un simple moyennage.

    Paramètres
    ----------
    signalValues : numpy.ndarray
        Signal 1-D à lisser (déjà réorienté par :func:`processData`).

    Retourne
    -------
    numpy.ndarray
        Signal lissé, de même taille que l'entrée.

    Lève
    ----
    ValueError
        Si le signal contient moins de 5 points, ce qui rend tout
        lissage non significatif.

    Notes
    -----
    La fenêtre est adaptée à la taille du signal :

    - Valeur nominale : 11 points (bon compromis en SWV courante).
    - Plafonnée à la taille du signal (en restant impaire, contrainte
      de ``savgol_filter``).
    - Minimum absolu : 3 points (sinon le polynôme d'ordre 2 ne peut
      être ajusté).
    """
    n = len(signalValues)
    # Verrou de sûreté : en-dessous de 5 points, aucun lissage n'a de
    # sens statistique et savgol_filter lèverait de toute façon.
    if n < 5:
        raise ValueError("Trop peu de points pour lisser le signal.")
    # Fenêtre par défaut = 11 (valeur empirique pour SWV ~200-400 pts).
    # Si le signal est plus court, on prend la taille du signal en
    # s'assurant qu'elle reste impaire (contrainte de Savitzky-Golay).
    window_length = min(11, n if n % 2 == 1 else n - 1)
    # Garde-fou : la fenêtre doit être ≥ polyorder + 1 = 3.
    if window_length < 3:
        window_length = 3
    # polyorder=2 : parabole locale — préserve correctement la courbure
    # d'un pic gaussien/lorentzien sans l'aplatir.
    return savgol_filter(signalValues, window_length=window_length, polyorder=2)


def getPeakValue(signalValues, potentialValues, marginRatio=0.10, maxSlope=None) -> tuple[float, float]:
    """
    Détecte le pic (maximum) du signal avec deux heuristiques de robustesse.

    La recherche ignore les bords du signal (``marginRatio``) pour éviter
    les artefacts de démarrage/arrêt du potentiostat, et peut optionnellement
    filtrer les points à forte pente locale (``maxSlope``) qui correspondent
    typiquement à des fronts parasites plutôt qu'à un vrai sommet de pic.

    Paramètres
    ----------
    signalValues : numpy.ndarray
        Signal 1-D sur lequel chercher le maximum.
    potentialValues : numpy.ndarray
        Potentiels associés, même taille que ``signalValues``.
    marginRatio : float, optionnel
        Fraction du signal à exclure de chaque côté (défaut 0.10 = 10 %
        à gauche et 10 % à droite). Empêche de détecter un « pic » sur
        les artefacts de bord de scan.
    maxSlope : float | None, optionnel
        Pente maximale tolérée (en unité ``signal/potentiel``) au point
        candidat. Si ``None``, le filtre est désactivé. Sinon, seuls les
        points où ``|d signal / d potentiel| < maxSlope`` sont candidats.

    Retourne
    -------
    tuple[float, float]
        ``(xPeak, yPeak)`` — potentiel et amplitude du pic détecté.

    Notes
    -----
    En cas d'échec du filtre de pente (aucun point valide), la fonction
    retourne le premier point après la marge plutôt que de lever — c'est
    un choix de robustesse pour que l'UI ne plante pas sur un signal
    pathologique.
    """
    n = len(signalValues)
    # Nombre de points à exclure à chaque extrémité du signal.
    margin = int(n * marginRatio)
    # Sous-tableaux centrés : on ne cherchera le pic que dans cette zone.
    searchRegion = signalValues[margin:-margin]
    potentialsRegion = potentialValues[margin:-margin]

    if maxSlope is not None:
        # Dérivée numérique centrée du signal lissé par rapport au
        # potentiel — np.gradient gère correctement les pas non uniformes.
        slopes = np.gradient(searchRegion, potentialsRegion)
        # On ne garde que les indices où la pente est « plate » (sous seuil).
        # Un vrai sommet de pic a une pente proche de 0 ; un front parasite
        # a une pente élevée.
        validIndices = np.where(np.abs(slopes) < maxSlope)[0]
        # Aucun point ne passe le filtre : repli défensif sur le premier
        # point de la zone de recherche plutôt qu'une exception.
        if len(validIndices) == 0:
            return potentialValues[margin], signalValues[margin]
        # Parmi les points à faible pente, on prend celui d'amplitude max.
        bestIndex = validIndices[np.argmax(searchRegion[validIndices])]
        # Réindexation vers le tableau complet (décalage de margin).
        index = bestIndex + margin
    else:
        # Mode simple : maximum global de la zone centrale, sans filtre.
        indexInRegion = np.argmax(searchRegion)
        index = indexInRegion + margin
    return potentialValues[index], signalValues[index]


def calculateSignalBaseLine(
    signalValues,
    potentialValues,
    xPeakVoltage,
    exclusionWidthRatio=0.03,
    lambdaFactor=1e3,
) -> tuple[np.ndarray, tuple[float, float]]:
    """
    Estime la ligne de base par l'algorithme asPLS en excluant le pic.

    L'algorithme asPLS (Adaptive Smoothness Penalized Least Squares) ajuste
    une courbe lisse sous le signal en minimisant :

        ||W (y - z)||² + λ ||D² z||²

    où ``W`` est la matrice diagonale des poids, ``D²`` l'opérateur dérivée
    seconde et ``λ`` le facteur de lissage. Ici on force les poids à une
    valeur très faible (0.001) dans une fenêtre autour du pic détecté,
    afin que l'algorithme ne soit pas tiré vers le haut par le pic.

    Paramètres
    ----------
    signalValues : numpy.ndarray
        Signal lissé dont on veut extraire la ligne de base.
    potentialValues : numpy.ndarray
        Potentiels associés.
    xPeakVoltage : float
        Position (en volts) du pic brut, autour de laquelle on crée une
        zone d'exclusion.
    exclusionWidthRatio : float, optionnel
        Demi-largeur de la zone d'exclusion, exprimée en fraction de
        l'étendue totale de potentiel (défaut 0.03 = 3 %).
    lambdaFactor : float, optionnel
        Facteur multiplicatif du paramètre de lissage ``λ``. La valeur
        effective utilisée est ``lambdaFactor * n²`` où ``n`` est le
        nombre de points : cette mise à l'échelle rend le comportement
        à peu près invariant à la densité d'échantillonnage.

    Retourne
    -------
    tuple[numpy.ndarray, tuple[float, float]]
        - ``baselineValues`` : ligne de base estimée, même taille que
          l'entrée.
        - ``(exclusion_min, exclusion_max)`` : bornes (en volts) de la
          zone d'exclusion autour du pic, utile pour affichage/debug.

    Notes
    -----
    Les hyperparamètres ``tol=1e-2`` et ``max_iter=25`` passés à ``aspls``
    sont des compromis vitesse/précision adaptés aux signaux SWV typiques
    (quelques centaines de points). Les rendre configurables dans l'UI
    est prévu en Vague 3 du ROADMAP.
    """
    n = len(signalValues)
    # Mise à l'échelle du facteur de lissage par n² — heuristique usuelle
    # pour que λ ait le même effet perceptuel quelle que soit la taille
    # du signal (cf. documentation pybaselines).
    lam = lambdaFactor * (n ** 2)
    # Demi-largeur de la zone d'exclusion convertie depuis un ratio en
    # volts absolus (étendue du scan).
    exclusionWidth = exclusionWidthRatio * (potentialValues[-1] - potentialValues[0])

    # Poids initiaux tous à 1 (tous les points participent pleinement).
    weights = np.ones_like(potentialValues)
    # Bornes gauche/droite de la zone de pic à déprécier.
    exclusion_min = xPeakVoltage - exclusionWidth
    exclusion_max = xPeakVoltage + exclusionWidth
    # Les points dans la zone du pic reçoivent un poids très faible
    # (0.001) : ils contribuent peu au fit de la baseline, ce qui évite
    # que la courbe remonte vers le sommet du pic.
    weights[(potentialValues > exclusion_min) & (potentialValues < exclusion_max)] = 0.001

    # Appel à asPLS :
    #   - diff_order=2  : pénalise la dérivée seconde (courbure lisse).
    #   - tol=1e-2      : critère d'arrêt relatif des itérations de poids.
    #   - max_iter=25   : garde-fou contre les signaux pathologiques.
    # Le second retour (détails de convergence) est ignoré ici.
    # Note : `pybaselines` ne fournit pas de stubs de types ; Pylance infère
    # donc un retour potentiellement `None` et signale un faux positif sur
    # le dépaquetage. À l'exécution `aspls` renvoie bien un tuple
    # `(ndarray, dict)` — on ignore explicitement la règle sur cette ligne.
    baselineValues, _ = aspls(  # pyright: ignore[reportGeneralTypeIssues]
        signalValues,
        lam=lam,
        diff_order=2,
        weights=weights,
        tol=1e-2,
        max_iter=25,
    )
    return baselineValues, (exclusion_min, exclusion_max)


def plotSignalAnalysis(
    ax,
    potentialValues,
    signalValues,
    signalSmoothed,
    baseline,
    signalCorrected,
    xCorrectedVoltage,
    yCorrectedCurrent,
    fileName,
) -> None:
    """
    Trace l'ensemble des courbes d'analyse sur un axe matplotlib.

    Les cinq éléments affichés sont :

    1. Signal brut (faible opacité).
    2. Signal lissé (Savitzky-Golay).
    3. Ligne de base estimée (asPLS, tiretée).
    4. Signal corrigé (lissé - baseline).
    5. Pic corrigé marqué par un point magenta + trait vertical.

    Paramètres
    ----------
    ax : matplotlib.axes.Axes
        Axe sur lequel tracer. Son contenu est effacé au préalable.
    potentialValues, signalValues : numpy.ndarray
        Couples (x, y) du signal brut.
    signalSmoothed : numpy.ndarray
        Signal après Savitzky-Golay.
    baseline : numpy.ndarray
        Ligne de base estimée.
    signalCorrected : numpy.ndarray
        ``signalSmoothed - baseline``.
    xCorrectedVoltage, yCorrectedCurrent : float
        Coordonnées du pic détecté sur le signal corrigé.
    fileName : str
        Nom du fichier source, utilisé dans le titre du graphique.

    Retourne
    -------
    None
        La figure est modifiée en place, aucun retour.

    Notes
    -----
    Les tailles de police sont très petites (``fontsize=4``) car la
    figure est embarquée dans une fenêtre Tk de taille modeste ; un
    export via la toolbar produit un PNG où ces tailles redeviennent
    raisonnables.
    """
    # On repart d'un axe vierge à chaque rafraîchissement, sinon les
    # tracés précédents resteraient superposés.
    ax.clear()

    # --- Tracés des courbes (ordre = ordre de dessin, de bas en haut).
    ax.plot(potentialValues, signalValues, label="Signal brut", alpha=0.5, linewidth=0.8)
    ax.plot(potentialValues, signalSmoothed, label="Signal lissé", linewidth=1)
    ax.plot(potentialValues, baseline, label="Baseline estimée (asPLS)", linestyle='--', linewidth=1)
    ax.plot(potentialValues, signalCorrected, label="Signal corrigé", linewidth=1.5)

    # Marqueur du pic corrigé — point magenta + libellé avec valeur numérique.
    # Le courant est converti en milliampères (× 1e3) pour la lisibilité.
    ax.plot(
        xCorrectedVoltage,
        yCorrectedCurrent,
        'mo',
        markersize=5,
        label=f"Pic corrigé à {xCorrectedVoltage:.3f} V ({yCorrectedCurrent*1e3:.3f} mA)",
    )
    # Trait vertical pointillé pour repérer visuellement la position du pic.
    ax.axvline(xCorrectedVoltage, color='magenta', linestyle=':', linewidth=1)

    # --- Mise en forme de l'axe (polices réduites : cf. docstring).
    ax.set_xlabel("Potentiel (V)", fontsize=4)
    ax.set_ylabel("Courant (A)", fontsize=4)
    ax.set_title(f"Correction de baseline : {fileName}", fontsize=4)
    ax.legend(fontsize=4)
    ax.grid(True)

    # Labels des graduations également en petit.
    ax.tick_params(axis='both', labelsize=4)
    # Ajustement automatique des marges pour éviter que les libellés
    # ne soient coupés par les bords de la figure.
    plt.tight_layout()


def processAndPlotSingleFile(filePath, sep, decimal, ax, canvas):
    """
    Pipeline complet : lecture + traitements + tracé + rafraîchissement.

    Cette fonction orchestre toutes les étapes scientifiques dans l'ordre
    attendu et déclenche le redessin du canvas Tk. Toute exception est
    capturée et affichée dans une boîte de dialogue pour ne pas faire
    planter l'interface.

    Paramètres
    ----------
    filePath : str
        Chemin du fichier `.txt` sélectionné par l'utilisateur.
    sep : str
        Séparateur de colonnes (cf. :func:`readFile`).
    decimal : str
        Séparateur décimal (cf. :func:`readFile`).
    ax : matplotlib.axes.Axes
        Axe cible du tracé, passé par l'UI parente.
    canvas : matplotlib.backends.backend_tkagg.FigureCanvasTkAgg
        Canvas Tk à rafraîchir après tracé.

    Retourne
    -------
    None

    Notes
    -----
    L'enchaînement ci-dessous est le cœur métier de l'application :

    1. ``readFile`` → DataFrame brut.
    2. ``processData`` → arrays alignés et orientés.
    3. ``smoothSignal`` → débruitage SG.
    4. ``getPeakValue`` (brut) → position approximative du pic.
    5. ``calculateSignalBaseLine`` → baseline asPLS avec exclusion.
    6. Soustraction baseline → signal corrigé.
    7. ``getPeakValue`` (corrigé) → pic définitif affiché.
    8. ``plotSignalAnalysis`` → tracé final.
    9. ``canvas.draw()`` → rafraîchissement visuel.
    """
    try:
        # Nom seul du fichier (sans répertoire) pour le titre du graphe.
        fileName = os.path.basename(filePath)

        # Étape 1 — lecture du fichier brut.
        dataFrame = readFile(filePath, sep=sep, decimal=decimal)
        if dataFrame is None:
            # Cas défensif : readFile pourrait un jour renvoyer None.
            messagebox.showerror("Erreur", f"Fichier invalide : {fileName}")
            return

        # Étape 2 — nettoyage et orientation.
        potentialValues, signalValues = processData(dataFrame)

        # Étape 3 — lissage Savitzky-Golay.
        signalSmoothed = smoothSignal(signalValues)

        # Étape 4 — détection du pic sur le signal lissé, avec filtre de
        # pente (maxSlope=500) pour ignorer les fronts parasites. Seule
        # l'abscisse du pic nous intéresse ici (elle sert à caler la zone
        # d'exclusion de la baseline) ; l'amplitude est ignorée via `_`.
        xPeakVoltage, _ = getPeakValue(
            signalSmoothed,
            potentialValues,
            marginRatio=0.10,
            maxSlope=500,
        )

        # Étape 5 — estimation de la ligne de base en excluant la zone
        # du pic identifiée précédemment.
        baseline, _ = calculateSignalBaseLine(
            signalSmoothed,
            potentialValues,
            xPeakVoltage,
            exclusionWidthRatio=0.03,
            lambdaFactor=1e3,
        )

        # Étape 6 — signal corrigé = lissé − baseline.
        signalCorrected = signalSmoothed - baseline

        # Étape 7 — nouvelle détection de pic sur le signal corrigé.
        # C'est ce pic-là qui est affiché à l'utilisateur (plus fiable
        # que le pic brut car l'effet de baseline est enlevé).
        xCorrectedVoltage, yCorrectedCurrent = getPeakValue(
            signalCorrected,
            potentialValues,
            marginRatio=0.10,
            maxSlope=500,
        )

        # Étape 8 — tracé de toutes les courbes dans l'axe fourni.
        plotSignalAnalysis(
            ax,
            potentialValues,
            signalValues,
            signalSmoothed,
            baseline,
            signalCorrected,
            xCorrectedVoltage,
            yCorrectedCurrent,
            fileName,
        )

        # Étape 9 — forcer le redessin du canvas Tk (sinon la figure
        # matplotlib reste inchangée visuellement).
        canvas.draw()
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Filet de sécurité global : on capture volontairement toute
        # exception (IO, parsing pandas, erreur numpy, divergence asPLS,
        # problème Tk…) pour la remonter à l'utilisateur via une boîte
        # de dialogue plutôt que de tuer l'application. Le warning Pylint
        # `broad-exception-caught` est donc volontairement ignoré ici.
        messagebox.showerror("Erreur", f"Une erreur est survenue : {e}")


def launch_gui():
    """
    Construit et lance l'interface graphique Tkinter.

    La fenêtre contient :

    - Un champ d'affichage du fichier sélectionné + bouton « Parcourir ».
    - Un groupe de boutons radio pour choisir le séparateur de colonnes.
    - Un groupe de boutons radio pour choisir le séparateur décimal.
    - Une zone graphique matplotlib embarquée avec sa barre d'outils
      (zoom, pan, sauvegarde PNG/PDF).

    Le clic sur « Parcourir » déclenche successivement :

    1. ``select_file`` : ouvre une boîte de dialogue de choix de fichier.
    2. ``run_single_analysis`` : si un fichier est choisi, lance tout le
       pipeline via :func:`processAndPlotSingleFile`.

    Retourne
    -------
    None
        La fonction ne rend la main qu'à la fermeture de la fenêtre
        (``root.mainloop()`` est bloquant).
    """

    def select_file():
        """Ouvre une boîte de dialogue et mémorise le chemin choisi."""
        # askopenfilename retourne "" si l'utilisateur annule — on ne
        # réaffecte donc file_path que si un chemin non vide est renvoyé.
        path = filedialog.askopenfilename(
            title="Sélectionnez un fichier .txt",
            filetypes=[("Fichiers texte", "*.txt")],
        )
        if path:
            file_path.set(path)

    def run_single_analysis():
        """Valide la sélection utilisateur puis lance le pipeline."""
        selected_file = file_path.get()
        # Double vérification : la StringVar peut contenir un chemin
        # obsolète si l'utilisateur a déplacé/supprimé le fichier entre
        # deux clics.
        if not selected_file or not os.path.isfile(selected_file):
            messagebox.showerror("Erreur", "Veuillez sélectionner un fichier valide.")
            return

        # Traduction du libellé de bouton radio vers le caractère
        # séparateur réel attendu par pandas.read_csv.
        sep_label = sep_var.get()
        sep_map = {
            "Tabulation": "\t",
            "Virgule": ",",
            "Point-virgule": ";",
            "Espace": " ",
        }
        # Valeur par défaut = tabulation si jamais le libellé est inconnu.
        sep = sep_map.get(sep_label, "\t")

        # Même principe pour le séparateur décimal.
        decimal_label = decimal_var.get()
        decimal_map = {
            "Point": ".",
            "Virgule": ",",
        }
        decimal = decimal_map.get(decimal_label, ".")

        # Délégation au pipeline scientifique + UI.
        processAndPlotSingleFile(selected_file, sep, decimal, ax, canvas)

    # ------------------------------------------------------------------
    # --- Construction de la fenêtre principale Tk.
    # ------------------------------------------------------------------
    root = Tk()
    root.title("Affichage d'un fichier SWV")
    # Taille initiale confortable pour afficher la figure matplotlib.
    root.geometry("1000x700")
    # Interdit de rendre la fenêtre trop petite pour que l'UI reste lisible.
    root.minsize(800, 500)

    # StringVar = variable Tk observable, liée aux widgets. Toute
    # modification déclenche un redessin automatique des Label associés.
    file_path = StringVar()
    sep_options = ["Tabulation", "Virgule", "Point-virgule", "Espace"]
    decimal_options = ["Point", "Virgule"]

    # Valeurs par défaut (les plus courantes pour les fichiers Autolab/
    # VersaSTAT côté GROUPE TRACE).
    sep_var = StringVar(value="Tabulation")
    decimal_var = StringVar(value="Point")

    # ------------------------------------------------------------------
    # --- Cadre principal occupant toute la fenêtre, géré en grille.
    # ------------------------------------------------------------------
    main_frame = Frame(root, padx=10, pady=10)
    main_frame.grid(row=0, column=0, sticky="nsew")
    # On rend la cellule (0, 0) de root extensible — sans ça le Frame
    # ne grandit pas avec la fenêtre.
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    # --- Ligne 0 : label + chemin fichier + bouton Parcourir.
    Label(main_frame, text="Fichier d'entrée :").grid(row=0, column=0, sticky="w")
    # relief="sunken" + anchor="w" : ressemble à un champ en lecture seule.
    Label(main_frame, textvariable=file_path, relief="sunken", anchor="w", width=70).grid(
        row=0, column=1, padx=5, sticky="ew"
    )
    # Le bouton enchaîne sélection puis analyse en une seule action
    # utilisateur (pas besoin de second bouton « Analyser »).
    Button(
        main_frame,
        text="Parcourir",
        command=lambda: [select_file(), run_single_analysis()],
    ).grid(row=0, column=2, padx=5)

    # ------------------------------------------------------------------
    # --- Ligne 1 : groupe de paramètres (séparateurs).
    # ------------------------------------------------------------------
    settings_frame = ttk.LabelFrame(main_frame, text="Paramètres de lecture")
    settings_frame.grid(row=1, column=0, columnspan=3, pady=(10, 5), sticky="ew")

    # Séparateur de colonnes : radio buttons horizontaux.
    Label(settings_frame, text="Séparateur de colonnes :").grid(row=0, column=0, sticky="w")
    sep_radio_frame = Frame(settings_frame)
    sep_radio_frame.grid(row=0, column=1, columnspan=4, sticky="w")
    # Boucle de création : un Radiobutton par libellé, tous liés à sep_var.
    for i, txt in enumerate(sep_options):
        ttk.Radiobutton(sep_radio_frame, text=txt, variable=sep_var, value=txt).grid(
            row=0, column=i, sticky="w", padx=(0, 10)
        )

    # Séparateur décimal : même structure, sur la ligne suivante.
    Label(settings_frame, text="Séparateur décimal :").grid(row=1, column=0, sticky="w")
    dec_radio_frame = Frame(settings_frame)
    dec_radio_frame.grid(row=1, column=1, columnspan=4, sticky="w")
    for i, txt in enumerate(decimal_options):
        ttk.Radiobutton(dec_radio_frame, text=txt, variable=decimal_var, value=txt).grid(
            row=0, column=i, sticky="w", padx=(0, 10)
        )

    # ------------------------------------------------------------------
    # --- Zone de prévisualisation du graphique matplotlib.
    # ------------------------------------------------------------------
    # Une Figure matplotlib + son axe (unique). figsize est volontairement
    # modeste car le widget Tk l'étire ensuite via sticky="nsew".
    fig, ax = plt.subplots(figsize=(5, 3.5))
    # FigureCanvasTkAgg : pont entre matplotlib et Tk, fournit un widget Tk
    # contenant la figure — on le récupère via get_tk_widget().
    canvas = FigureCanvasTkAgg(fig, master=main_frame)
    canvas.get_tk_widget().grid(row=4, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")

    # Barre d'outils matplotlib (zoom, pan, reset, sauvegarde). Elle doit
    # vivre dans son propre Frame pour que son layout interne (pack) ne
    # rentre pas en conflit avec le grid du parent.
    toolbar_frame = Frame(main_frame)
    toolbar_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=5, pady=(5, 0))
    toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
    toolbar.update()

    # Configuration d'expansion : la ligne 4 (canvas) et la colonne 1
    # (champ fichier) absorbent tout espace disponible au redimensionnement.
    main_frame.grid_rowconfigure(4, weight=1)
    main_frame.grid_columnconfigure(1, weight=1)

    # Boucle d'événements Tk — bloquante jusqu'à fermeture de la fenêtre.
    root.mainloop()


def main():
    """Point d'entrée logique : lance l'interface graphique."""
    launch_gui()


# ---------------------------------------------------------------------------
# Point d'entrée effectif : exécution directe `python voltapeak.py`.
# Le garde ``if __name__ == '__main__'`` permet aussi d'importer le module
# (`import voltapeak`) sans déclencher l'UI — utile pour tests futurs.
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    main()
