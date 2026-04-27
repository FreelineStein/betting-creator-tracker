"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { usePostHog } from "posthog-js/react";
import { Button } from "../../components/brand";
import { submitPick, SubmissionError, type SubmissionSuccess } from "../lib/api";

const TWEET_URL_PATTERN =
  /^https?:\/\/(?:www\.|mobile\.)?(?:twitter\.com|x\.com)\/[A-Za-z0-9_]{1,15}\/status\/\d+(?:[/?#].*)?$/;

const TURNSTILE_SCRIPT_SRC =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

declare global {
  interface Window {
    turnstile?: {
      render: (
        container: HTMLElement | string,
        options: {
          sitekey: string;
          callback?: (token: string) => void;
          "error-callback"?: () => void;
          "expired-callback"?: () => void;
          theme?: "light" | "dark" | "auto";
        },
      ) => string;
      reset: (widgetId?: string) => void;
      remove: (widgetId?: string) => void;
    };
  }
}

type FormState =
  | { kind: "idle"; error?: string }
  | { kind: "submitting" }
  | { kind: "success"; result: SubmissionSuccess };

const TURNSTILE_LOAD_TIMEOUT_MS = 10_000;

export default function SubmitForm({
  turnstileSiteKey,
}: {
  turnstileSiteKey: string;
}) {
  const [url, setUrl] = useState("");
  const [honeypot, setHoneypot] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);
  const [state, setState] = useState<FormState>({ kind: "idle" });

  const turnstileContainerRef = useRef<HTMLDivElement | null>(null);
  const turnstileWidgetIdRef = useRef<string | null>(null);
  const turnstileTokenRef = useRef<string>("");
  const [turnstileReady, setTurnstileReady] = useState(false);
  const [turnstileLoadFailed, setTurnstileLoadFailed] = useState(false);

  const posthog = usePostHog();

  // If the Turnstile script doesn't load within a sensible window (network
  // blocked, ad-blocker, Cloudflare unreachable), tell the user instead of
  // leaving them stuck on "Loading verification…".
  useEffect(() => {
    if (turnstileReady) return;
    const t = setTimeout(() => setTurnstileLoadFailed(true), TURNSTILE_LOAD_TIMEOUT_MS);
    return () => clearTimeout(t);
  }, [turnstileReady]);

  // Render the Turnstile widget once the script has loaded *and* the
  // container is mounted. We use refs for the token so a token change
  // doesn't force a re-render.
  useEffect(() => {
    if (!turnstileReady) return;
    if (!turnstileContainerRef.current) return;
    if (turnstileWidgetIdRef.current) return;
    if (!window.turnstile) return;

    turnstileWidgetIdRef.current = window.turnstile.render(
      turnstileContainerRef.current,
      {
        sitekey: turnstileSiteKey,
        theme: "dark",
        callback: (token) => {
          turnstileTokenRef.current = token;
        },
        "expired-callback": () => {
          turnstileTokenRef.current = "";
        },
        "error-callback": () => {
          turnstileTokenRef.current = "";
        },
      },
    );
  }, [turnstileReady, turnstileSiteKey, state.kind]);

  function resetForm() {
    setUrl("");
    setHoneypot("");
    setUrlError(null);
    turnstileTokenRef.current = "";
    turnstileWidgetIdRef.current = null;
    setState({ kind: "idle" });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (state.kind === "submitting") return;

    posthog?.capture("submission_started");

    const trimmed = url.trim();
    if (!trimmed) {
      posthog?.capture("submission_validation_failed", { reason: "empty" });
      setUrlError("Paste a link to the X post.");
      return;
    }
    if (!TWEET_URL_PATTERN.test(trimmed)) {
      posthog?.capture("submission_validation_failed", { reason: "invalid_format" });
      setUrlError("That doesn't look like an X post URL. Example: https://x.com/handle/status/123…");
      return;
    }
    setUrlError(null);

    if (!turnstileTokenRef.current) {
      posthog?.capture("submission_turnstile_blocked");
      setState({
        kind: "idle",
        error: "Please complete the verification check before submitting.",
      });
      return;
    }

    setState({ kind: "submitting" });
    try {
      const result = await submitPick({
        url: trimmed,
        turnstileToken: turnstileTokenRef.current,
        honeypot,
      });
      setState({ kind: "success", result });
      posthog?.capture("submission_succeeded", {
        picks_extracted: result.picks_extracted,
        already_tracked: result.status === "already_tracked",
        creator_handle: result.creator?.handle,
      });
    } catch (err) {
      const message =
        err instanceof SubmissionError
          ? err.message
          : "Something went wrong. Please try again.";
      posthog?.capture("submission_failed", {
        error_type: err instanceof SubmissionError ? "api_error" : "network_error",
      });
      // Reset Turnstile so the user can retry — tokens are single-use.
      if (window.turnstile && turnstileWidgetIdRef.current) {
        window.turnstile.reset(turnstileWidgetIdRef.current);
      }
      turnstileTokenRef.current = "";
      setState({ kind: "idle", error: message });
    }
  }

  if (state.kind === "success") {
    return (
      <>
        <SuccessPanel
          result={state.result}
          onSubmitAnother={() => {
            posthog?.capture("submission_another_clicked");
            resetForm();
          }}
        />
        {/* Keep the Turnstile script cached for the next submission */}
        <Script
          src={TURNSTILE_SCRIPT_SRC}
          strategy="afterInteractive"
          onLoad={() => setTurnstileReady(true)}
        />
      </>
    );
  }

  const submitting = state.kind === "submitting";
  const formError = state.kind === "idle" ? state.error : undefined;

  return (
    <>
      <Script
        src={TURNSTILE_SCRIPT_SRC}
        strategy="afterInteractive"
        onLoad={() => setTurnstileReady(true)}
      />
      <form onSubmit={handleSubmit} noValidate>
        {/* Honeypot — hidden from real users, irresistible to dumb bots.
            Inline styles so the field stays hidden even if Tailwind fails to load. */}
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            left: "-9999px",
            top: "auto",
            width: "1px",
            height: "1px",
            overflow: "hidden",
          }}
        >
          <label>
            Website
            <input
              type="text"
              name="website"
              tabIndex={-1}
              autoComplete="off"
              value={honeypot}
              onChange={(e) => setHoneypot(e.target.value)}
            />
          </label>
        </div>

        <label htmlFor="tweet-url" className="block">
          <div className="font-mono text-[10px] uppercase tracking-label text-ink-400 mb-2">
            Post URL
          </div>
          <input
            id="tweet-url"
            type="url"
            inputMode="url"
            autoComplete="off"
            placeholder="https://x.com/handle/status/123…"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              if (urlError) setUrlError(null);
            }}
            disabled={submitting}
            aria-invalid={Boolean(urlError)}
            aria-describedby={urlError ? "tweet-url-error" : undefined}
            className={`w-full rounded-md border bg-pitch px-3 py-3 text-white placeholder:text-ink-600 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-signal/40 disabled:opacity-50 ${
              urlError ? "border-alert" : "border-ink-800 hover:border-ink-400"
            }`}
          />
          {urlError && (
            <p id="tweet-url-error" className="mt-2 text-xs text-alert">
              {urlError}
            </p>
          )}
        </label>

        <div className="mt-6">
          <div ref={turnstileContainerRef} />
          {!turnstileReady && !turnstileLoadFailed && (
            <p className="text-xs text-ink-600 font-mono uppercase tracking-label">
              Loading verification…
            </p>
          )}
          {turnstileLoadFailed && !turnstileReady && (
            <p className="text-xs text-alert-deep">
              Couldn&apos;t load verification (Cloudflare Turnstile may be blocked
              by an ad-blocker or your network). Refresh the page to try again.
            </p>
          )}
        </div>

        {formError && (
          <div
            role="alert"
            className="mt-6 rounded-md border border-alert/40 bg-alert-dim px-4 py-3 text-sm text-alert-deep"
          >
            {formError}
          </div>
        )}

        <Button
          type="submit"
          variant="primary"
          disabled={submitting}
          className="mt-6 w-full sm:w-auto"
        >
          {submitting ? "Submitting…" : "Submit pick"}
        </Button>
      </form>
    </>
  );
}

