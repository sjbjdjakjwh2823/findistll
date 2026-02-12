import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    nextauth_url: Boolean(process.env.NEXTAUTH_URL),
    nextauth_secret: Boolean(process.env.NEXTAUTH_SECRET),
    database_url: Boolean(process.env.DATABASE_URL),
    google_configured: Boolean(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET),
    github_configured: Boolean(process.env.GITHUB_CLIENT_ID && process.env.GITHUB_CLIENT_SECRET),
    resend_configured: Boolean(process.env.RESEND_API_KEY),
    welcome_from_set: Boolean(process.env.WELCOME_EMAIL_FROM),
  });
}
