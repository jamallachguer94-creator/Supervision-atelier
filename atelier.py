"""Supervision d'un atelier : référentiel des machines, relevés capteurs, alertes et rapport."""
import csv
import json
import math
import re
from datetime import datetime
from pathlib import Path

from exceptions import FichierInvalide, ReleveInvalide

COLONNES = ("machine", "horodatage", "temperature", "vibration")

# Un relevé valide est un tuple : (machine, horodatage, temperature, vibration)
Releve = tuple[str, datetime, float, float]
# --- Étape 1 : le référentiel des machines (JSON, dictionnaires, ensembles) --------------------
def charger_machines(chemin: Path) -> dict[str, dict]:
    with open(chemin, encoding="utf-8") as f:
        fiches = json.load(f)

    machines = {}

    for fiche in fiches:
        identifiant = fiche["id"]

        if identifiant in machines:
            raise FichierInvalide(
                f"identifiant en double : {identifiant}"
            )

        machines[identifiant] = fiche

    return machines
# --- Étape 2 : Les exceptions du projet 10 -------------------------------------------
def ateliers(machines: dict[str, dict]) -> set[str]:
    """L'ensemble des ateliers où se trouvent les machines."""
    return {fiche["atelier"] for fiche in machines.values()}
# --- Étape 3 : valider une ligne (exceptions, tuples) -------------------------------------------
def lire_nombre(texte: str, champ: str, numero: int) -> float:
    """Convertit une valeur textuelle en nombre réel valide."""

    texte = texte.strip()

    if not texte:
        raise ReleveInvalide("valeur manquante", numero, champ)

    try:
        valeur = float(texte.replace(",", "."))
    except ValueError:
        raise ReleveInvalide(
            f"non numérique : '{texte}'", numero, champ
        )

    if not math.isfinite(valeur):
        raise ReleveInvalide("non finie", numero, champ)

    return valeur
def parser_releve(brut: dict[str, str], numero: int, machines: dict[str, dict]) -> Releve:
    """Transforme une ligne brute du CSV en relevé typé."""

    machine = (brut.get("machine") or "").strip().upper()

    if not machine:
        raise ReleveInvalide("valeur manquante", numero, "machine")

    if machine not in machines:
        raise ReleveInvalide(
            f"machine inconnue : '{machine}'", numero, "machine"
        )

    texte_date = (brut.get("horodatage") or "").strip()

    if not texte_date:
        raise ReleveInvalide("valeur manquante", numero, "horodatage")

    try:
        horodatage = datetime.fromisoformat(texte_date)
    except ValueError:
        raise ReleveInvalide(
            f"date invalide : '{texte_date}'", numero, "horodatage"
        )

    temperature = lire_nombre(
        brut.get("temperature") or "", "temperature", numero
    )

    vibration = lire_nombre(
        brut.get("vibration") or "", "vibration", numero
    )

    if vibration < 0:
        raise ReleveInvalide(
            "valeur négative", numero, "vibration"
        )

    return (machine, horodatage, temperature, vibration)
    """Transforme une ligne brute du CSV (dictionnaire de textes) en relevé typé.

    Lève ReleveInvalide (avec le numéro de ligne et le champ fautif) au premier problème.
    """
    raise NotImplementedError("à compléter")
# --- Étape 4 : lire le fichier (CSV, générateur, collecte des erreurs) ---------------------------
def lignes_csv(chemin: Path):
    """Générateur de lignes CSV avec numérotation."""

    with open(chemin, encoding="utf-8-sig", newline="") as f:
        lecteur = csv.DictReader(f, delimiter=";")

        manquantes = [col for col in COLONNES if col not in (lecteur.fieldnames or [])]

        if manquantes:
            raise FichierInvalide(
                f"colonnes manquantes : {', '.join(manquantes)}"
            )

        for numero, brut in enumerate(lecteur, start=2):
            yield numero, brut
def lire_releves(chemin: Path, machines: dict[str, dict]) -> tuple[list[Releve], list[ReleveInvalide]]:
    """Lit les relevés et collecte les lignes invalides."""

    releves = []
    erreurs = []

    for numero, brut in lignes_csv(chemin):
        try:
            releve = parser_releve(brut, numero, machines)
            releves.append(releve)
        except ReleveInvalide as err:
            erreurs.append(err)

    return releves, erreurs
