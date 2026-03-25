import { NextRequest, NextResponse } from "next/server";
import { Resend } from "resend";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const { nombre, cargo, empresa, email, telefono, volumen, mensaje } = await req.json();

  if (!nombre || !empresa || !email) {
    return NextResponse.json({ error: "Faltan campos requeridos" }, { status: 400 });
  }

  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    return NextResponse.json({ fallback: true, message: "Email service not configured" }, { status: 200 });
  }

  try {
    const resend = new Resend(apiKey);

    const { error } = await resend.emails.send({
      from: "FlexPQR Demo <onboarding@resend.dev>",
      to: process.env.CONTACT_EMAIL || "nicolas.herrera@flexfintech.com",
      replyTo: email,
      subject: `Nueva solicitud de demo — ${empresa}${cargo ? ` (${cargo})` : ""}`,
      html: `
        <div style="font-family:sans-serif;max-width:600px;margin:0 auto;background:#021f59;color:#fff;padding:32px;border-radius:12px;">
          <h2 style="color:#035aa7;margin-top:0;">Nueva solicitud de demo · FlexPQR</h2>
          <table style="width:100%;border-collapse:collapse;">
            <tr><td style="padding:8px 0;color:#94a3b8;width:140px;">Nombre</td><td style="padding:8px 0;color:#fff;font-weight:600;">${nombre}</td></tr>
            <tr><td style="padding:8px 0;color:#94a3b8;">Cargo</td><td style="padding:8px 0;color:#fff;">${cargo || "—"}</td></tr>
            <tr><td style="padding:8px 0;color:#94a3b8;">Empresa / Entidad</td><td style="padding:8px 0;color:#fff;font-weight:600;">${empresa}</td></tr>
            <tr><td style="padding:8px 0;color:#94a3b8;">Email</td><td style="padding:8px 0;"><a href="mailto:${email}" style="color:#035aa7;">${email}</a></td></tr>
            <tr><td style="padding:8px 0;color:#94a3b8;">Teléfono</td><td style="padding:8px 0;color:#fff;">${telefono || "—"}</td></tr>
            <tr><td style="padding:8px 0;color:#94a3b8;">Volumen PQRS</td><td style="padding:8px 0;color:#fff;">${volumen || "—"}</td></tr>
            <tr><td style="padding:8px 0;color:#94a3b8;vertical-align:top;">Problema a resolver</td><td style="padding:8px 0;color:#fff;">${mensaje || "—"}</td></tr>
          </table>
          <div style="margin-top:24px;padding:16px;background:#011640;border-radius:8px;border-left:3px solid #035aa7;">
            <p style="margin:0;color:#94a3b8;font-size:12px;">Responder directamente a este correo contactará a <strong style="color:#fff;">${email}</strong></p>
          </div>
        </div>
      `,
    });

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({ ok: true });
  } catch (err) {
    return NextResponse.json({ error: "Error al enviar email" }, { status: 500 });
  }
}
