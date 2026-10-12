/* DocOga support-mail Worker — Cloudflare Email Routing handler
 *
 * Lane model (owner instruction, 12 Oct 2026): the Business support lane is
 * FULLY AUTONOMOUS — like buying the Oga Pass, nobody is supposed to reach
 * the owner by hand, and after paying nobody is expected to talk to a human
 * either. What happens to every inbound mail to business@docoga.com.ng:
 *
 *   1. A SILENT ARCHIVE copy is forwarded to ARCHIVE_TO (the owner's Gmail).
 *      Record only — reading it is never required. FLW / CAC / provider
 *      notices addressed to business@ and dispute evidence land here instead
 *      of being silently deleted.
 *   2. If the mail qualifies (external, human, not a bounce/list/automated
 *      sender — see shouldAutoReply), an auto-reply goes out AS
 *      business@docoga.com.ng with the exact self-serve text (REPLY_TEXT).
 *      Delivery: Cloudflare's native reply() first (threaded, and CF only
 *      allows it for mail whose sender has valid DMARC — built-in
 *      anti-spoof); if that path fails or is switched off, the identical
 *      text goes out through Brevo's transactional API — the same key and
 *      code path the docoga-pass worker uses for magic links (300/day free).
 *
 * Nothing in this lane is a human step. The "support" a buyer experiences is:
 * pay-first self-serve + this auto-reply + the FAQ page (docoga.com.ng/support).
 *
 * CF-only module (cloudflare:email) is imported dynamically inside the CF
 * path so this file stays importable under plain node for the unit tests.
 */

const FROM_NAME = "DocOga Business";
const FROM = "business@docoga.com.ng";
const SELF_DOMAIN = "docoga.com.ng";

const REPLY_SUBJECT = "Received - DocOga Business is fully self-serve";

export const REPLY_TEXT = [
  "Hi,",
  "",
  "Thanks for writing to DocOga Business.",
  "",
  "This is an automated inbox - DocOga is built to be fully self-serve, and",
  "most things are faster done than explained:",
  "",
  "- Pay for your team (bank transfer or card): docoga.com.ng -> Set up your",
  "  team, or the Team dashboard once you've signed in",
  "- Your team dashboard (seats, branding, invoices, printable PDF):",
  "  docoga.com.ng -> Team dashboard (sign in with your work email - magic link,",
  "  no password)",
  "- A payment that already went through: don't re-send the transfer - the",
  "  system verifies the exact amount automatically and your team activates on",
  "  its own. If the amount was wrong, the system already emailed you a fresh",
  "  account number for the correct amount.",
  "- Everything else: the Business FAQ - docoga.com.ng/support",
  "",
  "Prefer to talk it through? The green WhatsApp button on docoga.com.ng",
  "reaches the support line directly.",
  "",
  "Every message you send is kept on record.",
  "",
  "DocOga - Abuja, Nigeria",
  "DocOga provides self-help document templates; it is not a law firm and does",
  "not provide legal advice.",
].join("\n");

const REPLY_HTML = (
  "<p>Hi,</p>" +
  "<p>Thanks for writing to DocOga Business.</p>" +
  "<p>This is an automated inbox - DocOga is built to be fully self-serve, and most things are faster done than explained:</p>" +
  "<ul>" +
  "<li><b>Pay for your team</b> (bank transfer or card): docoga.com.ng &rarr; Set up your team, or the Team dashboard once you've signed in</li>" +
  "<li><b>Your team dashboard</b> (seats, branding, invoices, printable PDF): docoga.com.ng &rarr; Team dashboard (sign in with your work email - magic link, no password)</li>" +
  "<li><b>A payment that already went through:</b> don't re-send the transfer - the system verifies the exact amount automatically and your team activates on its own. If the amount was wrong, the system already emailed you a fresh account number for the correct amount.</li>" +
  "<li><b>Everything else:</b> the Business FAQ - docoga.com.ng/support</li>" +
  "</ul>" +
  "<p>Prefer to talk it through? The green WhatsApp button on docoga.com.ng reaches the support line directly.</p>" +
  "<p>Every message you send is kept on record.</p>" +
  "<p>DocOga - Abuja, Nigeria<br>" +
  "DocOga provides self-help document templates; it is not a law firm and does not provide legal advice.</p>"
);

