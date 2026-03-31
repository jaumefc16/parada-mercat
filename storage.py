import json
import os
import uuid
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_FILE = DATA_DIR / "comandes.json"


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text("[]", encoding="utf-8")


def _llegir_totes() -> list:
    _ensure_data_dir()
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _escriure_totes(comandes: list):
    _ensure_data_dir()
    DATA_FILE.write_text(json.dumps(comandes, ensure_ascii=False, indent=2), encoding="utf-8")


def guardar_comanda(comanda: dict) -> dict:
    comandes = _llegir_totes()
    now = datetime.now()
    comanda["id"] = str(uuid.uuid4())
    comanda["data"] = date.today().isoformat()
    comanda["hora"] = now.strftime("%H:%M")
    comandes.append(comanda)
    _escriure_totes(comandes)
    return comanda


def obtenir_comandes_avui() -> list:
    avui = date.today().isoformat()
    return [c for c in _llegir_totes() if c.get("data") == avui]


def obtenir_totes_comandes() -> list:
    return _llegir_totes()


def eliminar_comanda(id: str) -> bool:
    comandes = _llegir_totes()
    noves = [c for c in comandes if c.get("id") != id]
    if len(noves) == len(comandes):
        return False
    _escriure_totes(noves)
    return True


def netejar_comandes_avui():
    avui = date.today().isoformat()
    comandes = [c for c in _llegir_totes() if c.get("data") != avui]
    _escriure_totes(comandes)
