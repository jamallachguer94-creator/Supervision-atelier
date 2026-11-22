"""Programme principal de supervision de l'atelier."""

from pathlib import Path

from atelier import (
    charger_machines,
    construire_rapport,
    ecrire_rapport,
    ecrire_rejets,
    lire_releves,
    classement,
    alertes,
    machines_silencieuses,
)
from exceptions import AtelierError

ICI = Path(__file__).parent
DONNEES = ICI / "donnees"
SORTIES = ICI / "sorties"


def main() -> int:
    """Renvoie 0 si tout s'est bien passé, 1 si un fichier est inutilisable."""

    try:
        machines = charger_machines(DONNEES / "machines.json")
        releves, erreurs = lire_releves(
            DONNEES / "releves.csv", machines
        )

    except (AtelierError, FileNotFoundError) as err:
        print(f"Erreur : {err}")
        return 1

    SORTIES.mkdir(exist_ok=True)

    ecrire_rejets(erreurs, SORTIES / "rejets.csv")

    rapport = construire_rapport(releves, erreurs, machines)
    ecrire_rapport(rapport, SORTIES / "rapport.json")

    classement_machines = [
        machine
        for machine, nombre in classement(releves, machines)
        if nombre > 0
    ]

    silencieuses = sorted(
        machines_silencieuses(releves, machines)
    )

    print(
        f"{len(releves)} relevés valides, "
        f"{len(erreurs)} lignes rejetées"
    )

    print(
        f"{len(alertes(releves, machines))} alertes ; "
        f"machines à surveiller : {', '.join(classement_machines)}"
    )

    print(f"Sans relevé : {', '.join(silencieuses)}")

    print(
        "Fichiers écrits dans sorties/ : "
        "rejets.csv, rapport.json"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
