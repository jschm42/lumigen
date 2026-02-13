import { ChevronLeft } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { ProfileActions } from "@/components/profiles/profile-actions";
import { prisma } from "@/lib/prisma";

type ProfileDetailPageProps = {
  params: {
    locale: string;
    id: string;
  };
};

export default async function ProfileDetailPage({
  params: { locale, id }
}: ProfileDetailPageProps) {
  const profileId = Number(id);
  if (!Number.isInteger(profileId) || profileId <= 0) {
    notFound();
  }

  const t = await getTranslations("Profiles");

  const profile = await prisma.profile.findUnique({
    where: { id: profileId },
    select: {
      id: true,
      name: true,
      provider: true,
      model: true,
      basePrompt: true,
      negativePrompt: true,
      width: true,
      height: true,
      aspectRatio: true,
      nImages: true,
      seed: true,
      outputFormat: true,
      paramsJson: true,
      storageTemplate: {
        select: {
          name: true,
          baseDir: true,
          template: true
        }
      }
    }
  });

  if (!profile) {
    notFound();
  }

  const resolution =
    profile.width && profile.height
      ? `${profile.width}x${profile.height}`
      : profile.aspectRatio || "auto";

  return (
    <section className="space-y-6">
      <a
        href={`/${locale}/profiles`}
        className="inline-flex items-center gap-2 text-sm font-medium text-slate-700 hover:text-ink"
      >
        <ChevronLeft className="h-4 w-4" />
        {t("backToList")}
      </a>

      <div className="rounded-3xl border border-border bg-white p-6 shadow-sm">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-ink">
              {profile.name}
            </h1>
            <p className="mt-1 text-sm text-slate-600">
              {profile.provider} - {profile.model}
            </p>
          </div>
          <ProfileActions
            profileId={profile.id}
            locale={locale}
          />
        </div>

        <dl className="grid gap-4 text-sm md:grid-cols-2">
          <div>
            <dt className="text-slate-500">{t("resolution")}</dt>
            <dd className="font-medium text-ink">{resolution}</dd>
          </div>
          <div>
            <dt className="text-slate-500">{t("images")}</dt>
            <dd className="font-medium text-ink">{profile.nImages}</dd>
          </div>
          <div>
            <dt className="text-slate-500">{t("seed")}</dt>
            <dd className="font-medium text-ink">{profile.seed ?? "-"}</dd>
          </div>
          <div>
            <dt className="text-slate-500">{t("output")}</dt>
            <dd className="font-medium text-ink">{profile.outputFormat}</dd>
          </div>
          <div>
            <dt className="text-slate-500">{t("storageTemplate")}</dt>
            <dd className="font-medium text-ink">{profile.storageTemplate.name}</dd>
          </div>
          <div>
            <dt className="text-slate-500">{t("storageBaseDir")}</dt>
            <dd className="font-mono text-xs text-ink">{profile.storageTemplate.baseDir}</dd>
          </div>
        </dl>

        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <div>
            <h2 className="mb-2 text-sm font-semibold text-ink">{t("basePrompt")}</h2>
            <p className="rounded-xl bg-slate-50 p-3 text-sm text-slate-700">
              {profile.basePrompt || "-"}
            </p>
          </div>
          <div>
            <h2 className="mb-2 text-sm font-semibold text-ink">{t("negativePrompt")}</h2>
            <p className="rounded-xl bg-slate-50 p-3 text-sm text-slate-700">
              {profile.negativePrompt || "-"}
            </p>
          </div>
        </div>

        <div className="mt-5">
          <h2 className="mb-2 text-sm font-semibold text-ink">{t("paramsJson")}</h2>
          <pre className="overflow-x-auto rounded-xl bg-slate-900 p-4 text-xs text-slate-100">
            {profile.paramsJson || "{}"}
          </pre>
        </div>
      </div>
    </section>
  );
}
