const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "http://localhost:8000";

// For client-side fetches: use NEXT_PUBLIC_API_URL if set, else fall back to a
// relative URL in deployed environments (vercel.json rewrites /api/* to Railway).
// In local dev the Next dev server doesn't apply vercel.json rewrites, so we
// hit the FastAPI backend directly on :8000.
function browserApiBase(): string {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window === "undefined") return "http://localhost:8000";
  const host = window.location.host;
  if (host.startsWith("localhost") || host.startsWith("127.0.0.1")) {
    return "http://localhost:8000";
  }
  return ""; // relative — the rewrite takes it from here
}

export interface Creator {
  creator_id: string;
  display_name: string;
  tier: string;
  platforms: { platform: string; handle: string; url: string }[];
  profile_image_url: string | null;
  tracking_active: boolean;
}

export interface CreatorRecord {
  creator_id: string;
  total_picks: number;
  wins: number;
  losses: number;
  pushes: number;
  win_rate: number;
  roi: number;
  accuracy_by_sport: Record<string, { wins: number; losses: number }>;
  last_updated: string;
}

export interface Pick {
  pick_id: string;
  creator_id: string;
  sport: string;
  league: string | null;
  event: string;
  event_date: string;
  pick_type: string;
  pick_detail: Record<string, string | number>;
  odds: string;
  units: number;
  status: "pending" | "won" | "lost" | "push" | "void";
  logged_at: string;
  extraction_method: string;
}

export async function getCreators(): Promise<Creator[]> {
  const res = await fetch(`${API_URL}/api/v1/creators/`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch creators");
  return res.json();
}

export async function getCreator(id: string): Promise<Creator> {
  const res = await fetch(`${API_URL}/api/v1/creators/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch creator");
  return res.json();
}

export async function getCreatorRecord(id: string): Promise<CreatorRecord> {
  const res = await fetch(`${API_URL}/api/v1/creators/${id}/record`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch creator record");
  return res.json();
}

export async function getCreatorPicks(id: string): Promise<Pick[]> {
  const res = await fetch(`${API_URL}/api/v1/picks/?creator_id=${id}&limit=50`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch picks");
  return res.json();
}

export async function getAllCreatorsWithRecords(): Promise<
  { creator: Creator; record: CreatorRecord | null }[]
> {
  const creators = await getCreators();
  const results = await Promise.all(
    creators.map(async (creator) => {
      try {
        const record = await getCreatorRecord(creator.creator_id);
        return { creator, record };
      } catch {
        return { creator, record: null };
      }
    })
  );
  return results.sort((a, b) => (b.record?.win_rate ?? 0) - (a.record?.win_rate ?? 0));
}

// ---------------------------------------------------------------------------
// Submissions
// ---------------------------------------------------------------------------

export interface SubmittedPick {
  source: string;
  sport: string | null;
  league: string | null;
  event: string | null;
  pick_type: string;
  pick_detail: Record<string, unknown>;
  odds: string | null;
  confidence: number;
}

export interface UnpinnedPick {
  sport: string | null;
  league: string | null;
  event: string | null;
  pick_type: string;
  pick_detail: Record<string, unknown>;
  odds: string | null;
}

export interface SubmissionSuccess {
  status: "received" | "already_tracked" | "needs_review";
  message: string;
  creator: {
    display_name: string;
    handle: string;
    was_new: boolean;
    pending_review: boolean;
  } | null;
  picks_extracted: number;
  picks: SubmittedPick[];
  // Populated only when status === "needs_review": picks the parser saw but
  // couldn't pin to a scheduled game.
  unpinned_picks: UnpinnedPick[];
}

export class SubmissionError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function submitPick(input: {
  url: string;
  turnstileToken: string;
  honeypot: string;
}): Promise<SubmissionSuccess> {
  let res: Response;
  try {
    res = await fetch(`${browserApiBase()}/api/v1/submissions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: input.url,
        turnstile_token: input.turnstileToken,
        website: input.honeypot,
      }),
    });
  } catch {
    throw new SubmissionError(
      "We couldn't reach the server. Check your connection and try again.",
      0,
    );
  }

  if (res.ok) {
    return (await res.json()) as SubmissionSuccess;
  }

  let detail = "";
  try {
    const body = await res.json();
    detail = typeof body?.detail === "string" ? body.detail : "";
  } catch {
    // ignore — we'll fall back to a status-based message
  }

  if (res.status === 429) {
    throw new SubmissionError(
      "You've submitted a lot of picks recently. Please wait an hour before trying again.",
      429,
    );
  }
  throw new SubmissionError(
    detail || "Something went wrong. Please try again.",
    res.status,
  );
}
