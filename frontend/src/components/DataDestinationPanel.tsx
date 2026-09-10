import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  CheckCircle2,
  Cloud,
  Database,
  FolderCog,
  KeyRound,
  Loader2,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import api from "@/lib/api";

const PROVIDERS = [
  { key: "platform", label: "LucioDigital workspace", icon: Cloud },
  { key: "postgres", label: "PostgreSQL", icon: Database },
  { key: "supabase", label: "Supabase PostgreSQL", icon: Database },
  { key: "rest_api", label: "Custom storage API", icon: FolderCog },
  { key: "google_drive", label: "Google Drive", icon: Cloud },
  { key: "dropbox", label: "Dropbox", icon: Cloud },
  { key: "onedrive", label: "Microsoft OneDrive", icon: Cloud },
];

const EMPTY = {
  label: "",
  configuration: {},
  secrets: {},
};

function SecretInput({ label, value, onChange, testid, multiline = false }) {
  const Tag = multiline ? "textarea" : "input";
  return (
    <label className="block">
      <span className="text-xs text-[var(--mut)]">{label}</span>
      <Tag
        data-testid={testid}
        type={multiline ? undefined : "password"}
        rows={multiline ? 4 : undefined}
        value={value || ""}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1.5 w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2"
      />
    </label>
  );
}

function TextInput({ label, value, onChange, testid, placeholder = "" }) {
  return (
    <label className="block">
      <span className="text-xs text-[var(--mut)]">{label}</span>
      <input
        data-testid={testid}
        value={value || ""}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="mt-1.5 w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2"
      />
    </label>
  );
}

