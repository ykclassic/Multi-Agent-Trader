import { signIn, signUp } from "./actions";

type AuthPageProps = {
  searchParams: Promise<{ error?: string; notice?: string }>;
};

const authErrors: Record<string, string> = {
  "email-not-confirmed": "Your email address has not been confirmed yet. Open the confirmation email from Supabase, then return here and sign in again.",
  "invalid-credentials": "The email or password is incorrect. Check both and try again.",
  "account-already-exists": "An account with this email may already exist. Try signing in, or use the confirmation email if you have not confirmed it yet.",
  "sign-in-failed": "We could not sign you in right now. Please try again in a moment.",
  "sign-up-failed": "We could not create the account. Check the details and try again.",
};

export default async function AuthPage({ searchParams }: AuthPageProps) {
  const params = await searchParams;
  const errorMessage = params.error ? authErrors[params.error] : undefined;
  const noticeMessage =
    params.notice === "confirm-email"
      ? "Your account was created. Check your inbox (and spam folder) for the confirmation email before signing in."
      : undefined;

  return (
    <main className="container" style={{ paddingTop: 72, maxWidth: 520 }}>
      <div className="card">
        <h1>Multi-Agent Trader</h1>
        <p className="muted">Foundation: authenticated workspace and strategy control plane.</p>
        {errorMessage ? (
          <p role="alert" style={{ marginTop: 16, padding: 12, border: "1px solid #dc2626", borderRadius: 8 }}>
            {errorMessage}
          </p>
        ) : null}
        {noticeMessage ? (
          <p role="status" style={{ marginTop: 16, padding: 12, border: "1px solid #16a34a", borderRadius: 8 }}>
            {noticeMessage}
          </p>
        ) : null}
        <form action={signIn} className="grid" style={{ marginTop: 24 }}>
          <input name="email" type="email" placeholder="Email" required autoComplete="email" />
          <input name="password" type="password" placeholder="Password" required minLength={8} autoComplete="current-password" />
          <button type="submit">Sign in</button>
        </form>
        <form action={signUp} style={{ marginTop: 12 }}>
          <input name="email" type="email" placeholder="New account email" required autoComplete="email" />
          <input name="password" type="password" placeholder="New account password" required minLength={8} autoComplete="new-password" style={{ marginTop: 8 }} />
          <button type="submit" style={{ marginTop: 8 }}>Create account</button>
        </form>
      </div>
    </main>
  );
}
