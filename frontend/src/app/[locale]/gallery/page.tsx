/* eslint-disable @next/next/no-img-element */
import { getTranslations } from "next-intl/server";
import { prisma } from "@/lib/prisma";

type GalleryPageProps = {
  params: {
    locale: string;
  };
};

function getFastApiBaseUrl() {
  return (
    process.env.NEXT_PUBLIC_FASTAPI_BASE_URL ||
    process.env.FASTAPI_BASE_URL ||
    "http://127.0.0.1:8010"
  ).replace(/\/$/, "");
}

export default async function GalleryPage({
  params: { locale }
}: GalleryPageProps) {
  void locale;
  const t = await getTranslations("Gallery");
  const fastApiBaseUrl = getFastApiBaseUrl();

  const assets = await prisma.asset.findMany({
    orderBy: {
      id: "desc"
    },
    take: 60,
    select: {
      id: true,
      width: true,
      height: true,
      filePath: true,
      galleryFolder: {
        select: {
          path: true
        }
      },
      generation: {
        select: {
          id: true,
          profileName: true,
          promptUser: true,
          status: true
        }
      }
    }
  });

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-ink">{t("headline")}</h1>
        <p className="text-sm text-slate-600">{t("subline")}</p>
      </div>

      {!assets.length ? (
        <div className="rounded-2xl border border-border bg-white/75 p-8 text-sm text-slate-600">
          {t("empty")}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {assets.map((asset) => (
            <article
              key={asset.id}
              className="overflow-hidden rounded-2xl border border-border bg-white shadow-sm"
            >
              <img
                src={`${fastApiBaseUrl}/assets/${asset.id}/thumb`}
                alt={asset.generation?.promptUser || `Asset ${asset.id}`}
                className="h-56 w-full bg-slate-100 object-cover"
                loading="lazy"
              />
              <div className="space-y-3 p-4">
                <div>
                  <p className="text-sm font-semibold text-ink">{asset.generation?.profileName}</p>
                  <p className="line-clamp-2 text-xs text-slate-600">{asset.generation?.promptUser}</p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-slate-600">
                  <span className="rounded-full bg-accentSoft px-2 py-1">{asset.width}x{asset.height}</span>
                  <span className="rounded-full bg-slate-100 px-2 py-1">
                    {asset.generation?.status ?? "unknown"}
                  </span>
                  {asset.galleryFolder?.path ? (
                    <span className="rounded-full bg-slate-100 px-2 py-1">{asset.galleryFolder.path}</span>
                  ) : null}
                </div>
                <div className="flex items-center gap-3 text-xs font-medium text-accent">
                  <a href={`${fastApiBaseUrl}/assets/${asset.id}/file`} target="_blank" rel="noreferrer">
                    {t("openFile")}
                  </a>
                  <a href={`${fastApiBaseUrl}/assets/${asset.id}/download`} target="_blank" rel="noreferrer">
                    {t("download")}
                  </a>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
