import { Resend } from "resend";

const resendApiKey = process.env.RESEND_API_KEY;
const fromEmail = process.env.WELCOME_EMAIL_FROM || "Preciso <no-reply@example.com>";

const resend = resendApiKey ? new Resend(resendApiKey) : null;

export async function sendWelcomeEmail(to: string, name?: string | null) {
  if (!resend) return { ok: false, error: "RESEND_API_KEY not set" };
  const subject = "Welcome to Preciso";
  const greeting = name ? `${name}님,` : "안녕하세요,";
  const html = `
    <div style="font-family:Arial,sans-serif;line-height:1.6;">
      <h2>${greeting}</h2>
      <p>Preciso에 가입해주셔서 감사합니다.</p>
      <p>이제 기업 에이전트 연결, 데이터 인입, 승인/학습, RAG 운영을 한 곳에서 관리할 수 있습니다.</p>
      <p style="margin-top:24px;">바로 시작하려면 <strong>Usage Guide</strong>를 확인해주세요.</p>
      <p>— Preciso Team</p>
    </div>
  `;
  const result = await resend.emails.send({
    from: fromEmail,
    to,
    subject,
    html,
  });
  return { ok: true, result };
}

export async function sendAnalysisAlert(to: string, subject: string, html: string) {
  if (!resend) return { ok: false, error: "RESEND_API_KEY not set" };
  const result = await resend.emails.send({
    from: fromEmail,
    to,
    subject,
    html,
  });
  return { ok: true, result };
}
