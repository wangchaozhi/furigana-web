import type { OAuthProvider } from "@/lib/auth";

type Props = {
  providers: readonly OAuthProvider[];
  busyProvider: OAuthProvider | "password" | null;
  onSignIn: (provider: OAuthProvider) => void;
};

const providerLabels: Record<OAuthProvider, string> = {
  google: "Google",
  github: "GitHub",
};

function ProviderIcon({ provider }: { provider: OAuthProvider }) {
  if (provider === "google") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path fill="#4285F4" d="M21.6 12.2c0-.7-.1-1.4-.2-2.1H12v4h5.4a4.6 4.6 0 0 1-2 3v2.6h3.3c1.9-1.8 2.9-4.4 2.9-7.5Z" />
        <path fill="#34A853" d="M12 22c2.7 0 5-.9 6.7-2.3l-3.3-2.6c-.9.6-2.1 1-3.4 1a5.9 5.9 0 0 1-5.6-4.1H3v2.7A10 10 0 0 0 12 22Z" />
        <path fill="#FBBC05" d="M6.4 14a6 6 0 0 1 0-3.9V7.4H3a10 10 0 0 0 0 9.3L6.4 14Z" />
        <path fill="#EA4335" d="M12 6c1.5 0 2.8.5 3.9 1.5l2.9-2.9A9.8 9.8 0 0 0 3 7.4l3.4 2.7A5.9 5.9 0 0 1 12 6Z" />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path fill="currentColor" d="M12 .8a11.4 11.4 0 0 0-3.6 22.2c.6.1.8-.3.8-.6v-2.2c-3.3.7-4-1.4-4-1.4-.5-1.4-1.3-1.8-1.3-1.8-1.1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1.1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.8-1.6-2.7-.3-5.5-1.3-5.5-6a4.7 4.7 0 0 1 1.2-3.2 4.4 4.4 0 0 1 .1-3.2s1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0c2.3-1.5 3.3-1.2 3.3-1.2a4.4 4.4 0 0 1 .1 3.2 4.7 4.7 0 0 1 1.2 3.2c0 4.7-2.8 5.7-5.5 6 .4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A11.4 11.4 0 0 0 12 .8Z" />
    </svg>
  );
}

export default function SocialLoginButtons({ providers, busyProvider, onSignIn }: Props) {
  if (!providers.length) return null;

  return (
    <div className="socialAuth">
      <div className="socialAuthButtons">
        {providers.map((provider) => (
          <button
            className="socialAuthButton"
            disabled={busyProvider !== null}
            key={provider}
            onClick={() => onSignIn(provider)}
            type="button"
          >
            <ProviderIcon provider={provider} />
            {busyProvider === provider ? "正在跳转…" : `使用 ${providerLabels[provider]} 继续`}
          </button>
        ))}
      </div>
      <div className="authDivider"><span>或使用邮箱</span></div>
    </div>
  );
}
