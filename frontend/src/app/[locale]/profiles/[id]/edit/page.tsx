import { ChevronLeft } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { ProfileForm } from "@/components/profiles/profile-form";
import { prisma } from "@/lib/prisma";

type EditProfilePageProps = {
  params: {
    locale: string;
    id: string;
  };
};

export default async function EditProfilePage({
  params: { locale, id }
}: EditProfilePageProps) {
  const profileId = Number(id);
  if (!Number.isInteger(profileId) || profileId <= 0) {
    notFound();
  }

  const t = await getTranslations("Profiles");

  const [profile, modelConfigs, storageTemplates] = await Promise.all([
    prisma.profile.findUnique({
      where: { id: profileId },
      select: {
        id: true,
        name: true,
        modelConfigId: true,
        basePrompt: true,
        negativePrompt: true,
        width: true,
        height: true,
        aspectRatio: true,
        nImages: true,
        seed: true,
        outputFormat: true,
        paramsJson: true,
        storageTemplateId: true
      }
    }),
    prisma.modelConfig.findMany({
      orderBy: { name: "asc" },
      select: {
        id: true,
        name: true,
        provider: true,
        model: true
      }
    }),
    prisma.storageTemplate.findMany({
      orderBy: { name: "asc" },
      select: {
        id: true,
        name: true,
        baseDir: true
      }
    })
  ]);

  if (!profile) {
    notFound();
  }

  return (
    <section className="space-y-6">
      <a
        href={`/${locale}/profiles/${profile.id}`}
        className="inline-flex items-center gap-2 text-sm font-medium text-slate-700 hover:text-ink"
      >
        <ChevronLeft className="h-4 w-4" />
        {t("backToProfile")}
      </a>

      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-ink">
          {t("editProfile")}: {profile.name}
        </h1>
        <p className="text-sm text-slate-600">{t("editSubline")}</p>
      </div>

      <ProfileForm
        mode="edit"
        locale={locale}
        profileId={profile.id}
        modelConfigs={modelConfigs}
        storageTemplates={storageTemplates}
        initialValues={{
          name: profile.name,
          modelConfigId: profile.modelConfigId ?? undefined,
          basePrompt: profile.basePrompt ?? "",
          negativePrompt: profile.negativePrompt ?? "",
          width: profile.width ?? undefined,
          height: profile.height ?? undefined,
          aspectRatio: profile.aspectRatio ?? "",
          nImages: profile.nImages,
          seed: profile.seed ?? undefined,
          outputFormat:
            profile.outputFormat === "jpg" ||
            profile.outputFormat === "png" ||
            profile.outputFormat === "webp"
              ? profile.outputFormat
              : "png",
          paramsJson: profile.paramsJson || "{}",
          storageTemplateId: profile.storageTemplateId
        }}
      />
    </section>
  );
}
