/**
 * Bot WhatsApp — Parada de Mercat (mode GRUP + cron divendres)
 *
 * Flux setmanal:
 *  - Divendres 09:00 → envia la llista de productes al grup (llista_divendres.txt)
 *  - Durant el dia  → respon a cada membre que escrigui, conversa i pren la comanda
 *  - Divendres 21:00 → extreu totes les comandes del dia i envia el resum al grup
 *
 * Configuració (.env):
 *  GRUP_ID=1234567890-1234567890@g.us   ← ID del grup (es mostra en arrencar)
 *  HORA_LLISTA=9                         ← hora d'enviar la llista (per defecte: 9)
 *  HORA_RESUM=21                         ← hora d'extreure les comandes (per defecte: 21)
 *  API_URL=http://localhost:8000         ← opcional
 *
 * Per arrencar:
 *  1. Arrenca el servidor Python: uvicorn main:app --port 8000
 *  2. npm install   (primera vegada)
 *  3. node bot.js
 *  4. Escaneja el QR amb el mòbil del mercat
 */

const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const axios  = require("axios");
const cron   = require("node-cron");
const fs     = require("fs");
const path   = require("path");

// ── Carregar .env ─────────────────────────────────────────────────────────────

const envPath = path.join(__dirname, ".env");
if (fs.existsSync(envPath)) {
  for (const line of fs.readFileSync(envPath, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const idx = trimmed.indexOf("=");
    if (idx === -1) continue;
    const k = trimmed.slice(0, idx).trim();
    const v = trimmed.slice(idx + 1).trim();
    process.env[k] ??= v;
  }
}

const API_URL     = process.env.API_URL    || "http://localhost:8000";
const GRUP_ID     = process.env.GRUP_ID    || "";
const HORA_LLISTA = parseInt(process.env.HORA_LLISTA || "9",  10);
const HORA_RESUM  = parseInt(process.env.HORA_RESUM  || "21", 10);

// Missatges rebuts durant el dia: [{ nom, telefon, text }]
const _missatgesDia = [];

// ── Client WhatsApp ───────────────────────────────────────────────────────────

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: ".wwebjs_auth" }),
  puppeteer: {
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
  },
});

client.on("qr", qr => {
  console.log("\n╔══════════════════════════════════════════════╗");
  console.log("║  Escaneja el QR amb el mòbil del mercat:    ║");
  console.log("║  WhatsApp → Ajustos → Dispositius vinculats ║");
  console.log("╚══════════════════════════════════════════════╝\n");
  qrcode.generate(qr, { small: true });
});

client.on("authenticated", () => console.log("🔐 Sessió autenticada."));
client.on("auth_failure",  () => console.error("❌ Error d'autenticació. Esborra .wwebjs_auth i torna a escanejar."));
client.on("disconnected",  r  => console.warn(`⚠️  Desconnectat: ${r}`));

client.on("ready", async () => {
  console.log("\n✅ Bot connectat!\n");

  const chats = await client.getChats();
  const grups = chats.filter(c => c.isGroup);

  if (!GRUP_ID) {
    console.log("⚠️  No has configurat GRUP_ID al .env");
    console.log("   Grups disponibles:\n");
    grups.forEach(g => {
      console.log(`   Nom: ${g.name}`);
      console.log(`   ID:  ${g.id._serialized}`);
      console.log(`   ────────────────────────────────`);
    });
    console.log("\n   Afegeix al .env:  GRUP_ID=<id del grup>  i reinicia.\n");
  } else {
    const grup = grups.find(g => g.id._serialized === GRUP_ID);
    if (grup) {
      console.log(`📱 Grup actiu: "${grup.name}"`);
    } else {
      console.log(`⚠️  Grup no trobat: ${GRUP_ID}`);
      console.log("   Grups disponibles:");
      grups.forEach(g => console.log(`   • ${g.name}  →  ${g.id._serialized}`));
    }
    console.log(`⏰ Llista de divendres: ${HORA_LLISTA}:00h`);
    console.log(`⏰ Resum de comandes:   ${HORA_RESUM}:00h\n`);
  }

  // Programar crons (només si el grup està configurat)
  if (GRUP_ID) {
    // Divendres a HORA_LLISTA: envia la llista de productes
    cron.schedule(`0 ${HORA_LLISTA} * * 5`, () => enviarLlista(), { timezone: "Europe/Madrid" });

    // Divendres a HORA_RESUM: envia el resum de comandes
    cron.schedule(`0 ${HORA_RESUM} * * 5`, () => enviarResum(), { timezone: "Europe/Madrid" });

    console.log("🕐 Crons programats per als divendres.\n");
  }
});

// ── Processament de missatges ─────────────────────────────────────────────────

