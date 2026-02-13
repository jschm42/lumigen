"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import {
  generateRequestSchema,
  type GenerateRequestInput
} from "@/lib/validation/generate";

type ProfileOption = {
  id: number;
  name: string;
  width: number | null;
  height: number | null;
  aspectRatio: string | null;
};

type DimensionPresetOption = {
  id: number;
  name: string;
  width: number;
  height: number;
};

type GenerateFormProps = {
  profiles: ProfileOption[];
  presets: DimensionPresetOption[];
};

type ApiResponse = {
  ok: boolean;
  jobPath?: string | null;
  error?: string;
};

export function GenerateForm({ profiles, presets }: GenerateFormProps) {
  const t = useTranslations("Generate");
  const [serverMessage, setServerMessage] = useState<string>("");
  const [isServerError, setIsServerError] = useState(false);

  const initialProfileId = profiles[0]?.id;

  const form = useForm<GenerateRequestInput>({
    resolver: zodResolver(generateRequestSchema),
    defaultValues: {
      promptUser: "",
      profileId: initialProfileId,
      nImages: 1
    }
  });

  const selectedProfile = useMemo(() => {
    const profileId = form.watch("profileId");
    return profiles.find((profile) => profile.id === Number(profileId)) ?? null;
  }, [form, profiles]);

  async function onSubmit(values: GenerateRequestInput) {
    setServerMessage("");
    setIsServerError(false);

    const response = await fetch("/api/generate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(values)
    });

    const payload = (await response.json()) as ApiResponse;
    if (!response.ok || !payload.ok) {
      setIsServerError(true);
      setServerMessage(payload.error || t("error"));
      return;
    }

    const suffix = payload.jobPath ? ` (${payload.jobPath})` : "";
    setServerMessage(`${t("success")}${suffix}`);
    form.reset({
      ...values,
      promptUser: ""
    });
  }

  if (!profiles.length) {
    return (
      <div className="rounded-2xl border border-amber-300 bg-amber-50 p-5 text-sm text-amber-800">
        {t("emptyProfiles")}
      </div>
    );
  }

  return (
    <form
      onSubmit={form.handleSubmit(onSubmit)}
      className="space-y-6 rounded-3xl border border-border bg-white/80 p-6 shadow-sm"
    >
      <div className="grid gap-5 md:grid-cols-2">
        <label className="md:col-span-2">
          <span className="mb-2 block text-sm font-semibold text-ink">{t("prompt")}</span>
          <textarea
            rows={4}
            placeholder={t("promptPlaceholder")}
            className="w-full rounded-xl border border-border bg-white px-4 py-3 text-sm outline-none transition focus:border-accent"
            {...form.register("promptUser")}
          />
          <p className="mt-1 text-xs text-rose-700">{form.formState.errors.promptUser?.message}</p>
        </label>

        <label>
          <span className="mb-2 block text-sm font-semibold text-ink">{t("profile")}</span>
          <select
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm"
            {...form.register("profileId", { valueAsNumber: true })}
          >
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span className="mb-2 block text-sm font-semibold text-ink">{t("nImages")}</span>
          <input
            type="number"
            min={1}
            max={8}
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm"
            {...form.register("nImages", { valueAsNumber: true })}
          />
        </label>

        <label>
          <span className="mb-2 block text-sm font-semibold text-ink">{t("width")}</span>
          <input
            type="number"
            min={1}
            placeholder={selectedProfile?.width?.toString() ?? ""}
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm"
            {...form.register("width")}
          />
        </label>

        <label>
          <span className="mb-2 block text-sm font-semibold text-ink">{t("height")}</span>
          <input
            type="number"
            min={1}
            placeholder={selectedProfile?.height?.toString() ?? ""}
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm"
            {...form.register("height")}
          />
        </label>

        <label>
          <span className="mb-2 block text-sm font-semibold text-ink">{t("aspectRatio")}</span>
          <input
            type="text"
            placeholder={selectedProfile?.aspectRatio ?? "1:1"}
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm"
            {...form.register("aspectRatio")}
          />
        </label>

        <label>
          <span className="mb-2 block text-sm font-semibold text-ink">{t("seed")}</span>
          <input
            type="number"
            min={1}
            className="w-full rounded-xl border border-border bg-white px-3 py-2 text-sm"
            {...form.register("seed")}
          />
        </label>
      </div>

      {presets.length > 0 ? (
        <section className="space-y-2">
          <p className="text-sm font-semibold text-ink">{t("presets")}</p>
          <div className="flex flex-wrap gap-2">
            {presets.map((preset) => (
              <button
                key={preset.id}
                type="button"
                onClick={() => {
                  form.setValue("width", preset.width);
                  form.setValue("height", preset.height);
                }}
                className="rounded-full border border-border bg-white px-3 py-1.5 text-xs font-medium hover:bg-accentSoft"
              >
                {preset.name} ({preset.width}x{preset.height})
              </button>
            ))}
          </div>
        </section>
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <button
          type="submit"
          disabled={form.formState.isSubmitting}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white transition hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-70"
        >
          <Sparkles className="h-4 w-4" />
          {form.formState.isSubmitting ? t("submitting") : t("submit")}
        </button>
        {serverMessage ? (
          <p className={isServerError ? "text-sm text-rose-700" : "text-sm text-emerald-700"}>
            {serverMessage}
          </p>
        ) : null}
      </div>
    </form>
  );
}
