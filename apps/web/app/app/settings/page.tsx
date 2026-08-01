"use client";

import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { deriveBrandVars } from "@/lib/brand";
import { Spinner } from "@/components/activity";
import { useWorkspace, type Tenant } from "../workspace";
import Members from "./members";

const card = "rounded-card border border-edge bg-card p-5 shadow-card";
const input = "w-full rounded-[10px] border border-line bg-surface px-3 py-2 text-sm";
const btn =
  "rounded-[10px] bg-accent px-4 py-2 text-sm font-medium text-accent-ink hover:bg-accent-deep disabled:opacity-50";

function WorkspaceSection({ tenant }: { tenant: Tenant }) {
  const ws = useWorkspace();
  const [name, setName] = useState(tenant.name);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api("/tenants/me", { method: "PATCH", body: JSON.stringify({ name }) }, tenant.id);
      await ws.refreshTenant();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className={card}>
      <h2 className="data mb-3 text-ink-muted uppercase">Workspace</h2>
      <form onSubmit={save} className="flex items-end gap-2">
        <label className="min-w-0 flex-1 text-sm">
          Name
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={`mt-1 ${input}`}
          />
        </label>
        <button type="submit" disabled={saving || name === tenant.name} className={btn}>
          {saving ? <Spinner /> : "Save"}
        </button>
      </form>
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}
      <p className="data mt-3 text-ink-faint uppercase">
        {tenant.plan} plan · {tenant.seats} seats
      </p>
    </section>
  );
}

const LOGO_MIMES = ["image/png", "image/jpeg", "image/webp"];
const PPTX_MIME =
  "application/vnd.openxmlformats-officedocument.presentationml.presentation";