const LOCAL_BAD = /(^|[._-])(noreply|no-reply|donotreply|do-not-reply|mailer-daemon|mailerdaemon|postmaster|bounce|bounces|daemon|abuse|spam|error|errors|failed)([._-]|$)/;
const SUBJECT_BAD = /(do not reply|don't reply|automatic( response| reply)?|auto-?response|mailer-?daemon|mail delivery (status|failure|report)|delivery (status|failure|report)|undeliver|bounce|automatic notification)/;

/**
 * Pure guard: should this inbound mail get the auto-reply?
 * (message.from is the envelope MAIL FROM; message.headers is a Headers-like.)
 * Exports nothing CF-specific — unit-testable under plain node.
 */
export function shouldAutoReply({ from, subject, headers }) {
  if (!from || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(from)) return false;
  const parts = from.split("@");
  const local = (parts[0] || "").toLowerCase();
  const domain = (parts[1] || "").toLowerCase();
  if (!domain || domain === SELF_DOMAIN) return false; // never reply to our own domain
  const h = (n) => String(headers.get(n) || "").toLowerCase().trim();
  if (LOCAL_BAD.test(local)) return false;
  const autoSubmitted = h("auto-submitted");
  if (autoSubmitted === "auto-generated" || autoSubmitted === "automatic-reply") return false;
  const precedence = h("precedence");
  if (["bulk", "auto-reply", "list", "first", "second"].includes(precedence)) return false; // mailing lists
  if (h("list-unsubscribe")) return false; // mailing list
  if (h("x-auto-response") || h("x-autoreply")) return false;
  const s = (subject || "").toLowerCase();
  if (SUBJECT_BAD.test(s)) return false;
  return true;
}

function rid() {
  return Math.random().toString(36).slice(2, 10);
}

/** Build the reply as raw MIME (text/plain + text/html). Pure — node-safe. */
export function buildReplyMime({ from, subject, messageId, text, html }) {
  const b = "docoga" + rid();
  const lines = [
    `Date: ${new Date().toUTCString()}`,
    `Message-ID: <${Date.now()}.${rid()}@${SELF_DOMAIN}>`,
    `From: ${FROM_NAME} <${FROM}>`,
    `To: ${from}`,
    `Subject: ${subject}`,
  ];
  if (messageId) {
    lines.push(`In-Reply-To: ${messageId}`, `References: ${messageId}`);
  }
  lines.push(
    `MIME-Version: 1.0`,
    `Content-Type: multipart/alternative; boundary="${b}"`,
    "",
    `--${b}`,
    `Content-Type: text/plain; charset="utf-8"`,
    "",
    text,
    `--${b}`,
    `Content-Type: text/html; charset="utf-8"`,
    "",
    html,
    `--${b}--`,
    "",
  );
  return lines.join("\r\n");
}

async function brevoReply(env, { from, subject, messageId, html }) {
  if (!env.BREVO_API_KEY) throw new Error("BREVO_API_KEY unset");
  const headers = {};
  if (messageId) {
    headers["In-Reply-To"] = messageId;
    headers["References"] = messageId;
  }
  const response = await fetch("https://api.brevo.com/v3/smtp/email", {
    method: "POST",
    headers: {
      "api-key": env.BREVO_API_KEY,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      sender: { name: FROM_NAME, email: FROM },
      to: [{ email: from }],
      subject,
      html,
      headers,
    }),
  });
  if (!response.ok) throw new Error(`BREVO_HTTP_${response.status}`);
}

/**
 * Send the auto-reply AS business@. Returns the provider that delivered it.
 * CF native reply() first (env.USE_CF_REPLY !== "off"); Brevo API fallback —
 * so the reply goes out no matter which path the CF free tier allows.
 */
export async function sendAutoReply(env, message, { from, subject, messageId }) {
  const mime = buildReplyMime({ from, subject, messageId, text: REPLY_TEXT, html: REPLY_HTML });
  if (env.USE_CF_REPLY !== "off") {
    try {
      const { EmailMessage } = await import("cloudflare:email");
      await message.reply(new EmailMessage(FROM, from, mime));
      console.info(`[support-mail] auto-reply via cf to=${from}`);
      return "cf";
    } catch (err) {
      console.warn(`[support-mail] cf reply failed (${err.message}) - brevo fallback to=${from}`);
    }
  }
  await brevoReply(env, { from, subject, messageId, html: REPLY_HTML });
  console.info(`[support-mail] auto-reply via brevo to=${from}`);
  return "brevo";
}

export default {
  async email(message, env) {
    const from = message.from;
    const subject = message.headers.get("subject") || "";
    const messageId = message.headers.get("message-id") || "";

    // 1) archive copy — ALWAYS, best-effort; never blocks the reply
    if (env.ARCHIVE_TO) {
      try {
        await message.forward(env.ARCHIVE_TO);
        console.info(`[support-mail] archived from=${from}`);
      } catch (err) {
        console.error(`[support-mail] archive failed (${err.message}) - continuing without archive`);
      }
    }

    // 2) auto-reply — only qualifying external human mail
    if (!shouldAutoReply({ from, subject, headers: message.headers })) {
      console.info(`[support-mail] no auto-reply (guard) from=${from}`);
      return;
    }
    await sendAutoReply(env, message, { from, subject, messageId });
  },
};