function ProviderFields({ provider, draft, setDraft }) {
  const setConfig = (key, value) => {
    setDraft((current) => ({
      ...current,
      configuration: { ...current.configuration, [key]: value },
    }));
  };
  const setSecret = (key, value) => {
    setDraft((current) => ({
      ...current,
      secrets: { ...current.secrets, [key]: value },
    }));
  };
  const config = draft.configuration;
  const secrets = draft.secrets;

  if (provider === "platform") {
    return null;
  }
  if (provider === "postgres" || provider === "supabase") {
    return (
      <SecretInput
        label={provider === "supabase" ? "Transaction Pooler URI (port 6543)" : "Connection URI"}
        value={secrets.connection_uri}
        onChange={(value) => setSecret("connection_uri", value)}
        testid="data-destination-connection-uri-input"
      />
    );
  }
  if (provider === "rest_api") {
    return (
      <div className="space-y-3">
        <TextInput
          label="HTTPS API base URL"
          value={config.base_url}
          onChange={(value) => setConfig("base_url", value)}
          testid="data-destination-api-url-input"
          placeholder="https://workspace.example.com/api"
        />
        <label className="block">
          <span className="text-xs text-[var(--mut)]">Authentication</span>
          <select
            data-testid="data-destination-api-auth-select"
            value={config.auth_mode || "bearer"}
            onChange={(event) => setConfig("auth_mode", event.target.value)}
            className="mt-1.5 w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2"
          >
            <option value="bearer">Bearer token</option>
            <option value="headers">Custom JSON headers</option>
            <option value="none">No authentication</option>
          </select>
        </label>
        {config.auth_mode !== "none" && (
          <SecretInput
            label={config.auth_mode === "headers" ? "Custom headers JSON" : "Bearer token"}
            value={config.auth_mode === "headers" ? secrets.headers_json : secrets.token}
            onChange={(value) => setSecret(
              config.auth_mode === "headers" ? "headers_json" : "token",
              value,
            )}
            testid="data-destination-api-credentials-input"
            multiline={config.auth_mode === "headers"}
          />
        )}
      </div>
    );
  }
  if (provider === "google_drive") {
    const oauth = config.connection_mode === "oauth";
    return (
      <div className="space-y-3">
        <label className="block">
          <span className="text-xs text-[var(--mut)]">Connection method</span>
          <select
            data-testid="data-destination-google-mode-select"
            value={config.connection_mode || "service_account"}
            onChange={(event) => setConfig("connection_mode", event.target.value)}
            className="mt-1.5 w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-2"
          >
            <option value="service_account">Service account</option>
            <option value="oauth">OAuth application</option>
          </select>
        </label>
        <TextInput
          label="Shared folder ID"
          value={config.folder_id}
          onChange={(value) => setConfig("folder_id", value)}
          testid="data-destination-google-folder-input"
        />
        {oauth ? (
          <>
            <TextInput
              label="OAuth Client ID"
              value={config.client_id}
              onChange={(value) => setConfig("client_id", value)}
              testid="data-destination-google-client-id-input"
            />
            <SecretInput
              label="OAuth Client Secret"
              value={secrets.client_secret}
              onChange={(value) => setSecret("client_secret", value)}
              testid="data-destination-google-client-secret-input"
            />
          </>
        ) : (
          <SecretInput
            label="Service account JSON"
            value={secrets.service_account_json}
            onChange={(value) => setSecret("service_account_json", value)}
            testid="data-destination-google-service-account-input"
            multiline
          />
        )}
      </div>
    );
  }
  if (provider === "dropbox") {
    return (
      <div className="space-y-3">
        <TextInput
          label="App key"
          value={config.app_key}
          onChange={(value) => setConfig("app_key", value)}
          testid="data-destination-dropbox-key-input"
        />
        <SecretInput
          label="App secret"
          value={secrets.app_secret}
          onChange={(value) => setSecret("app_secret", value)}
          testid="data-destination-dropbox-secret-input"
        />
        <TextInput
          label="Destination folder"
          value={config.folder_path}
          onChange={(value) => setConfig("folder_path", value)}
          testid="data-destination-dropbox-folder-input"
          placeholder="/LucioDigital/client-name"
        />
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <TextInput
        label="Entra client ID"
        value={config.entra_tenant_id}
        onChange={(value) => setConfig("entra_tenant_id", value)}
        testid="data-destination-onedrive-client-input"
      />
      <TextInput
        label="Application client ID"
        value={config.client_id}
        onChange={(value) => setConfig("client_id", value)}
        testid="data-destination-onedrive-client-id-input"
      />
      <SecretInput
        label="Application client secret"
        value={secrets.client_secret}
        onChange={(value) => setSecret("client_secret", value)}
        testid="data-destination-onedrive-client-secret-input"
      />
      <TextInput
        label="Drive ID"
        value={config.drive_id}
        onChange={(value) => setConfig("drive_id", value)}
        testid="data-destination-onedrive-drive-input"
      />
      <TextInput
        label="Destination folder item ID"
        value={config.root_item_id}
        onChange={(value) => setConfig("root_item_id", value)}
        testid="data-destination-onedrive-folder-input"
      />
    </div>
  );
}

export default function DataDestinationPanel({ appId }) {
  const [destination, setDestination] = useState(null);
  const [provider, setProvider] = useState("platform");
  const [draft, setDraft] = useState(EMPTY);
  const [busy, setBusy] = useState(false);

  const selected = useMemo(
    () => PROVIDERS.find((item) => item.key === provider) || PROVIDERS[0],
    [provider],
  );
  const SelectedIcon = selected.icon;

  async function load() {
    try {
      const { data } = await api.get(`/apps/${appId}/data-destination`);
      setDestination(data);
      setProvider(data.provider);
      setDraft({ label: data.label || "", configuration: data.configuration || {}, secrets: {} });
    } catch (error) {
      toast.error(error.response?.data?.detail || "Could not load data storage settings");
    }
  }

  useEffect(() => {
    load();
  }, [appId]);

  function choose(nextProvider) {
    setProvider(nextProvider);
    if (nextProvider !== destination?.provider) {
      setDraft({ ...EMPTY, label: PROVIDERS.find((item) => item.key === nextProvider)?.label || "" });
    }
  }

  async function save() {
    setBusy(true);
    try {
      const { data } = await api.put(`/apps/${appId}/data-destination`, { provider, ...draft });
      setDestination(data);
      setDraft({ label: data.label || "", configuration: data.configuration || {}, secrets: {} });
      toast.success(provider === "platform" ? "LucioDigital workspace selected" : "Secure destination saved");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Could not save destination");
    } finally {
      setBusy(false);
    }
  }

  async function test() {
    setBusy(true);
    try {
      const { data } = await api.post(`/apps/${appId}/data-destination/test`);
      toast.success(data.message);
      await load();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Connection test failed");
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    setBusy(true);
    try {
      const { data } = await api.delete(`/apps/${appId}/data-destination`);
      setDestination(data);
      setProvider("platform");
      setDraft({ label: data.label, configuration: {}, secrets: {} });
      toast.success("Returned to the LucioDigital workspace");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Could not reset destination");
    } finally {
      setBusy(false);
    }
  }

  if (!destination) {
    return <div data-testid="data-destination-loading" className="text-sm text-[var(--mut)]">Loading storage choices…</div>;
  }

  return (
    <div data-testid="data-destination-panel" className="max-w-5xl space-y-6">
      <div className="grid lg:grid-cols-[0.9fr_1.1fr] gap-5">
        <section className="card-surface p-5">
          <div className="overline flex items-center gap-2">
            <ShieldCheck size={13} className="text-[var(--acc)]" />
            Client data destination
          </div>
          <div className="mt-4 grid sm:grid-cols-2 gap-2">
            {PROVIDERS.map((item) => {
              const Icon = item.icon;
              const active = provider === item.key;
              return (
                <button
                  key={item.key}
                  data-testid={`data-destination-provider-${item.key}`}
                  onClick={() => choose(item.key)}
                  className={`flex items-center gap-2 p-3 rounded-lg border text-left transition-[border-color,background-color,transform] hover:-translate-y-0.5 ${active ? "border-[var(--acc)] bg-[var(--acc)]/10" : "border-[var(--line)] hover:bg-white/5"}`}
                >
                  <Icon size={15} className={active ? "text-[var(--acc)]" : "text-[var(--mut)]"} />
                  <span className="text-xs font-medium">{item.label}</span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="card-surface p-5">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-[var(--acc)]/10 flex items-center justify-center">
              <SelectedIcon size={16} className="text-[var(--acc)]" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="overline">Primary destination</div>
              <h2 data-testid="data-destination-title" className="font-display text-xl mt-1">
                {selected.label}
              </h2>
            </div>
            <span
              data-testid="data-destination-status"
              className="chip"
              style={{ padding: "3px 8px" }}
            >
              {destination.provider === provider
                ? destination.status.replace(/_/g, " ")
                : "not saved"}
            </span>
          </div>

          <div className="space-y-3 mt-5">
            <TextInput
              label="Connection label"
              value={draft.label}
              onChange={(value) => setDraft((current) => ({ ...current, label: value }))}
              testid="data-destination-label-input"
            />
            <ProviderFields provider={provider} draft={draft} setDraft={setDraft} />
          </div>

          {destination.provider === provider && destination.secret_fields.length > 0 && (
            <div data-testid="data-destination-secret-notice" className="mt-4 flex gap-2 text-xs text-[var(--mut)]">
              <KeyRound size={13} className="shrink-0 text-[var(--acc)]" />
              Connection secrets are encrypted and never shown again. Leave a field blank to keep it.
            </div>
          )}
          {destination.provider === provider && destination.missing_fields.length > 0 && (
            <div data-testid="data-destination-missing-fields" className="mt-4 text-xs text-amber-300">
              Missing: {destination.missing_fields.map((field) => field.replace(/_/g, " ")).join(", ")}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2 mt-5">
            <button
              data-testid="data-destination-save-button"
              onClick={save}
              disabled={busy}
              className="btn-primary text-sm inline-flex items-center gap-2 disabled:opacity-50"
            >
              {busy ? <Loader2 size={14} className="animate-spin" /> : <ShieldCheck size={14} />}
              Save destination
            </button>
            {destination.provider === provider && destination.can_test && (
              <button
                data-testid="data-destination-test-button"
                onClick={test}
                disabled={busy}
                className="btn-ghost text-sm inline-flex items-center gap-2 disabled:opacity-50"
              >
                <RefreshCw size={14} />
                Test connection
              </button>
            )}
            {destination.provider !== "platform" && (
              <button
                data-testid="data-destination-reset-button"
                onClick={reset}
                disabled={busy}
                className="btn-ghost text-sm inline-flex items-center gap-2 disabled:opacity-50"
              >
                <RotateCcw size={14} />
                Use LucioDigital workspace
              </button>
            )}
          </div>
          {destination.last_test_message && destination.provider === provider && (
            <div data-testid="data-destination-test-result" className="mt-4 text-xs text-emerald-300 flex gap-2">
              <CheckCircle2 size={13} />
              {destination.last_test_message}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}