function BrandSection({ tenant }: { tenant: Tenant }) {
  const ws = useWorkspace();
  const stored = typeof tenant.brand?.accent === "string" ? (tenant.brand.accent as string) : "";
  const [accent, setAccent] = useState(stored || "#1f6d53");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const templateRef = useRef<HTMLInputElement>(null);

  async function patchBrand(brand: Record<string, unknown>) {
    await api("/tenants/me", { method: "PATCH", body: JSON.stringify({ brand }) }, tenant.id);
    await ws.refreshTenant();
  }

  async function saveAccent(e: React.FormEvent) {
    e.preventDefault();
    setBusy("colour");
    setError(null);
    try {
      await patchBrand({ ...tenant.brand, accent });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function uploadLogo(file: File) {
    setError(null);
    if (!LOGO_MIMES.includes(file.type)) {
      setError("Logos must be PNG, JPEG or WebP.");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setError("Logos are limited to 2 MB.");
      return;
    }
    setBusy("logo");
    try {
      const presign = await api<{ upload_url: string; logo_key: string }>(
        "/tenants/me/logo",
        { method: "POST", body: JSON.stringify({ mime: file.type, size_bytes: file.size }) },
        tenant.id
      );
      const put = await fetch(presign.upload_url, {
        method: "PUT",
        body: file,
        headers: { "Content-Type": file.type },
      });
      if (!put.ok) throw new Error("Upload failed — try again.");
      await patchBrand({ ...tenant.brand, logo_key: presign.logo_key });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function uploadTemplate(file: File) {
    setError(null);
    if (file.type !== PPTX_MIME && !file.name.endsWith(".pptx")) {
      setError("Templates must be .pptx files (save .potx masters as .pptx first).");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      setError("Templates are limited to 20 MB.");
      return;
    }
    setBusy("template");
    try {
      const presign = await api<{ upload_url: string; template_key: string }>(
        "/tenants/me/slides-template",
        { method: "POST", body: JSON.stringify({ mime: PPTX_MIME, size_bytes: file.size }) },
        tenant.id
      );
      const put = await fetch(presign.upload_url, {
        method: "PUT",
        body: file,
        headers: { "Content-Type": PPTX_MIME },
      });
      if (!put.ok) throw new Error("Upload failed — try again.");
      await patchBrand({ ...tenant.brand, slides_template_key: presign.template_key });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
      if (templateRef.current) templateRef.current.value = "";
    }
  }

  async function removeTemplate() {
    setBusy("template");
    setError(null);
    try {
      const rest = { ...tenant.brand };
      delete rest.slides_template_key;
      await patchBrand(rest);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function removeLogo() {
    setBusy("logo");
    setError(null);
    try {
      const rest = { ...tenant.brand };
      delete rest.logo_key;
      await patchBrand(rest);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className={card}>
      <h2 className="data mb-3 text-ink-muted uppercase">Brand</h2>

      <p className="mb-3 text-xs text-ink-muted">
        Your brand colour appears on exported slide decks and health-card PDFs.
      </p>
      <form onSubmit={saveAccent} className="flex flex-wrap items-end gap-2">
        <label className="text-sm">
          Brand colour
          <span className="mt-1 flex items-center gap-2">
            <input
              type="color"
              value={/^#[0-9a-fA-F]{6}$/.test(accent) ? accent : "#1f6d53"}
              onChange={(e) => setAccent(e.target.value)}
              className="h-9 w-12 cursor-pointer rounded-[10px] border border-line bg-surface"
              aria-label="Pick accent colour"
            />
            <input
              value={accent}
              onChange={(e) => setAccent(e.target.value)}
              pattern="^#[0-9a-fA-F]{6}$"
              title="#rrggbb hex colour"
              className={`w-28 ${input}`}
            />
          </span>
        </label>
        <span
          className="rounded-[10px] px-3 py-2 text-sm"
          style={deriveBrandVars(accent)}
        >
          <span className="rounded-[10px] bg-accent px-2 py-1 text-xs font-medium text-accent-ink">
            Preview
          </span>{" "}
          <span className="rounded-[10px] bg-accent-soft px-2 py-1 text-xs text-accent">soft</span>
        </span>
        <button type="submit" disabled={busy !== null || accent === stored} className={btn}>
          {busy === "colour" ? <Spinner /> : "Save colour"}
        </button>
      </form>

      <div className="mt-5 border-t border-line pt-4">
        <p className="text-sm">Slides template</p>
        <p className="text-xs text-ink-muted">
          A PowerPoint file (.pptx) whose master and layouts brand every exported deck —
          save your corporate template as .pptx first. Up to 20 MB.
        </p>
        <div className="mt-2 flex items-center gap-3">
          {typeof tenant.brand?.slides_template_key === "string" && (
            <span className="stamp bg-accent-soft text-accent">custom template active</span>
          )}
          <input
            ref={templateRef}
            type="file"
            accept={PPTX_MIME}
            onChange={(e) => e.target.files?.[0] && uploadTemplate(e.target.files[0])}
            className="text-xs"
            disabled={busy !== null}
          />
          {busy === "template" && <Spinner className="text-accent" />}
          {typeof tenant.brand?.slides_template_key === "string" && (
            <button
              onClick={removeTemplate}
              disabled={busy !== null}
              className="text-xs text-ink-muted underline hover:text-danger"
            >
              Remove
            </button>
          )}
        </div>
      </div>

      <div className="mt-5 border-t border-line pt-4">
        <p className="text-sm">Logo</p>
        <p className="text-xs text-ink-muted">
          Shown in the sidebar for everyone in this workspace. PNG, JPEG or WebP, up to 2 MB.
        </p>
        <div className="mt-2 flex items-center gap-3">
          {tenant.logo_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={tenant.logo_url} alt="Current logo" className="max-h-10 w-auto" />
          )}
          <input
            ref={fileRef}
            type="file"
            accept={LOGO_MIMES.join(",")}
            onChange={(e) => e.target.files?.[0] && uploadLogo(e.target.files[0])}
            className="text-xs"
            disabled={busy !== null}
          />
          {busy === "logo" && <Spinner className="text-accent" />}
          {tenant.logo_url && (
            <button
              onClick={removeLogo}
              disabled={busy !== null}
              className="text-xs text-ink-muted underline hover:text-danger"
            >
              Remove
            </button>
          )}
        </div>
      </div>

      {error && <p className="mt-3 text-sm text-danger">{error}</p>}
    </section>
  );
}

export default function SettingsPage() {
  const ws = useWorkspace();
  const tenant = ws.tenant;
  if (!tenant) return null;

  if (tenant.role !== "admin" && tenant.role !== "owner") {
    return (
      <main className="flex min-h-0 flex-1 items-center justify-center p-6">
        <p className="text-sm text-ink-muted">
          Workspace settings are managed by your admins.
        </p>
      </main>
    );
  }

  return (
    <main className="min-h-0 flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-5 p-6">
        <header>
          <h1 className="font-display text-[26px] font-medium tracking-[-0.01em]">Workspace settings</h1>
          <p className="mt-0.5 text-sm text-ink-muted">
            Branding, people and roles for {tenant.name}.
          </p>
        </header>
        <WorkspaceSection tenant={tenant} />
        <BrandSection tenant={tenant} />
        <Members tenant={tenant} />
      </div>
    </main>
  );
}
