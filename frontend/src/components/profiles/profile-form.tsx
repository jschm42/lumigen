"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import {
  profilePayloadSchema,
  type ProfilePayloadInput
} from "@/lib/validation/profile";

type ModelConfigOption = {
  id: number;
  name: string;
  provider: string;
  model: string;
};

type StorageTemplateOption = {
  id: number;
  name: string;
  baseDir: string;
};

type ProfileFormProps = {
  mode: "create" | "edit";
  locale: string;
  profileId?: number;
  modelConfigs: ModelConfigOption[];
  storageTemplates: StorageTemplateOption[];
  initialValues?: Partial<ProfilePayloadInput>;
};

type ApiResponse = {
  ok: boolean;
  id?: number;
  error?: string;
};

export function ProfileForm({
  mode,
  locale,
  profileId,
  modelConfigs,
  storageTemplates,
  initialValues
}: ProfileFormProps) {
  const t = useTranslations("Profiles");
  const router = useRouter();
  const [submitError, setSubmitError] = useState("");

  const canSubmit = modelConfigs.length > 0 && storageTemplates.length > 0;

  const defaultModelConfigId = initialValues?.modelConfigId ?? modelConfigs[0]?.id;
  const defaultStorageTemplateId =
    initialValues?.storageTemplateId ?? storageTemplates[0]?.id;

  const form = useForm<ProfilePayloadInput>({
    resolver: zodResolver(profilePayloadSchema),
    defaultValues: {
      name: initialValues?.name ?? "",
      modelConfigId: defaultModelConfigId,
      basePrompt: initialValues?.basePrompt ?? "",
      negativePrompt: initialValues?.negativePrompt ?? "",
      width: initialValues?.width ?? undefined,
      height: initialValues?.height ?? undefined,
      aspectRatio: initialValues?.aspectRatio ?? "",
      nImages: initialValues?.nImages ?? 1,
      seed: initialValues?.seed ?? undefined,
      outputFormat: initialValues?.outputFormat ?? "png",
      paramsJson: initialValues?.paramsJson ?? "{}",
      storageTemplateId: defaultStorageTemplateId
    }
  });

  const selectedModelConfigId = form.watch("modelConfigId");
  const selectedModelConfig = useMemo(() => {
    return (
      modelConfigs.find((item) => item.id === Number(selectedModelConfigId)) ?? null
    );
  }, [modelConfigs, selectedModelConfigId]);

  async function onSubmit(values: ProfilePayloadInput) {
    setSubmitError("");

    const endpoint =
      mode === "create" ? "/api/profiles" : `/api/profiles/${profileId}`;
    const method = mode === "create" ? "POST" : "PATCH";

    const response = await fetch(endpoint, {
      method,
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(values)
    });
    const payload = (await response.json()) as ApiResponse;

    if (!response.ok || !payload.ok) {
      setSubmitError(payload.error || t("saveError"));
      return;
    }

    const targetId = mode === "create" ? payload.id : profileId;
    if (targetId) {
      router.push(`/${locale}/profiles/${targetId}`);
    } else {
      router.push(`/${locale}/profiles`);
    }
    router.refresh();
  }

  return (
    <form
      onSubmit={form.handleSubmit(onSubmit)}
      className="space-y-5 rounded-3xl border border-border bg-white p-6 shadow-sm"
    >
      {!canSubmit ? (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          {t("missingDependencies")}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <label className="md:col-span-2">
          <span className="mb-1 block text-sm font-semibold text-ink">{t("name")}</span>
          <input
            type="text"
            className="w-full rounded-xl border border-border px-3 py-2 text-sm"
            {...form.register("name")}
          />
          <p className="mt-1 text-xs text-rose-700">{form.formState.errors.name?.message}</p>
        </label>

        <label>
          <span className="mb-1 block text-sm font-semibold text-ink">{t("model")}</span>
          <select
            className="w-full rounded-xl border border-border px-3 py-2 text-sm"
            {...form.register("modelConfigId", { valueAsNumber: true })}
          >
            {modelConfigs.map((config) => (
              <option key={config.id} value={config.id}>
                {config.name} ({config.provider} / {config.model})
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-slate-500">
            {selectedModelConfig
              ? `${selectedModelConfig.provider} / ${selectedModelConfig.model}`
              : t("noModelConfig")}
          </p>
        </label>

        <label>
          <span className="mb-1 block text-sm font-semibold text-ink">{t("storageTemplate")}</span>
          <select
            className="w-full rounded-xl border border-border px-3 py-2 text-sm"
            {...form.register("storageTemplateId", { valueAsNumber: true })}
          >
            {storageTemplates.map((storage) => (
              <option key={storage.id} value={storage.id}>
                {storage.name} :: {storage.baseDir}
              </option>
            ))}
          </select>
        </label>

        <label className="md:col-span-2">
          <span className="mb-1 block text-sm font-semibold text-ink">{t("basePrompt")}</span>
          <textarea
            rows={3}
            className="w-full rounded-xl border border-border px-3 py-2 text-sm"
            {...form.register("basePrompt")}
          />
        </label>

        <label className="md:col-span-2">
          <span className="mb-1 block text-sm font-semibold text-ink">{t("negativePrompt")}</span>
          <textarea
            rows={2}
            className="w-full rounded-xl border border-border px-3 py-2 text-sm"
            {...form.register("negativePrompt")}
          />
        </label>

        <label>
          <span className="mb-1 block text-sm font-semibold text-ink">{t("width")}</span>
          <input
            type="number"
            min={1}
            className="w-full rounded-xl border border-border px-3 py-2 text-sm"
            {...form.register("width")}
          />
        </label>
        <label>
          <span className="mb-1 block text-sm font-semibold text-ink">{t("height")}</span>
          <input
            type="number"
            min={1}
            className="w-full rounded-xl border border-border px-3 py-2 text-sm"
            {...form.register("height")}
          />
        </label>
        <label>
          <span className="mb-1 block text-sm font-semibold text-ink">{t("aspectRatio")}</span>
          <input
            type="text"
            placeholder="1:1"
            className="w-full rounded-xl border border-border px-3 py-2 text-sm"
            {...form.register("aspectRatio")}
          />
        </label>
        <label>
          <span className="mb-1 block text-sm font-semibold text-ink">{t("images")}</span>
          <input
            type="number"
            min={1}
            max={8}
            className="w-full rounded-xl border border-border px-3 py-2 text-sm"
            {...form.register("nImages", { valueAsNumber: true })}
          />
        </label>
        <label>
          <span className="mb-1 block text-sm font-semibold text-ink">{t("seed")}</span>
          <input
            type="number"
            min={1}
            className="w-full rounded-xl border border-border px-3 py-2 text-sm"
            {...form.register("seed")}
          />
        </label>
        <label>
          <span className="mb-1 block text-sm font-semibold text-ink">{t("output")}</span>
          <select
            className="w-full rounded-xl border border-border px-3 py-2 text-sm"
            {...form.register("outputFormat")}
          >
            <option value="png">png</option>
            <option value="jpg">jpg</option>
            <option value="webp">webp</option>
          </select>
        </label>

        <label className="md:col-span-2">
          <span className="mb-1 block text-sm font-semibold text-ink">{t("paramsJson")}</span>
          <textarea
            rows={5}
            className="w-full rounded-xl border border-border px-3 py-2 font-mono text-xs"
            {...form.register("paramsJson")}
          />
          <p className="mt-1 text-xs text-rose-700">
            {form.formState.errors.paramsJson?.message}
          </p>
        </label>
      </div>

      {submitError ? <p className="text-sm text-rose-700">{submitError}</p> : null}

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={form.formState.isSubmitting || !canSubmit}
          className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
        >
          {form.formState.isSubmitting
            ? t("saving")
            : mode === "create"
              ? t("create")
              : t("update")}
        </button>
        <a
          href={`/${locale}/profiles`}
          className="rounded-xl border border-border px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          {t("cancel")}
        </a>
      </div>
    </form>
  );
}
