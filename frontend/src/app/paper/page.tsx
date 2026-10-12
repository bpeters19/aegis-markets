import Nav from "@/components/nav";
import PaperDashboard from "@/components/paper-dashboard";

export default function PaperPage() {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <Nav />
        <header className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight">Paper trading</h1>
          <p className="mt-1 text-sm text-slate-400">
            Forward paper accounts. Each trading day is recorded after the close by the daily runner and can never be edited.
          </p>
        </header>
        <PaperDashboard />
      </div>
    </main>
  );
}
