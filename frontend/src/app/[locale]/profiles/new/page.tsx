import { ChevronLeft } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { ProfileForm } from "@/components/profiles/profile-form";
import { prisma } from "@/lib/prisma";

type NewProfilePageProps = {
  params: {
    locale: string;
  };
};

export default async function NewProfilePage({
  params: { locale }
}: NewProfilePageProps) {
  const t = await getTranslations("Profiles");

  const [modelConfigs, storageTemplates] = await Promise.all([
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

  return (
    <section className="space-y-6">
      <a
        href={`/${locale}/profiles`}
        className="inline-flex items-center gap-2 text-sm font-medium text-slate-700 hover:text-ink"
      >
        <ChevronLeft className="h-4 w-4" />
        {t("backToList")}
      </a>

      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-ink">{t("newProfile")}</h1>
        <p className="text-sm text-slate-600">{t("createSubline")}</p>
      </div>

      <ProfileForm
        mode="create"
        locale={locale}
        modelConfigs={modelConfigs}
        storageTemplates={storageTemplates}
      />
    </section>
  );
}