client.on("message", async msg => {
  if (!msg.from.includes("@g.us"))       return;  // només grups
  if (GRUP_ID && msg.from !== GRUP_ID)   return;  // només el grup configurat
  if (msg.fromMe)                        return;
  if (msg.from === "status@broadcast")   return;

  const text = msg.body?.trim();
  if (!text) return;

  const contact   = await msg.getContact();
  const nomClient = contact.pushname || contact.name || "";
  const telefon   = (msg.author || msg.from).replace(/@[cg]\.us$/, "");

  // Guardar en silenci, sense respondre
  _missatgesDia.push({ nom: nomClient, telefon, text });
  console.log(`📩 [${hora()}] ${nomClient || telefon}: ${text.substring(0, 80)}`);
});

// ── Funcions del cron ─────────────────────────────────────────────────────────

async function enviarLlista() {
  const llistaPath = path.join(__dirname, "llista_divendres.txt");
  if (!fs.existsSync(llistaPath)) {
    console.error("❌ No s'ha trobat llista_divendres.txt");
    return;
  }
  const text = fs.readFileSync(llistaPath, "utf8").trim();
  try {
    const chat = await client.getChatById(GRUP_ID);
    await chat.sendMessage(text);
    console.log(`[${hora()}] 📋 Llista de divendres enviada al grup.`);
  } catch (err) {
    console.error(`❌ Error enviant la llista: ${err.message}`);
  }
}

async function enviarResum() {
  const chat = await client.getChatById(GRUP_ID);

  if (_missatgesDia.length === 0) {
    await chat.sendMessage("📋 No s'ha rebut cap missatge de comanda avui.");
    return;
  }

  // Agrupar missatges per client
  const perClient = {};
  for (const m of _missatgesDia) {
    if (!perClient[m.telefon]) perClient[m.telefon] = { nom: m.nom, textos: [] };
    perClient[m.telefon].textos.push(m.text);
  }

  let resum = `📋 *Resum de comandes — ${new Date().toLocaleDateString("ca", { weekday: "long", day: "numeric", month: "long" })}*\n\n`;
  let total = 0;

  for (const [tel, data] of Object.entries(perClient)) {
    try {
      const missatgeCombined = data.textos.join("\n");
      const res = await axios.post(`${API_URL}/api/extreure`, {
        missatge:   missatgeCombined,
        nom_client: data.nom || tel,
      });
      const comanda = res.data;
      if (!comanda.articles || comanda.articles.length === 0) continue;

      // Guardar la comanda al servidor
      await axios.post(`${API_URL}/api/comandes`, {
        client:            comanda.client || data.nom || tel,
        telefon:           tel,
        missatge_original: missatgeCombined,
        articles:          comanda.articles,
      });

      resum += `👤 *${comanda.client || data.nom || tel}*\n`;
      for (const a of comanda.articles) {
        resum += `   • ${a.quantitat} ${a.unitat} de ${a.nom}\n`;
      }
      resum += "\n";
      total++;
    } catch (err) {
      console.error(`Error extraient comanda de ${tel}: ${err.message}`);
    }
  }

  if (total === 0) {
    resum = "📋 No s'han pogut extreure comandes dels missatges d'avui.";
  } else {
    resum += `Total: ${total} comand${total === 1 ? "a" : "es"} ✅`;
  }

  // Buidar els missatges del dia
  _missatgesDia.length = 0;

  await chat.sendMessage(resum);
  console.log(`[${hora()}] 📊 Resum enviat al grup (${total} comandes).`);
}

// ── Helper ────────────────────────────────────────────────────────────────────

function hora() {
  return new Date().toLocaleTimeString("ca", { hour: "2-digit", minute: "2-digit" });
}

// ── Arrancada ─────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);

// Mode test: envia la llista ara mateix sense esperar el cron
if (args.includes("--test-llista")) {
  console.log("🧪 MODE TEST: connectant per enviar la llista...");
  client.on("ready", async () => {
    await enviarLlista();
    console.log("✅ Prova finalitzada. Tanca amb Ctrl+C.");
  });
  client.initialize();
  return;
}

// Mode test: envia el resum de comandes ara mateix
if (args.includes("--test-resum")) {
  console.log("🧪 MODE TEST: connectant per enviar el resum...");
  client.on("ready", async () => {
    await enviarResum();
    console.log("✅ Prova finalitzada. Tanca amb Ctrl+C.");
  });
  client.initialize();
  return;
}

// Mode normal
console.log("🚀 Iniciant bot WhatsApp — Parada de Mercat...");
console.log(`   Servidor Python: ${API_URL}`);
if (GRUP_ID) console.log(`   Grup: ${GRUP_ID}`);
console.log();
client.initialize();
