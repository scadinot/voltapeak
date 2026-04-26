"""
voltapeak
=========

Application Python / Tkinter d'analyse de voltampérogrammes SWV avec
correction automatique de la ligne de base par l'algorithme asPLS et
détection robuste du pic anodique.

Le code métier (lecture de fichier, lissage Savitzky-Golay, détection
de pic, baseline asPLS, GUI Tkinter) tient en un seul module
:mod:`voltapeak.__main__` lancé par ``python -m voltapeak`` depuis le
dossier parent.

Ce ``__init__.py`` se contente d'exposer la version du paquet — il
n'effectue aucun effet de bord (pas de lancement de GUI à l'import).
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
