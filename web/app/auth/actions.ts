"use server";

import bcrypt from "bcryptjs";
import { prisma } from "@/lib/prisma";
import { sendWelcomeEmail } from "@/lib/mailer";

type SignupState = { ok: boolean; message: string };

export async function signupAction(_: SignupState | null, formData: FormData): Promise<SignupState> {
  const name = String(formData.get("name") || "").trim();
  const emailRaw = String(formData.get("email") || "").trim();
  const password = String(formData.get("password") || "");
  const email = emailRaw.toLowerCase();

  if (!email || !password) {
    return { ok: false, message: "이메일과 비밀번호를 입력하세요." };
  }
  if (password.length < 8) {
    return { ok: false, message: "비밀번호는 8자 이상이어야 합니다." };
  }

  const existing = await prisma.user.findUnique({ where: { email } });
  if (existing) {
    return { ok: false, message: "이미 가입된 이메일입니다." };
  }

  const passwordHash = await bcrypt.hash(password, 10);
  const user = await prisma.user.create({
    data: {
      email,
      name: name || null,
      passwordHash,
    },
  });

  await sendWelcomeEmail(user.email || email, user.name);

  return { ok: true, message: "가입이 완료되었습니다. 로그인 페이지로 이동하세요." };
}
