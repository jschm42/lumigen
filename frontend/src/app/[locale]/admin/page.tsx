import { getTranslations } from "next-intl/server";
import { SUPPORTED_PROVIDERS } from "@/lib/providers";
import { prisma } from "@/lib/prisma";

type AdminPageProps = {
  params: {
    locale: string;
  };
  searchParams: {
    message?: string | string[];
    error?: string | string[];
  };
};

function firstParam(value?: string | string[]): string {
  if (Array.isArray(value)) {
    return value[0] || "";
  }
  return value || "";
}

export default async function AdminPage({
  params: { locale },
  searchParams
}: AdminPageProps) {
  const t = await getTranslations("Admin");

  const modelConfigs = await prisma.modelConfig.findMany({
    orderBy: { name: "asc" },
    select: {
      id: true,
      name: true,
      provider: true,
      model: true,
      enhancementPrompt: true,
      apiKeyEncrypted: true,
      _count: {
        select: {
          profiles: true
        }
      }
    }
  });

  const providerOptions = Array.from(
    new Set([
      ...SUPPORTED_PROVIDERS,
      ...modelConfigs.map((config) => config.provider)
    ])
  ).sort((a, b) => a.localeCompare(b));

  const message = firstParam(searchParams.message);
  const error = firstParam(searchParams.error);
  const returnTo = `/${locale}/admin`;

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-ink">{t("headline")}</h1>
        <p className="text-sm text-slate-600">{t("subline")}</p>
      </div>

      {message ? (
        <div className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {message}
        </div>
      ) : null}
      {error ? (
        <div className="rounded-xl border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {error}
        </div>
      ) : null}

      <article className="rounded-3xl border border-border bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-xl font-semibold text-ink">{t("newModel")}</h2>
        <form action="/api/model-configs" method="post" className="grid gap-4 md:grid-cols-2">
          <input type="hidden" name="returnTo" value={returnTo} />

          <label>
            <span className="mb-1 block text-sm font-semibold text-ink">{t("name")}</span>
            <input
              name="name"
              type="text"
              required
              className="w-full rounded-xl border border-border px-3 py-2 text-sm"
            />
          </label>

          <label>
            <span className="mb-1 block text-sm font-semibold text-ink">{t("provider")}</span>
            <select
              name="provider"
              required
              className="w-full rounded-xl border border-border px-3 py-2 text-sm"
              defaultValue={SUPPORTED_PROVIDERS[0]}
            >
              {providerOptions.map((provider) => (
                <option key={provider} value={provider}>
                  {provider}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span className="mb-1 block text-sm font-semibold text-ink">{t("model")}</span>
            <input
              name="model"
              type="text"
              required
              className="w-full rounded-xl border border-border px-3 py-2 text-sm"
            />
          </label>

          <label className="md:col-span-2">
            <span className="mb-1 block text-sm font-semibold text-ink">{t("enhancementPrompt")}</span>
            <textarea
              name="enhancement_prompt"
              rows={3}
              placeholder={t("enhancementPromptPlaceholder")}
              className="w-full rounded-xl border border-border px-3 py-2 text-sm"
            />
          </label>

          <div className="md:col-span-2 flex justify-end">
            <button
              type="submit"
              className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white hover:brightness-95"
            >
              {t("create")}
            </button>
          </div>
        </form>
      </article>

      <article className="rounded-3xl border border-border bg-white p-6 shadow-sm">
        <div className="mb-4 space-y-1">
          <h2 className="text-xl font-semibold text-ink">{t("existingModels")}</h2>
          <p className="text-xs text-slate-500">{t("apiKeyHint")}</p>
        </div>

        {!modelConfigs.length ? (
          <div className="rounded-xl border border-border bg-slate-50 p-4 text-sm text-slate-600">
            {t("empty")}
          </div>
        ) : (
          <div className="space-y-4">
            {modelConfigs.map((config) => (
              <form
                key={config.id}
                action={`/api/model-configs/${config.id}`}
                method="post"
                className="space-y-4 rounded-2xl border border-border bg-white p-4"
              >
                <input type="hidden" name="returnTo" value={returnTo} />

                <div className="grid gap-4 md:grid-cols-2">
                  <label>
                    <span className="mb-1 block text-sm font-semibold text-ink">{t("name")}</span>
                    <input
                      name="name"
                      type="text"
                      defaultValue={config.name}
                      required
                      className="w-full rounded-xl border border-border px-3 py-2 text-sm"
                    />
                  </label>

                  <label>
                    <span className="mb-1 block text-sm font-semibold text-ink">{t("provider")}</span>
                    <select
                      name="provider"
                      defaultValue={config.provider}
                      required
                      className="w-full rounded-xl border border-border px-3 py-2 text-sm"
                    >
                      {providerOptions.map((provider) => (
                        <option key={`${config.id}-${provider}`} value={provider}>
                          {provider}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label>
                    <span className="mb-1 block text-sm font-semibold text-ink">{t("model")}</span>
                    <input
                      name="model"
                      type="text"
                      defaultValue={config.model}
                      required
                      className="w-full rounded-xl border border-border px-3 py-2 text-sm"
                    />
                  </label>

                  <label className="md:col-span-2">
                    <span className="mb-1 block text-sm font-semibold text-ink">{t("enhancementPrompt")}</span>
                    <textarea
                      name="enhancement_prompt"
                      rows={3}
                      defaultValue={config.enhancementPrompt || ""}
                      className="w-full rounded-xl border border-border px-3 py-2 text-sm"
                    />
                  </label>
                </div>

                <div className="flex flex-col gap-3 border-t border-border pt-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs text-slate-500">
                    {t("profilesLinked", { count: config._count.profiles })} | {t("apiKey")}:{" "}
                    {config.apiKeyEncrypted ? t("apiKeyStored") : t("apiKeyNone")}
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      type="submit"
                      name="_action"
                      value="update"
                      className="rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white hover:brightness-95"
                    >
                      {t("save")}
                    </button>
                    <button
                      type="submit"
                      name="_action"
                      value="delete"
                      formNoValidate
                      className="rounded-xl border border-rose-200 px-4 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-50"
                    >
                      {t("delete")}
                    </button>
                  </div>
                </div>
              </form>
            ))}
          </div>
        )}
      </article>
    </section>
  );
}