function SuccessPanel({
  result,
  onSubmitAnother,
}: {
  result: SubmissionSuccess;
  onSubmitAnother: () => void;
}) {
  const isAlreadyTracked = result.status === "already_tracked";
  const accent = isAlreadyTracked ? "ink" : "signal";
  const eyebrow = isAlreadyTracked ? "Already on the record" : "Submission received";

  return (
    <div
      className={`rounded-xl border p-6 ${
        accent === "signal"
          ? "border-signal/40 bg-signal-dim"
          : "border-ink-800 bg-ink-800/40"
      }`}
    >
      <div
        className={`font-mono text-[10px] uppercase tracking-label mb-3 ${
          accent === "signal" ? "text-signal" : "text-ink-400"
        }`}
      >
        {eyebrow}
      </div>
      <h2 className="font-display font-black text-2xl sm:text-3xl tracking-display leading-tight text-white">
        {result.message}
      </h2>

      {result.creator && (
        <div className="mt-5 text-sm text-ink-200">
          <div>
            <span className="text-ink-400">Creator: </span>
            <span className="text-white font-medium">{result.creator.display_name}</span>{" "}
            <span className="text-ink-400 font-mono">{result.creator.handle}</span>
          </div>
          {result.creator.was_new && (
            <div className="mt-1 text-ink-400 text-xs">
              New to the platform — pending admin review before appearing publicly.
            </div>
          )}
        </div>
      )}

      {result.picks_extracted > 0 && (
        <ul className="mt-5 space-y-2">
          {result.picks.map((p, i) => (
            <li
              key={i}
              className="rounded-md border border-ink-800 bg-pitch px-3 py-2 text-sm"
            >
              <div className="text-white">
                <span className="font-mono text-[10px] uppercase tracking-label text-ink-400 mr-2">
                  {p.sport ?? "—"}
                </span>
                {p.event ?? formatPickDetail(p)}
              </div>
              <div className="text-ink-400 text-xs mt-1 font-mono">
                {p.pick_type}
                {p.odds ? ` · ${p.odds}` : ""}
                {" · via "}
                {p.source}
              </div>
              {p.pick_type === "parlay" && <ParlayLegs detail={p.pick_detail} />}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Button variant="primary" onClick={onSubmitAnother}>
          Submit another
        </Button>
        <a
          href="/"
          className="inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-bold uppercase tracking-label text-ink-400 hover:text-white transition-colors"
        >
          Back to records
        </a>
      </div>
    </div>
  );
}

function formatPickDetail(p: { pick_type: string; pick_detail: Record<string, unknown> }): string {
  const d = p.pick_detail || {};
  switch (p.pick_type) {
    case "spread":
      return `${d.team ?? ""} ${d.line ?? ""}`.trim();
    case "moneyline":
      return `${d.team ?? ""} ML`.trim();
    case "over_under":
      return `${d.direction ?? "Over"} ${d.total ?? ""}`.trim();
    case "prop":
      return `${d.player ?? ""} ${d.direction ?? "Over"} ${d.line ?? ""} ${d.prop ?? ""}`.trim();
    case "parlay":
      return `${(d.legs as unknown[] | undefined)?.length ?? 0}-leg parlay`;
    default:
      return p.pick_type;
  }
}

type Leg = {
  text?: string;
  type?: string;
  detail?: Record<string, unknown>;
  sport?: string;
  event?: string;
};

function ParlayLegs({ detail }: { detail: Record<string, unknown> }) {
  const legs = (detail?.legs as Leg[] | undefined) ?? [];
  if (legs.length === 0) return null;
  return (
    <ol className="mt-3 space-y-1.5 border-l-2 border-ink-800 pl-3">
      {legs.map((leg, i) => (
        <li key={i} className="text-xs text-ink-200 leading-snug">
          <span className="font-mono text-[10px] uppercase tracking-label text-ink-400 mr-2">
            {leg.sport ?? "—"}
          </span>
          <span className="text-white">{leg.text || formatLeg(leg)}</span>
          {leg.event && (
            <span className="text-ink-600 ml-1.5">· {leg.event}</span>
          )}
        </li>
      ))}
    </ol>
  );
}

function formatLeg(leg: Leg): string {
  const d = leg.detail ?? {};
  switch (leg.type) {
    case "spread":
      return `${d.team ?? ""} ${d.line ?? ""}`.trim();
    case "moneyline":
      return `${d.team ?? ""} ML`.trim();
    case "over_under":
      return `${d.direction ?? "Over"} ${d.total ?? ""}`.trim();
    case "prop":
      return `${d.player ?? ""} ${d.direction ?? "Over"} ${d.line ?? ""} ${d.prop ?? ""}`.trim();
    default:
      return leg.type ?? "leg";
  }
}
