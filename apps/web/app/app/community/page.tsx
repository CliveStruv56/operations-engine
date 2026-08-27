"use client";

// The community profile: the place this workspace covers, presented the way
// the trust presents it — to a funder, the council, or somebody thinking of
// moving here. Headline figures first, then the fabric of the place by
// category. Dull on purpose, like the register it feeds.

import { useCallback, useEffect, useState } from "react";
import { Spinner } from "@/components/activity";
import { useToast } from "@/components/toast";
import { useAsk } from "@/components/ui/dialog";
import {
  btnPrimary as btn,
  btnQuiet as btnGhost,
  cardPadded as card,
} from "@/components/ui/styles";
import {
  ASSET_CATEGORY_LABELS,
  ASSET_CATEGORY_ORDER,
  CommunityAsset,
  CommunityProfile,
  CommunityStat,
  deleteCommunityAsset,
  deleteCommunityStat,
  getCommunityExport,
  getCommunityProfile,
  listCommunityAssets,
  listCommunityStats,
  submitProfilePdf,
} from "@/lib/community";
import { openPresigned } from "@/lib/groundwork";
import { COMMUNITY_DISABLED, ModuleDisabled, useModuleEnabled } from "../module-gate";
import { AssetEditor } from "./asset-editor";
import { ProfileEditor } from "./profile-editor";
import { StatsEditor } from "./stats-editor";

const attrLabel = (v: string | number | boolean) =>
  typeof v === "boolean" ? (v ? "yes" : "no") : String(v);

