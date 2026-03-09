const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "http://localhost:8000";

export interface Creator {
  creator_id: string;
  display_name: string;
  tier: string;
  platforms: { platform: string; handle: string; url: string }[];
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
