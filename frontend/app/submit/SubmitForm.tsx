"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { usePostHog } from "posthog-js/react";
import { Button, ButtonLink, Panel, SectionHead } from "../../components/brand";
import { formatPickDetail, legText, parlayLegs, sportLabel } from "../lib/picks";
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

export default function SubmitForm({ turnstileSiteKey }: { turnstileSiteKey: string }) {
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

    turnstileWidgetIdRef.current = window.turnstile.render(turnstileContainerRef.current, {
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
    });
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
        err instanceof SubmissionError ? err.message : "Something went wrong. Please try again.";
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
          <span className="block text-[13px] font-semibold uppercase tracking-[0.06em] text-fg-2">
            Post URL
          </span>
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
            className={`mt-2 h-[52px] w-full rounded-control border bg-ground px-4 text-[16px] font-medium text-fg placeholder:text-fg-3 transition-colors duration-150 focus:outline-none focus-visible:outline-none disabled:opacity-50 ${
              urlError ? "border-loss" : "border-line-2 focus:border-win"
            }`}
          />
          {urlError && (
            <p id="tweet-url-error" className="mt-2 text-[13px] font-semibold text-loss">
              {urlError}
            </p>
          )}
        </label>

        <div className="mt-6">
          <div ref={turnstileContainerRef} />
          {!turnstileReady && !turnstileLoadFailed && (
            <p className="text-[13px] text-fg-3">
              Loading verification…
            </p>
          )}
          {turnstileLoadFailed && !turnstileReady && (
            <p className="text-[13px] text-loss">
              Couldn&apos;t load verification (Cloudflare Turnstile may be blocked by an ad-blocker
              or your network). Refresh the page to try again.
            </p>
          )}
        </div>

        {formError && (
          <div role="alert" className="mt-6 rounded-control border border-loss/40 bg-loss-dim px-4 py-3 text-[14px] font-semibold text-loss">
            {formError}
          </div>
        )}

        <Button type="submit" variant="primary" disabled={submitting} className="mt-6 w-full sm:w-auto">
          {submitting ? "Checking the post…" : "Put it on the record"}
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
        message: err instanceof SubmissionError ? err.message : "We couldn't flag that submission.",
      });
    }
  }

  const heading = isNeedsReview
    ? "Held for review"
    : isAlreadyTracked
      ? "Already on the record"
      : "On the record";

  return (
    <section aria-labelledby="submit-result-heading">
      <span
        className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-[12.5px] font-bold uppercase tracking-[0.06em] ${
          isNeedsReview ? "bg-panel-3 text-fg-2" : "bg-win-dim text-win"
        }`}
      >
        <span className={`h-1.5 w-1.5 rounded-full ${isNeedsReview ? "bg-fg-3" : "bg-win"}`} aria-hidden="true" />
        <span id="submit-result-heading">{heading}</span>
      </span>

      <h2 className="mt-4 font-display text-[28px] font-bold uppercase leading-[1.05] text-fg sm:text-[34px]">
        {result.message}
      </h2>

      {isNeedsReview && (
        <p className="mt-3 max-w-[60ch] text-[15px] leading-relaxed text-fg-2">
          We only log picks we can match to a specific scheduled game so the outcome can be settled
          fairly. This one didn&apos;t match cleanly. A human will take a look and decide whether to
          add it to the record.
        </p>
      )}

      {result.creator && (
        <div className="mt-5 text-[15px] text-fg-2">
          <span className="text-fg-3">Creator </span>
          <span className="font-semibold text-fg">{result.creator.display_name}</span>{" "}
          <span className="text-fg-3">{result.creator.handle}</span>
          {result.creator.was_new && (
            <p className="mt-1.5 text-[14px]">
              <span className="font-semibold text-fg">{result.creator.display_name}</span> is new
              to PickReceipts. They appear in{" "}
              <span className="font-semibold text-fg">Division II</span> until they build a track
              record.
            </p>
          )}
        </div>
      )}

      {result.picks_extracted > 0 && (
        <PickList
          title="Picks logged"
          items={result.picks.map((p) => ({
            sport: sportLabel({ sport: p.sport, league: p.league }),
            title: p.event ?? formatPickDetail(p.pick_type, p.pick_detail),
            meta: [p.pick_type, p.odds ?? "", `via ${p.source}`].filter(Boolean).join(" · "),
            legs: p.pick_type === "parlay" ? parlayLegs(p.pick_detail) : [],
          }))}
        />
      )}

      {isNeedsReview && result.unpinned_picks.length > 0 && (
        <PickList
          title="What we saw"
          items={result.unpinned_picks.map((p) => ({
            sport: sportLabel({ sport: p.sport, league: p.league }),
            title: p.event ?? formatPickDetail(p.pick_type, p.pick_detail),
            meta: [p.pick_type, p.odds ?? ""].filter(Boolean).join(" · "),
            legs: p.pick_type === "parlay" ? parlayLegs(p.pick_detail) : [],
          }))}
        />
      )}

      {/* Flag-for-review affordance. Only shown when we actually have a
          Source on file (source_id present) — the parser found at least
          something and we want the user to call out mistakes. */}
      {result.source_id && (
        <div className="mt-6 text-[14px]">
          {flagState.kind === "flagged" ? (
            <p className="text-fg-2">Thanks. We&apos;ll take a look and clean it up.</p>
          ) : (
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-fg-2">
              <span>Picks don&apos;t look right?</span>
              <button
                type="button"
                onClick={onFlag}
                disabled={flagState.kind === "flagging"}
                className="u-link is-on font-semibold text-fg disabled:opacity-50"
              >
                {flagState.kind === "flagging" ? "Flagging…" : "Flag for manual review"}
              </button>
              <span>and we&apos;ll clean it up.</span>
              {flagState.kind === "error" && (
                <span className="mt-1 basis-full text-[13px] font-semibold text-loss">
                  {flagState.message}
                </span>
              )}
            </div>
          )}
        </div>
      )}

      <div className="mt-8 flex flex-wrap items-center gap-3">
        <Button variant="primary" onClick={onSubmitAnother}>
          Submit another
        </Button>
        <ButtonLink href="/" variant="secondary">
          Back to standings
        </ButtonLink>
      </div>
    </section>
  );
}

function PickList({
  title,
  items,
}: {
  title: string;
  items: { sport: string; title: string; meta: string; legs: ReturnType<typeof parlayLegs> }[];
}) {
  return (
    <div className="mt-6">
      <SectionHead count={items.length}>{title}</SectionHead>
      <Panel className="px-[18px]">
        <ul className="divide-y divide-line">
          {items.map((p, i) => (
            <li key={i} className="flex items-start gap-3 py-3">
              <span className="mt-0.5 w-[44px] shrink-0 text-[12px] font-bold uppercase tracking-[0.05em] text-fg-3">
                {p.sport}
              </span>
              <div className="min-w-0">
                <div className="text-[15px] font-semibold text-fg">{p.title}</div>
                <div className="text-[12.5px] text-fg-3">{p.meta}</div>
                {p.legs.length > 0 && (
                  <ol className="mt-1.5 space-y-1 border-l border-line-2 pl-2.5 text-[13px] text-fg-2">
                    {p.legs.map((leg, j) => (
                      <li key={j}>
                        <span className="mr-1.5 text-[11px] font-semibold uppercase tracking-[0.05em] text-fg-3">
                          {sportLabel({ sport: leg.sport ?? null, league: leg.league ?? null })}
                        </span>
                        <span className="font-medium text-fg">{legText(leg)}</span>
                        {leg.event && <span className="text-fg-3"> · {leg.event}</span>}
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