function AssetRow({
  asset,
  onEdit,
  onRemoved,
}: {
  asset: CommunityAsset;
  onEdit: () => void;
  onRemoved: () => void;
}) {
  const meta = [
    asset.subcategory,
    asset.settlement,
    asset.status !== "open" ? asset.status : null,
  ].filter(Boolean);
  const details = Object.entries(asset.attributes);
  return (
    <li className="flex items-start justify-between gap-3 border-b border-edge py-2.5 last:border-b-0">
      <div className="min-w-0">
        <p className="text-sm font-medium">
          {asset.name}
          {meta.length > 0 && (
            <span className="ml-2 text-xs font-normal text-ink-faint">{meta.join(" · ")}</span>
          )}
        </p>
        {details.length > 0 && (
          <p className="mt-0.5 text-xs text-ink-muted">
            {details.map(([k, v]) => `${k.replaceAll("_", " ")}: ${attrLabel(v)}`).join(" · ")}
          </p>
        )}
        {asset.description && <p className="mt-0.5 text-xs text-ink-muted">{asset.description}</p>}
        {asset.url && (
          <a
            href={asset.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-0.5 inline-block text-xs text-ink-faint underline hover:text-ink"
          >
            {asset.url}
          </a>
        )}
      </div>
      <span className="flex shrink-0 items-center gap-2 text-xs">
        <button onClick={onEdit} className="font-semibold text-electric-blue hover:underline">
          Edit
        </button>
        <button onClick={onRemoved} className="text-faint hover:text-ink">
          Remove
        </button>
      </span>
    </li>
  );
}

export default function CommunityPage() {
  const enabled = useModuleEnabled("community");
  const toast = useToast();
  const ask = useAsk();
  const [profile, setProfile] = useState<CommunityProfile | null>(null);
  const [assets, setAssets] = useState<CommunityAsset[] | null>(null);
  const [stats, setStats] = useState<CommunityStat[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editingProfile, setEditingProfile] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  // null = closed; "new" = adding; otherwise the row being edited.
  const [assetEdit, setAssetEdit] = useState<CommunityAsset | "new" | null>(null);
  const [statEdit, setStatEdit] = useState<CommunityStat | "new" | null>(null);

  const refresh = useCallback(() => {
    const fail = (e: unknown) => setError(e instanceof Error ? e.message : String(e));
    getCommunityProfile().then(setProfile).catch(fail);
    listCommunityAssets().then(setAssets).catch(fail);
    listCommunityStats().then(setStats).catch(fail);
  }, []);

  useEffect(() => {
    if (enabled) refresh();
  }, [enabled, refresh]);

  if (enabled === undefined) return null;
  if (!enabled) return <ModuleDisabled {...COMMUNITY_DISABLED} />;

  const loading = assets === null || stats === null;
  // Figures that feed the register lead; they are the ones a report opens with.
  const headline = (stats ?? []).filter((s) => s.claim_kind !== null);
  const otherStats = (stats ?? []).filter((s) => s.claim_kind === null);
  const empty = !loading && !profile && (assets ?? []).length === 0 && (stats ?? []).length === 0;

  async function downloadPdf() {
    setPdfBusy(true);
    setError(null);
    try {
      const job = await submitProfilePdf();
      // Same 2s poll as the chat answer export — the render takes seconds.
      for (;;) {
        await new Promise((r) => setTimeout(r, 2000));
        const next = await getCommunityExport(job.id);
        if (next.status === "succeeded" && next.download_url) {
          openPresigned(next.download_url);
          break;
        }
        if (next.status === "failed") throw new Error(next.error ?? "PDF export failed");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPdfBusy(false);
    }
  }

  async function removeAsset(asset: CommunityAsset) {
    const sure = await ask.confirm({
      title: `Remove ${asset.name}?`,
      body: "Its details go with it. Facilities that have closed can be marked closed instead.",
      confirmLabel: "Remove it",
      tone: "danger",
    });
    if (!sure) return;
    try {
      await deleteCommunityAsset(asset.id);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function removeStat(stat: CommunityStat) {
    const sure = await ask.confirm({
      title: `Remove ${stat.label}?`,
      body:
        stat.claim_kind !== null
          ? "The fact it fed stays asserted in Your organisation until you manage it there."
          : undefined,
      confirmLabel: "Remove it",
      tone: "danger",
    });
    if (!sure) return;
    try {
      await deleteCommunityStat(stat.id);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <main className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-4 p-6">
        <header className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h1 className="text-xl font-medium">{profile?.place_name ?? "Your community"}</h1>
            <p className="mt-1 text-sm text-ink-muted">
              {profile?.description ??
                "The place you cover — its services, facilities and figures, kept in one place for funders, the council and residents."}
            </p>
            {profile && (
              <p className="mt-1 text-xs text-ink-faint">
                {[
                  profile.council_area,
                  profile.settlements.length > 0 ? profile.settlements.join(", ") : null,
                  profile.geography_note,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            )}
          </div>
          {!editingProfile && !assetEdit && !statEdit && (
            <div className="flex items-center gap-3">
              {profile && (
                <button onClick={() => void downloadPdf()} disabled={pdfBusy} className={btnGhost}>
                  {pdfBusy ? <Spinner /> : "Download as PDF"}
                </button>
              )}
              <button onClick={() => setEditingProfile(true)} className={btnGhost}>
                {profile ? "Edit the profile" : "Describe the place"}
              </button>
              <button onClick={() => setAssetEdit("new")} className={btnGhost}>
                Add a facility
              </button>
              <button onClick={() => setStatEdit("new")} className={btn}>
                Add a figure
              </button>
            </div>
          )}
        </header>

        {editingProfile && (
          <section className={card}>
            <h2 className="mb-3 font-medium">The place</h2>
            <ProfileEditor
              existing={profile}
              onCancel={() => setEditingProfile(false)}
              onSaved={() => {
                setEditingProfile(false);
                refresh();
              }}
            />
          </section>
        )}

        {assetEdit && (
          <section className={card}>
            <h2 className="mb-3 font-medium">
              {assetEdit === "new" ? "Add a facility or service" : `Edit ${assetEdit.name}`}
            </h2>
            <AssetEditor
              existing={assetEdit === "new" ? null : assetEdit}
              onCancel={() => setAssetEdit(null)}
              onSaved={() => {
                setAssetEdit(null);
                refresh();
              }}
            />
          </section>
        )}

        {statEdit && (
          <section className={card}>
            <h2 className="mb-3 font-medium">
              {statEdit === "new" ? "Add a figure" : `Edit ${statEdit.label}`}
            </h2>
            <StatsEditor
              existing={statEdit === "new" ? null : statEdit}
              onCancel={() => setStatEdit(null)}
              onSaved={(fedRegister) => {
                setStatEdit(null);
                if (fedRegister)
                  toast({ message: "Saved — and asserted in Your organisation." });
                refresh();
              }}
            />
          </section>
        )}

        {error && (
          <p className="rounded-card bg-danger-soft px-3 py-2 text-sm text-danger">{error}</p>
        )}

        {loading ? (
          <p className="flex items-center gap-2 text-sm text-ink-muted">
            <Spinner /> Loading…
          </p>
        ) : empty && !editingProfile && !assetEdit && !statEdit ? (
          <section className={card}>
            <h2 className="font-medium">Nothing here yet</h2>
            <p className="mt-2 text-sm text-ink-muted">
              Start with the place itself — a name and a couple of sentences — then add the
              figures a funding application always asks for (population, households) and the
              facilities that make the case: the school, the ferry, the surgery, the shop.
            </p>
            <div className="mt-4 flex items-center gap-3">
              <button onClick={() => setEditingProfile(true)} className={btn}>
                Describe the place
              </button>
            </div>
          </section>
        ) : (
          <>
            {headline.length > 0 && (
              <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {headline.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setStatEdit(s)}
                    className="rounded-card border border-edge bg-surface p-4 text-left hover:border-edge-strong"
                  >
                    <span className="block font-display text-2xl font-medium">
                      {s.value.toLocaleString("en-GB")}
                    </span>
                    <span className="block text-sm text-ink-muted">{s.label}</span>
                    <span className="mt-0.5 block text-xs text-ink-faint">
                      {[s.period, s.source].filter(Boolean).join(" · ") || " "}
                    </span>
                  </button>
                ))}
              </section>
            )}

            {ASSET_CATEGORY_ORDER.map((category) => {
              const rows = (assets ?? []).filter((a) => a.category === category);
              if (rows.length === 0) return null;
              return (
                <section key={category} className={card}>
                  <h2 className="data mb-1 text-ink-muted uppercase">
                    {ASSET_CATEGORY_LABELS[category]}
                  </h2>
                  <ul>
                    {rows.map((a) => (
                      <AssetRow
                        key={a.id}
                        asset={a}
                        onEdit={() => setAssetEdit(a)}
                        onRemoved={() => void removeAsset(a)}
                      />
                    ))}
                  </ul>
                </section>
              );
            })}

            {otherStats.length > 0 && (
              <section className={card}>
                <h2 className="data mb-1 text-ink-muted uppercase">Other figures</h2>
                <ul>
                  {otherStats.map((s) => (
                    <li
                      key={s.id}
                      className="flex items-baseline justify-between gap-3 border-b border-edge py-2 last:border-b-0"
                    >
                      <span className="min-w-0 text-sm">
                        {s.label}
                        <span className="ml-2 font-medium">{s.value.toLocaleString("en-GB")}</span>
                        {s.unit && <span className="ml-1 text-xs text-ink-faint">{s.unit}</span>}
                        <span className="ml-2 text-xs text-ink-faint">
                          {[s.period, s.source].filter(Boolean).join(" · ")}
                        </span>
                      </span>
                      <span className="flex shrink-0 items-center gap-2 text-xs">
                        <button
                          onClick={() => setStatEdit(s)}
                          className="font-semibold text-electric-blue hover:underline"
                        >
                          Edit
                        </button>
                        <button onClick={() => void removeStat(s)} className="text-faint hover:text-ink">
                          Remove
                        </button>
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {profile?.data_sources_note && (
              <p className="text-xs text-ink-faint">Sources: {profile.data_sources_note}</p>
            )}
          </>
        )}
      </div>
    </main>
  );
}