def ecrire_rejets(erreurs: list[ReleveInvalide], chemin: Path) -> None:
    """Écrit les lignes rejetées dans un CSV."""

    with open(chemin, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";")

        writer.writerow(["ligne", "champ", "message"])

        for err in erreurs:
            writer.writerow([err.ligne, err.champ, err.message])
# --- Étape 5 : analyser (dictionnaires, compréhensions) ------------------------------------------
def par_machine(releves: list[Releve]) -> dict[str, list[Releve]]:
    """Regroupe les relevés par machine."""

    groupes = {}

    for releve in releves:
        machine = releve[0]
        groupes.setdefault(machine, []).append(releve)

    return groupes
def moyennes(releves: list[Releve]) -> dict[str, tuple[float, float]]:
    """Calcule les moyennes de température et de vibration."""

    return {
        machine: (
            round(sum(r[2] for r in liste) / len(liste), 1),
            round(sum(r[3] for r in liste) / len(liste), 2)
        )
        for machine, liste in par_machine(releves).items()
    }
def alertes(releves: list[Releve], machines: dict[str, dict]) -> list[tuple[str, datetime, str]]:
    """Détecte les dépassements de seuil."""

    alertes_temperature = [
        (machine, horodatage,
         f"température {temperature} > {machines[machine]['temp_max']}")
        for machine, horodatage, temperature, vibration in releves
        if temperature > machines[machine]["temp_max"]
    ]

    alertes_vibration = [
        (machine, horodatage,
         f"vibration {vibration} > {machines[machine]['vib_max']}")
        for machine, horodatage, temperature, vibration in releves
        if vibration > machines[machine]["vib_max"]
    ]

    return sorted(
        alertes_temperature + alertes_vibration,
        key=lambda a: (a[1], a[0])
    )
def machines_silencieuses(releves: list[Releve], machines: dict[str, dict]) -> set[str]:
    """Retourne les machines sans relevé valide."""

    machines_actives = {releve[0] for releve in releves}

    return set(machines) - machines_actives
# --- Étape 6 : trier ---------------------------------------------------------------------------
def classement(releves: list[Releve], machines: dict[str, dict]) -> list[tuple[str, int]]:
    """Classe toutes les machines par nombre d'alertes décroissant."""

    compteurs = {m: 0 for m in machines}

    for machine, horodatage, motif in alertes(releves, machines):
        compteurs[machine] += 1

    return sorted(
        compteurs.items(),
        key=lambda item: (-item[1], item[0])
    )
def top_vibrations(releves: list[Releve], n: int = 3) -> list[Releve]:
    """Retourne les n relevés avec les vibrations les plus élevées."""

    return sorted(releves, key=lambda r: r[3], reverse=True)[:n]
# --- Étape 7 : le rapport JSON ------------------------------------------------------------------
def construire_rapport(releves: list[Releve], erreurs: list[ReleveInvalide], machines: dict[str, dict]) -> dict:
    """Construit le rapport final sous forme de dictionnaire JSON."""

    moyennes_calculees = moyennes(releves)

    moyennes_json = {
        machine: {
            "temperature": valeurs[0],
            "vibration": valeurs[1]
        }
        for machine, valeurs in sorted(moyennes_calculees.items())
    }

    alertes_json = [
        {
            "machine": machine,
            "heure": horodatage.strftime("%H:%M"),
            "motif": motif
        }
        for machine, horodatage, motif in alertes(releves, machines)
    ]

    classement_json = [
        machine
        for machine, nombre in classement(releves, machines)
        if nombre > 0
    ]

    return {
        "releves_valides": len(releves),
        "lignes_rejetees": len(erreurs),
        "moyennes": moyennes_json,
        "alertes": alertes_json,
        "classement": classement_json,
        "machines_silencieuses": sorted(
            machines_silencieuses(releves, machines)
        )
    }


def ecrire_rapport(rapport: dict, chemin: Path) -> None:
    """Écrit le rapport au format JSON."""

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)
# --- Étape 8 (à la maison) : le journal des événements (expressions régulières) ------------------
MOTIF_EVENEMENT = re.compile(r"à compléter")   # étape 8
def lire_evenements(chemin: Path):
    """Générateur : un dictionnaire par ligne valide du journal, les lignes mal formées sont sautées.

    Clés : machine, type, code, heure, duree (entier en minutes, ou None si absente).
    """
    raise NotImplementedError("à compléter")
def temps_arret(evenements) -> dict[str, int]:
    """Durée totale des ARRET par machine, en minutes."""
    raise NotImplementedError("à compléter")
