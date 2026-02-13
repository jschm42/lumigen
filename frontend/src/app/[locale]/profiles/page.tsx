import { getTranslations } from "next-intl/server";
import { ProfileActions } from "@/components/profiles/profile-actions";
import { prisma } from "@/lib/prisma";

type ProfilesPageProps = {
  params: {
    locale: string;
  };
};

export default async function ProfilesPage({
  params: { locale }
}: ProfilesPageProps) {
  const t = await getTranslations("Profiles");

  const profiles = await prisma.profile.findMany({
    orderBy: {
      name: "asc"
    },
    select: {
      id: true,
      name: true,
      provider: true,
      model: true,
      width: true,
      height: true,
      aspectRatio: true,
      nImages: true,
      outputFormat: true,
      storageTemplate: {
        select: {
          name: true
        }
      }
    }
  });

  return (
    <section className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight text-ink">{t("headline")}</h1>
          <p className="text-sm text-slate-600">{t("subline")}</p>
        </div>
        <a
          href={`/${locale}/profiles/new`}
          className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white hover:brightness-95"
        >
          {t("newProfile")}
        </a>
      </div>

      {!profiles.length ? (
        <div className="rounded-2xl border border-border bg-white/75 p-8 text-sm text-slate-600">
          {t("empty")}
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-border bg-white shadow-sm">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Provider</th>
                <th className="px-4 py-3">Model</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">n</th>
                <th className="px-4 py-3">Output</th>
                <th className="px-4 py-3">Storage</th>
                <th className="px-4 py-3">{t("actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {profiles.map((profile) => (
                <tr key={profile.id} className="hover:bg-slate-50/80">
                  <td className="px-4 py-3 font-medium text-ink">{profile.name}</td>
                  <td className="px-4 py-3 text-slate-700">{profile.provider}</td>
                  <td className="px-4 py-3 text-slate-700">{profile.model}</td>
                  <td className="px-4 py-3 text-slate-700">
                    {profile.width && profile.height
                      ? `${profile.width}x${profile.height}`
                      : profile.aspectRatio || "auto"}
                  </td>
                  <td className="px-4 py-3 text-slate-700">{profile.nImages}</td>
                  <td className="px-4 py-3 text-slate-700">{profile.outputFormat}</td>
                  <td className="px-4 py-3 text-slate-700">{profile.storageTemplate.name}</td>
                  <td className="px-4 py-3">
                    <ProfileActions
                      profileId={profile.id}
                      locale={locale}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
