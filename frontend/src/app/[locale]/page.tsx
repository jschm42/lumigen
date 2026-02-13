import { getTranslations } from "next-intl/server";
import { GenerateForm } from "@/components/forms/generate-form";
import { prisma } from "@/lib/prisma";

type HomePageProps = {
  params: {
    locale: string;
  };
};

export default async function HomePage({ params: { locale } }: HomePageProps) {
  void locale;
  const t = await getTranslations("Generate");

  const [profiles, presets] = await Promise.all([
    prisma.profile.findMany({
      orderBy: {
        name: "asc"
      },
      select: {
        id: true,
        name: true,
        width: true,
        height: true,
        aspectRatio: true
      }
    }),
    prisma.dimensionPreset.findMany({
      orderBy: {
        name: "asc"
      },
      select: {
        id: true,
        name: true,
        width: true,
        height: true
      }
    })
  ]);

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-ink">{t("headline")}</h1>
        <p className="text-sm text-slate-600">{t("subline")}</p>
      </div>
      <GenerateForm profiles={profiles} presets={presets} />
    </section>
  );
}
