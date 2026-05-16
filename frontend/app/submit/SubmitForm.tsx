"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { usePostHog } from "posthog-js/react";
import { Button } from "../../components/brand";
import {
  flagSubmission,
  submitPick,
  SubmissionError,
  type SubmissionSuccess,
} from "../lib/api";

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

  useEffect(() => {
    if (!turnstileReady) return;
    if (!turnstileContainerRef.current) return;
    if (turnstileWidgetIdRef.current) return;
    if (!window.turnstile) return;

    turnstileWidgetIdRef.current = window.turnstile.render(
      turnstileContainerRef.current,
      {
        sitekey: turnstileSiteKey,
        theme: "light",
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
        needs_review: result.status === "needs_review",
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
        {/* Honeypot — hidden from real users, irresistible to dumb bots. */}
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
          <div className="font-mono text-[10px] uppercase tracking-label-x font-medium text-ink-500 mb-2">
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
            className={`w-full rounded-[10px] border bg-paper-2 px-3.5 py-3 text-ink placeholder:text-ink-300 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-amber-glow disabled:opacity-50 transition-colors ${
              urlError ? "border-amber-deep" : "border-rule hover:border-ink-500"
            }`}
          />
          {urlError && (
            <p id="tweet-url-error" className="mt-2 text-xs text-amber-deep">
              {urlError}
            </p>
          )}
        </label>

        <div className="mt-6">
          <div ref={turnstileContainerRef} />
          {!turnstileReady && !turnstileLoadFailed && (
            <p className="text-xs text-ink-500 font-mono uppercase tracking-label-x">
              Loading verification…
            </p>
          )}
          {turnstileLoadFailed && !turnstileReady && (
            <p className="text-xs text-amber-deep">
              Couldn&apos;t load verification (Cloudflare Turnstile may be blocked
              by an ad-blocker or your network). Refresh the page to try again.
            </p>
          )}
        </div>

        {formError && (
          <div
            role="alert"
            className="mt-6 rounded-[10px] border border-amber-deep/30 bg-amber-dim px-4 py-3 text-sm text-amber-deep"
          >
            {formError}
          </div>
        )}

        <Button
          type="submit"
          variant="accent"
          disabled={submitting}
          className="mt-6 w-full sm:w-auto"
        >
          {submitting ? "Submitting…" : "Submit pick"}
        </Button>
      </form>
    </>
  );
}

type FlagState =
  | { kind: "idle" }
  | { kind: "flagging" }
  | { kind: "flagged" }
  | { kind: "error"; message: string };

function SuccessPanel({
  result,
  onSubmitAnother,
}: {
  result: SubmissionSuccess;
  onSubmitAnother: () => void;
}) {
  const posthog = usePostHog();
  const [flagState, setFlagState] = useState<FlagState>({ kind: "idle" });
  const isNeedsReview = result.status === "needs_review";
  const isAlreadyTracked = result.status === "already_tracked";

  async function onFlag() {
    if (!result.source_id || flagState.kind === "flagging") return;
    setFlagState({ kind: "flagging" });
    posthog?.capture("submission_flag_clicked", {
      source_id: result.source_id,
      submission_status: result.status,
    });
    try {
      await flagSubmission(result.source_id);
      setFlagState({ kind: "flagged" });
    } catch (err) {
      setFlagState({
        kind: "error",
        message:
          err instanceof SubmissionError
            ? err.message
            : "We couldn't flag that submission.",
      });
    }
  }

  const eyebrow = isNeedsReview
    ? "Pending review"
    : isAlreadyTracked
      ? "Already on the record"
      : "Submission received";

  // needs_review and already_tracked both use the muted ink treatment —
  // neither is a "new pick added to the record" outcome.
  const useAmberAccent = !isNeedsReview && !isAlreadyTracked;

  const containerClass = useAmberAccent
    ? "border-amber-deep/30 bg-amber-dim"
    : "border-rule bg-paper-2";
  const eyebrowClass = useAmberAccent ? "text-amber-deep" : "text-ink-500";

  return (
    <div className={`rounded-[16px] border p-6 shadow-card ${containerClass}`}>
      <div
        className={`font-mono text-[10px] uppercase tracking-label-x font-medium mb-3 ${eyebrowClass}`}
      >
        {eyebrow}
      </div>
      <h2 className="font-display font-extrabold text-2xl sm:text-3xl tracking-display leading-tight text-ink">
        {result.message}
      </h2>

      {isNeedsReview && (
        <p className="mt-3 text-sm text-ink-700 leading-relaxed">
          We only log picks we can match to a specific scheduled game so the
          outcome can be settled fairly. This one didn&apos;t match cleanly —
          a human will take a look and decide whether to add it to the record.
        </p>
      )}

      {result.creator && (
        <div className="mt-5 text-sm text-ink-700">
          <div>
            <span className="text-ink-500">Creator: </span>
            <span className="text-ink font-semibold">{result.creator.display_name}</span>{" "}
            <span className="text-ink-500 font-mono">{result.creator.handle}</span>
          </div>
          {result.creator.was_new && (
            <div className="mt-3 rounded-[10px] border border-rule bg-paper-2 px-3.5 py-2.5 text-sm text-ink">
              🎉 <span className="font-semibold">{result.creator.display_name}</span> is new to
              PickReceipts! They&apos;ll appear under{" "}
              <span className="font-semibold">Lesser Known Creators</span> until they build a track
              record.
            </div>
          )}
        </div>
      )}

      {result.picks_extracted > 0 && (
        <ul className="mt-5 space-y-2">
          {result.picks.map((p, i) => (
            <li
              key={i}
              className="rounded-[10px] border border-rule bg-paper-2 px-3.5 py-2.5 text-sm"
            >
              <div className="text-ink">
                <span className="font-mono text-[10px] uppercase tracking-label-x font-medium text-ink-500 mr-2">
                  {p.league ?? p.sport ?? "—"}
                </span>
                {p.event ?? formatPickDetail(p)}
              </div>
              <div className="text-ink-500 text-xs mt-1 font-mono">
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

      {isNeedsReview && result.unpinned_picks.length > 0 && (
        <div className="mt-5">
          <div className="font-mono text-[10px] uppercase tracking-label-x font-medium text-ink-500 mb-2">
            What we saw
          </div>
          <ul className="space-y-2">
            {result.unpinned_picks.map((p, i) => (
              <li
                key={i}
                className="rounded-[10px] border border-rule bg-paper-2 px-3.5 py-2.5 text-sm"
              >
                <div className="text-ink">
                  <span className="font-mono text-[10px] uppercase tracking-label-x font-medium text-ink-500 mr-2">
                    {p.sport ?? "—"}
                  </span>
                  {p.event ??
                    formatPickDetail({ pick_type: p.pick_type, pick_detail: p.pick_detail })}
                </div>
                <div className="text-ink-500 text-xs mt-1 font-mono">
                  {p.pick_type}
                  {p.odds ? ` · ${p.odds}` : ""}
                </div>
                {p.pick_type === "parlay" && <ParlayLegs detail={p.pick_detail} />}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Flag-for-review affordance. Only shown when we actually have a
          Source on file (source_id present) — the parser found at least
          something and we want the user to call out mistakes. */}
      {result.source_id && (
        <div className="mt-5 border-t border-rule-soft pt-4 text-sm">
          {flagState.kind === "flagged" ? (
            <p className="text-ink-700">
              Thanks — we&apos;ll take a look and clean it up.
            </p>
          ) : (
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-ink-500">
              <span>Picks don&apos;t look right?</span>
              <button
                type="button"
                onClick={onFlag}
                disabled={flagState.kind === "flagging"}
                className="font-mono text-[11px] uppercase tracking-label-x font-semibold text-amber-deep underline decoration-amber-deep/40 underline-offset-4 hover:decoration-amber-deep disabled:opacity-50"
              >
                {flagState.kind === "flagging"
                  ? "Flagging…"
                  : "Flag for manual review →"}
              </button>
              <span className="text-ink-500">we&apos;ll clean it up.</span>
              {flagState.kind === "error" && (
                <span className="basis-full text-xs text-amber-deep mt-1">
                  {flagState.message}
                </span>
              )}
            </div>
          )}
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Button variant="accent" onClick={onSubmitAnother}>
          Submit another
        </Button>
        <a
          href="/"
          className="inline-flex items-center justify-center rounded-[10px] px-4 py-2 text-sm font-semibold tracking-tight text-ink-700 hover:text-ink hover:bg-paper-3 transition-colors"
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
  league?: string;
  event?: string;
};

function ParlayLegs({ detail }: { detail: Record<string, unknown> }) {
  const legs = (detail?.legs as Leg[] | undefined) ?? [];
  if (legs.length === 0) return null;
  return (
    <ol className="mt-3 space-y-1.5 border-l-2 border-rule pl-3">
      {legs.map((leg, i) => (
        <li key={i} className="text-xs text-ink-700 leading-snug">
          <span className="font-mono text-[10px] uppercase tracking-label-x font-medium text-ink-500 mr-2">
            {leg.league ?? leg.sport ?? "—"}
          </span>
          <span className="text-ink font-medium">{leg.text || formatLeg(leg)}</span>
          {leg.event && <span className="text-ink-500 ml-1.5">· {leg.event}</span>}
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
