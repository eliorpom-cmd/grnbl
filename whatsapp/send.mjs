// grnbl's WhatsApp side: connects as a linked device, does one thing, disconnects.
// No server stays up: the Python publish step calls `send` once per post.
//
//   node whatsapp/send.mjs link [phone]      link the account once (QR code, or pairing code if phone given, e.g. 33476000000)
//   node whatsapp/send.mjs groups            the groups of the account, by community, with their ids
//   node whatsapp/send.mjs channel <invite>  id of a channel from its invite link (https://whatsapp.com/channel/...)
//   node whatsapp/send.mjs send <jid>        sends {"text": "..."} read on stdin, prints {"id": "..."}
//
// The session lives in data/whatsapp-auth/ (not versioned): copying the data folder
// to another machine moves the link with it.

import makeWASocket, { Browsers, DisconnectReason, useMultiFileAuthState } from "@whiskeysockets/baileys";
import pino from "pino";
import qrcode from "qrcode-terminal";
import QRCode from "qrcode";
import { execFile } from "node:child_process";
import { existsSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const DATA = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "data");
const AUTH = path.join(DATA, "whatsapp-auth");
// The QR is also shown as a page that reloads itself, easier to scan than the terminal.
const QR_PAGE = path.join(DATA, "whatsapp-qr.html");

function qrPage(body) {
  writeFileSync(QR_PAGE, `<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="3"><title>Relier grnbl</title>
<body style="margin:0;display:grid;place-items:center;min-height:100vh;font:17px -apple-system,system-ui;background:#fff;color:#111;text-align:center">
<div>${body}</div></body>`);
}
const OPEN_TIMEOUT_MS = 60_000;
// Linking waits for a human to type the code or scan the QR on the phone.
const LINK_TIMEOUT_MS = 300_000;

function fail(message) {
  console.error(message);
  process.exit(1);
}

// Resolves once the connection is open; `onQr` receives QR codes while not linked yet.
async function connect({ onQr, phone, timeout = OPEN_TIMEOUT_MS } = {}) {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH);
  const sock = makeWASocket({
    auth: state,
    logger: pino({ level: "silent" }),
    browser: Browsers.macOS("grnbl"),
    markOnlineOnConnect: false, // the phone keeps receiving its own notifications
    syncFullHistory: false,
  });
  sock.ev.on("creds.update", saveCreds);
  if (phone && !state.creds.registered) {
    // Asked a little after the socket starts, as Baileys expects.
    setTimeout(async () => {
      const code = await sock.requestPairingCode(phone.replace(/\D/g, ""));
      console.error(`WhatsApp > Appareils connectés > Connecter un appareil > Lier avec le numéro : ${code}`);
    }, 3000);
  }
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`WhatsApp did not connect within ${timeout / 1000} s`)), timeout);
    sock.ev.on("connection.update", ({ connection, lastDisconnect, qr }) => {
      if (qr && onQr) onQr(qr);
      if (connection === "open") {
        clearTimeout(timer);
        resolve();
      }
      if (connection === "close") {
        const code = lastDisconnect?.error?.output?.statusCode;
        clearTimeout(timer);
        if (code === DisconnectReason.restartRequired) {
          // Normal right after linking: reconnect with the new credentials.
          connect({ onQr, phone, timeout }).then((s) => { sock.reconnected = s; resolve(); }, reject);
        } else if (code === DisconnectReason.loggedOut) {
          reject(new Error("Logged out: run `node whatsapp/send.mjs link` again"));
        } else {
          reject(new Error(`Connection closed (${code ?? "unknown"})`));
        }
      }
    });
  });
  return sock.reconnected ?? sock;
}

async function readStdin() {
  let raw = "";
  for await (const chunk of process.stdin) raw += chunk;
  return JSON.parse(raw);
}

const [command, arg] = process.argv.slice(2);

try {
  if (command === "link") {
    const sock = await connect({
      phone: arg,
      timeout: LINK_TIMEOUT_MS,
      onQr: arg ? null : async (qr) => {
        console.error("WhatsApp > Appareils connectés > Connecter un appareil, puis scanne :");
        qrcode.generate(qr, { small: true }, (art) => console.error(art));
        const svg = await QRCode.toString(qr, { type: "svg", margin: 2, width: 420 });
        const first = !existsSync(QR_PAGE);
        qrPage(`<p>WhatsApp → Appareils connectés → Connecter un appareil, puis scanne :</p>${svg}<p style="color:#888">Le code change toutes les 20 s, la page suit.</p>`);
        if (first && process.platform === "darwin") execFile("open", [QR_PAGE]);
      },
    });
    console.log(JSON.stringify({ linked: sock.user?.id ?? true }));
    if (existsSync(QR_PAGE)) qrPage("<h1>Relié ✓</h1><p>Tu peux fermer cette page.</p>");
    // Leave time for the first keys to be saved before closing.
    await new Promise((r) => setTimeout(r, 5000));
    sock.end(undefined);
  } else if (command === "groups") {
    // grnbl posts into the groups of a community (one per topic); this gives their ids for data/whatsapp.json.
    const sock = await connect();
    const groups = Object.values(await sock.groupFetchAllParticipating());
    const names = Object.fromEntries(groups.map((g) => [g.id, g.subject]));
    const rows = groups
      .filter((g) => !g.isCommunity)
      .map((g) => ({ id: g.id, name: g.subject, community: names[g.linkedParent] ?? null,
                     admins_only: Boolean(g.announce), community_announce: Boolean(g.isCommunityAnnounce) }))
      .sort((a, b) => `${a.community}${a.name}`.localeCompare(`${b.community}${b.name}`));
    console.log(JSON.stringify(rows, null, 1));
    sock.end(undefined);
  } else if (command === "channel") {
    if (!arg) fail("usage: channel <invite link>");
    const sock = await connect();
    const code = arg.split("/").filter(Boolean).pop();
    const meta = await sock.newsletterMetadata("invite", code);
    if (!meta) fail("Channel not found");
    console.log(JSON.stringify({ id: meta.id, name: meta.thread_metadata?.name?.text ?? meta.name }));
    sock.end(undefined);
  } else if (command === "send") {
    if (!arg) fail("usage: send <jid>");
    const { text } = await readStdin();
    if (!text) fail("nothing to send");
    const sock = await connect();
    const sent = await sock.sendMessage(arg, { text });
    // The message is acknowledged asynchronously: a short wait before closing.
    await new Promise((r) => setTimeout(r, 3000));
    console.log(JSON.stringify({ id: sent?.key?.id }));
    sock.end(undefined);
  } else {
    fail("usage: link [phone] | groups | channel <invite link> | send <jid>");
  }
  process.exit(0);
} catch (e) {
  fail(e.message ?? String(e));
}
