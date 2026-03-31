import os
from pathlib import Path
from datetime import date

# Carregar .env si existeix (sense dependències externes)
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

import storage
import extractor
import excel_generator
import productes as productes_mod
import conversa as conversa_mod

app = FastAPI(title="Parada Mercat — Comandes WhatsApp")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Models ────────────────────────────────────────────────────────────────────

class ExtreureRequest(BaseModel):
    missatge: str
    nom_client: str = ""

class Article(BaseModel):
    nom: str
    quantitat: float
    unitat: str

class ComandaRequest(BaseModel):
    client: str
    telefon: str = ""
    missatge_original: str = ""
    articles: list[Article]

class ConversaRequest(BaseModel):
    telefon: str
    missatge: str
    nom_client: str = ""

class ProducteRequest(BaseModel):
    nom: str
    preu: Optional[float] = None
    unitat: str = "kg"
    disponible: bool = True
    nota: str = ""

class ProducteUpdateRequest(BaseModel):
    preu: Optional[float] = None
    unitat: Optional[str] = None
    disponible: Optional[bool] = None
    nota: Optional[str] = None


# ── Pàgina principal ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# ── Extracció manual (pestanya Nova Comanda) ──────────────────────────────────

@app.post("/api/extreure")
def api_extreure(req: ExtreureRequest):
    if not req.missatge.strip():
        raise HTTPException(status_code=400, detail="El missatge no pot estar buit.")
    try:
        return extractor.extreure_comanda(req.missatge, req.nom_client)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ── Conversa WhatsApp (bot) ───────────────────────────────────────────────────

@app.post("/api/conversa")
def api_conversa(req: ConversaRequest):
    """
    Endpoint principal del bot.
    Rep un missatge d'un client i retorna la resposta de la IA.
    Si la conversa porta a una comanda confirmada, la guarda automàticament.
    """
    if not req.missatge.strip():
        raise HTTPException(status_code=400, detail="El missatge no pot estar buit.")
    if not req.telefon.strip():
        raise HTTPException(status_code=400, detail="Cal indicar el telèfon.")

    prod = productes_mod.obtenir_productes()
    try:
        resultat = conversa_mod.processar_missatge(
            telefon=req.telefon,
            missatge=req.missatge,
            nom_client=req.nom_client,
            productes=prod,
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Si la conversa ha generat una comanda, guardar-la automàticament
    comanda_guardada = None
    if resultat.get("comanda"):
        c = resultat["comanda"]
        comanda = {
            "client":            c.get("client") or req.nom_client or req.telefon,
            "telefon":           req.telefon,
            "missatge_original": req.missatge,
            "articles":          c.get("articles", []),
        }
        comanda_guardada = storage.guardar_comanda(comanda)

    return {
        "resposta":        resultat["resposta"],
        "comanda_guardada": comanda_guardada,
        "historial":       resultat["historial"],
    }

@app.delete("/api/conversa/{telefon}")
def api_netejar_conversa(telefon: str):
    """Reinicia la conversa d'un client concret."""
    conversa_mod.netejar_conversa(telefon)
    return {"ok": True}

@app.get("/api/converses")
def api_converses_actives():
    """Retorna les converses en curs (per a l'admin)."""
    return conversa_mod.obtenir_converses_actives()


# ── Comandes ──────────────────────────────────────────────────────────────────

@app.post("/api/comandes")
def api_guardar_comanda(req: ComandaRequest):
    comanda = {
        "client":            req.client,
        "telefon":           req.telefon,
        "missatge_original": req.missatge_original,
        "articles":          [a.model_dump() for a in req.articles],
    }
    return storage.guardar_comanda(comanda)

@app.get("/api/comandes")
def api_obtenir_comandes():
    return storage.obtenir_comandes_avui()

@app.delete("/api/comandes/{id}")
def api_eliminar_comanda(id: str):
    if not storage.eliminar_comanda(id):
        raise HTTPException(status_code=404, detail="Comanda no trobada.")
    return {"ok": True}

@app.delete("/api/comandes")
def api_netejar_comandes():
    storage.netejar_comandes_avui()
    return {"ok": True}


# ── Excel ─────────────────────────────────────────────────────────────────────

@app.get("/api/excel")
def api_excel():
    comandes = storage.obtenir_comandes_avui()
    if not comandes:
        raise HTTPException(status_code=404, detail="No hi ha comandes per avui.")
    try:
        path = excel_generator.generar_excel(comandes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generant l'Excel: {e}")
    nom_fitxer = f"comandes_{date.today().isoformat()}.xlsx"
    return FileResponse(
        path=path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nom_fitxer}"'},
    )


# ── Llista de divendres ───────────────────────────────────────────────────────

@app.get("/api/llista-divendres")
def api_llista_divendres():
    path = Path(__file__).parent / "llista_divendres.txt"
    if not path.exists():
        raise HTTPException(status_code=404, detail="llista_divendres.txt no trobat.")
    return {"text": path.read_text(encoding="utf-8").strip()}


# ── Productes ─────────────────────────────────────────────────────────────────

@app.get("/api/productes")
def api_obtenir_productes():
    return productes_mod.obtenir_productes()

@app.post("/api/productes")
def api_afegir_producte(req: ProducteRequest):
    llista = productes_mod.afegir_producte(req.model_dump())
    return llista

@app.patch("/api/productes/{nom}")
def api_actualitzar_producte(nom: str, req: ProducteUpdateRequest):
    camps = {k: v for k, v in req.model_dump().items() if v is not None}
    if not productes_mod.actualitzar_producte(nom, camps):
        raise HTTPException(status_code=404, detail="Producte no trobat.")
    return {"ok": True}

@app.delete("/api/productes/{nom}")
def api_eliminar_producte(nom: str):
    if not productes_mod.eliminar_producte(nom):
        raise HTTPException(status_code=404, detail="Producte no trobat.")
    return {"ok": True}

@app.put("/api/productes")
def api_desar_productes(productes: list[dict]):
    """Desa la llista completa de productes (per a l'editor massiu del frontend)."""
    productes_mod.desar_productes(productes)
    return {"ok": True}
