import os
import json
import anthropic

SYSTEM_PROMPT = """Ets un assistent per a una parada de fruita i verdura al mercat.
Analitza el missatge de WhatsApp d'un client i extreu:
1. El nom del client (si apareix al missatge)
2. La llista d'articles amb quantitat i unitat

Respon SEMPRE en JSON amb aquest format exacte, sense cap text addicional:
{
  "client": "nom del client o string buit si no apareix",
  "articles": [
    {"nom": "nom de l'article en minúscules", "quantitat": número, "unitat": "kg/g/unitats/manats/bosses"}
  ]
}

Regles:
- Si no s'especifica unitat, infereix-la (fruites/verdures normalment en kg)
- Si diu "mitja dotzena" = 6 unitats, "una dotzena" = 12 unitats
- Normalitza els noms: "tomaquets" → "tomàquets", "pomes" → "pomes"
- Si diu "un quilo" o "1 kilo" → quantitat: 1.0, unitat: "kg"
- Si diu "dos quilos i mig" → quantitat: 2.5, unitat: "kg"
- Unitats possibles: kg, g, unitats, manats, bosses, caixes"""


def extreure_comanda(missatge: str, nom_client: str = "") -> dict:
    """
    Envia el missatge a Claude i retorna:
    {
      "client": "Joan",
      "articles": [
        {"nom": "peres", "quantitat": 2.0, "unitat": "kg"},
        ...
      ],
      "missatge_original": "..."
    }
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY no està configurada.")

    client = anthropic.Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": missatge}],
        )
        raw = message.content[0].text.strip()

        # Eliminar possibles blocs de codi markdown
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        resultat = json.loads(raw)

        # Si l'IA no ha trobat el client, usar el nom_client passat manualment
        if not resultat.get("client") and nom_client:
            resultat["client"] = nom_client

        resultat["missatge_original"] = missatge
        return resultat

    except json.JSONDecodeError as e:
        raise ValueError(f"La IA ha retornat un format inesperat: {e}")
    except anthropic.APIConnectionError:
        raise ValueError("No s'ha pogut connectar amb la IA. Comprova la connexió a Internet.")
    except anthropic.AuthenticationError:
        raise ValueError("Clau de la API d'Anthropic invàlida. Comprova ANTHROPIC_API_KEY.")
    except anthropic.APIError as e:
        raise ValueError(f"Error de la API d'Anthropic: {e}")
