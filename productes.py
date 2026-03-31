import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
PRODUCTES_FILE = DATA_DIR / "productes.json"

PRODUCTES_DEFAULT = [
    {"nom": "peres conference",   "preu": 1.50, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "pomes golden",       "preu": 1.80, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "pomes fuji",         "preu": 2.00, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "taronges",           "preu": 1.20, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "mandarines",         "preu": 1.40, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "llimones",           "preu": 1.00, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "plàtans",            "preu": 1.60, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "raïm",               "preu": 2.50, "unitat": "kg",      "disponible": False, "nota": "Fora de temporada"},
    {"nom": "maduixes",           "preu": 3.00, "unitat": "kg",      "disponible": False, "nota": "Fins la setmana que ve"},
    {"nom": "tomàquets",          "preu": 2.00, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "tomàquets cherry",   "preu": 2.80, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "patates",            "preu": 0.80, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "cebes",              "preu": 0.90, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "alls",               "preu": 0.50, "unitat": "cap",     "disponible": True,  "nota": ""},
    {"nom": "enciam",             "preu": 1.00, "unitat": "unitat",  "disponible": True,  "nota": ""},
    {"nom": "espinacs",           "preu": 1.50, "unitat": "manat",   "disponible": True,  "nota": ""},
    {"nom": "bròquil",            "preu": 1.20, "unitat": "unitat",  "disponible": True,  "nota": ""},
    {"nom": "coliflor",           "preu": 1.50, "unitat": "unitat",  "disponible": False, "nota": "Fins dimecres"},
    {"nom": "carbassó",           "preu": 1.30, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "albergínies",        "preu": 1.80, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "pebrots vermells",   "preu": 2.20, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "pebrots verds",      "preu": 1.60, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "mongetes tendres",   "preu": 2.50, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "pastanagues",        "preu": 0.90, "unitat": "kg",      "disponible": True,  "nota": ""},
    {"nom": "ous",                "preu": 3.20, "unitat": "dotzena", "disponible": True,  "nota": "Ous de pagès"},
]


def _ensure():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not PRODUCTES_FILE.exists():
        PRODUCTES_FILE.write_text(
            json.dumps(PRODUCTES_DEFAULT, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def obtenir_productes() -> list:
    _ensure()
    try:
        return json.loads(PRODUCTES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return list(PRODUCTES_DEFAULT)


def desar_productes(productes: list):
    _ensure()
    PRODUCTES_FILE.write_text(
        json.dumps(productes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def actualitzar_producte(nom: str, camps: dict) -> bool:
    """Actualitza els camps d'un producte existent (cerca per nom)."""
    productes = obtenir_productes()
    for p in productes:
        if p["nom"].lower() == nom.lower():
            p.update(camps)
            desar_productes(productes)
            return True
    return False


def afegir_producte(producte: dict) -> list:
    productes = obtenir_productes()
    productes.append(producte)
    desar_productes(productes)
    return productes


def eliminar_producte(nom: str) -> bool:
    productes = obtenir_productes()
    nous = [p for p in productes if p["nom"].lower() != nom.lower()]
    if len(nous) == len(productes):
        return False
    desar_productes(nous)
    return True
