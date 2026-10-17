"use server";

import { createSupabaseServerClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export async function signIn(formData: FormData) {
  const supabase = await createSupabaseServerClient();
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  const { error } = await supabase.auth.signInWithPassword({ email, password });

  if (error) {
    if (error.code === "email_not_confirmed" || /email not confirmed/i.test(error.message)) {
      redirect("/auth?error=email-not-confirmed");
    }

    if (error.code === "invalid_credentials" || /invalid login credentials/i.test(error.message)) {
      redirect("/auth?error=invalid-credentials");
    }

    redirect("/auth?error=sign-in-failed");
  }

  redirect("/dashboard");
}

export async function signUp(formData: FormData) {
  const supabase = await createSupabaseServerClient();
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  const { data, error } = await supabase.auth.signUp({ email, password });

  if (error) {
    if (/already registered|already exists/i.test(error.message)) {
      redirect("/auth?error=account-already-exists");
    }

    redirect("/auth?error=sign-up-failed");
  }

  // When email confirmation is enabled, signUp succeeds without creating a session.
  // Do not send users to a protected page until a session actually exists.
  if (!data.session) {
    redirect("/auth?notice=confirm-email");
  }

  redirect("/dashboard");
}

export async function signOut() {
  const supabase = await createSupabaseServerClient();
  await supabase.auth.signOut();
  redirect("/auth");
}
