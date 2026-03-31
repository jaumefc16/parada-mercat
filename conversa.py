"""
Gestió de converses multi-torn amb Claude. v2

Cada client (identificat pel telèfon) té el seu historial de conversa.
Quan Claude detecta una comanda confirmada, insereix un marcador especial
que aquest mòdul extreu i retorna com a objecte 'comanda'.
"""

import os
import json
import anthropic
from datetime import datetime, timedelta

# Historial en memòria: { telefon: { "messages": [...], "last_activity": datetime, "nom": str } }
_histories: dict = {}

# Temps d'inactivitat màxim abans de reiniciar la conversa
TIMEOUT_MINUTS = 45


# ── System prompt ─────────────────────────────────────────────────────────────

def _construir_system_prompt(productes: list) -> str:
    disponibles    = [p for p in productes if p.get("disponible", True)]
    no_disponibles = [p for p in productes if not p.get("disponible", True)]

    def formatar(p):
        parts = [f"*{p['nom']}*"]
        if p.get("preu"):
            parts.append(f"{p['preu']}€/{p['unitat']}")
        if p.get("nota"):
            parts.append(f"({p['nota']})")
        return " — ".join(parts)

    linia_disp    = "\n".join(f"  • {formatar(p)}" for p in disponibles)    or "  (cap)"
    linia_no_disp = "\n".join(f"  • {formatar(p)}" for p in no_disponibles) or "  (cap)"

    return f"""Ets l'assistent de WhatsApp d'una parada de fruita i verdura al mercat municipal.
Et diuen "La Parada". Ets amable, proper i eficient, com un venedor real.

═══ PRODUCTES DISPONIBLES AVUI ═══
{linia_disp}

═══ PRODUCTES NO DISPONIBLES ═══
{linia_no_disp}

═══ INSTRUCCIONS ═══
- Respon en el mateix idioma que el client (català, castellà, anglès…).
- Sigues breu i natural, com si fos un WhatsApp real. Màxim 3-4 línies per resposta.
- Pots informar sobre preus, disponibilitat, temporada i alternatives.
- Si un producte no és disponible, dis-ho i suggereix alternatives si n'hi ha.
- No inventes productes que no estiguin a la llista.
- Pren nota mentalment de tot el que el client va demanant al llarg de la conversa.
- Quan el client indiqui que ja ha acabat (digui "gràcies", "ja és tot", "res més",
  "perfecte", "d'acord", o confirmi la comanda), redacta un resum de la comanda
  i afegeix AL FINAL del missatge, en una línia sola, el marcador (sense espais addicionals):
  [COMANDA:{{"client":"nom o buit","articles":[{{"nom":"...","quantitat":0.0,"unitat":"..."}}]}}]
- No tornis a posar el marcador si ja l'has posat en un missatge anterior.
- Si el client no ha demanat res concret, NO posis el marcador.
"""


# ── Processament principal ────────────────────────────────────────────────────

def processar_missatge(telefon: str, missatge: str, nom_client: str, productes: list) -> dict:
    """
    Processa un missatge dins d'una conversa multi-torn.

    Retorna:
        {
            "resposta":  str,          # text a enviar al client
            "comanda":   dict | None,  # comanda extreta si s'ha confirmat
            "historial": int           # nombre de missatges en la conversa
        }
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY no configurada.")

    _netejar_inactives()

    # Obtenir o crear historial per a aquest telèfon
    if telefon not in _histories:
        _histories[telefon] = {"messages": [], "last_activity": datetime.now(), "nom": nom_client}
    hist = _histories[telefon]
    hist["last_activity"] = datetime.now()
    if nom_client and not hist.get("nom"):
        hist["nom"] = nom_client

    # Afegir missatge del client
    hist["messages"].append({"role": "user", "content": missatge})

    # Cridar Claude
    ai = anthropic.Anthropic(api_key=api_key)
    try:
        resp = ai.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            system=_construir_system_prompt(productes),
            messages=hist["messages"],
        )
        resposta_text = resp.content[0].text.strip()
    except Exception as e:
        hist["messages"].pop()  # revertir si falla
        raise ValueError(f"Error de la IA: {e}")

    # Guardar resposta a l'historial
    hist["messages"].append({"role": "assistant", "content": resposta_text})

    # Detectar marcador de comanda
    comanda = _extreure_comanda(resposta_text)
    if comanda is not None:
        # Afegir nom del client si no ve al marcador
        if not comanda.get("client") and hist.get("nom"):
            comanda["client"] = hist["nom"]
        # Netejar la conversa un cop confirmada la comanda
        del _histories[telefon]
        # Netejar el marcador del text visible
        idx_marker = resposta_text.find("[COMANDA:")
        resposta_text = resposta_text[:idx_marker].strip()

    return {
        "resposta":  resposta_text,
        "comanda":   comanda,
        "historial": len(hist["messages"]) if telefon in _histories else 0,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extreure_comanda(text: str) -> dict | None:
    """Extreu el JSON de comanda del marcador [COMANDA:{...}]."""
    marker = "[COMANDA:"
    if marker not in text:
        return None
    try:
        idx_s = text.index(marker) + len(marker)
        obj, _ = json.JSONDecoder().raw_decode(text, idx_s)
        return obj
    except (ValueError, json.JSONDecodeError):
        return None


def _netejar_inactives():
    ara = datetime.now()
    per_eliminar = [
        tel for tel, h in _histories.items()
        if (ara - h["last_activity"]) > timedelta(minutes=TIMEOUT_MINUTS)
    ]
    for tel in per_eliminar:
        del _histories[tel]


def netejar_conversa(telefon: str):
    """Reinicia la conversa d'un client (per ús des de l'admin)."""
    _histories.pop(telefon, None)


def obtenir_converses_actives() -> dict:
    """Retorna un resum de les converses en curs (per debugging)."""
    return {
        tel: {
            "nom":               h.get("nom", ""),
            "missatges":         len(h["messages"]),
            "ultima_activitat":  h["last_activity"].strftime("%H:%M:%S"),
        }
        for tel, h in _histories.items()
    }
