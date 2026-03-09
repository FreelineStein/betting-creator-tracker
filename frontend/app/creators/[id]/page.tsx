// Creator profile page — Record card, pick history, W/L breakdown
// TODO: Fetch creator + picks from API

type Props = {
  params: { id: string };
};

export default function CreatorPage({ params }: Props) {
  return (
    <main>
      <h1>Creator Profile</h1>
      <p>Record card for creator {params.id} coming soon.</p>
    </main>
  );
}
