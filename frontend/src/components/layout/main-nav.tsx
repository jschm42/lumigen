"use client";

import { Link, usePathname } from "@/i18n/navigation";
import { AppLocale } from "@/i18n/routing";
import { cn } from "@/lib/cn";

type MainNavProps = {
  locale: AppLocale;
  labels: {
    title: string;
    generate: string;
    gallery: string;
    profiles: string;
    admin: string;
    switchToGerman: string;
    switchToEnglish: string;
  };
};
export function MainNav({ locale, labels }: MainNavProps) {
  const pathname = usePathname();
  const currentPath = pathname ?? "/";

  const galleryPath = "/gallery";
  const profilesPath = "/profiles";
  const adminPath = "/admin";

  return (
    <header className="border-b border-border bg-white/70 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-6 py-4">
        <Link href="/" className="text-lg font-semibold tracking-tight text-ink">
          {labels.title}
        </Link>

        <nav className="flex items-center gap-2 rounded-full border border-border bg-surface p-1">
          <Link
            href="/"
            className={cn(
              "rounded-full px-4 py-2 text-sm font-medium transition",
              currentPath === "/"
                ? "bg-accent text-white"
                : "text-ink hover:bg-accentSoft"
            )}
          >
            {labels.generate}
          </Link>
          <Link
            href={galleryPath}
            className={cn(
              "rounded-full px-4 py-2 text-sm font-medium transition",
              currentPath.startsWith(galleryPath)
                ? "bg-accent text-white"
                : "text-ink hover:bg-accentSoft"
            )}
          >
            {labels.gallery}
          </Link>
          <Link
            href={profilesPath}
            className={cn(
              "rounded-full px-4 py-2 text-sm font-medium transition",
              currentPath.startsWith(profilesPath)
                ? "bg-accent text-white"
                : "text-ink hover:bg-accentSoft"
            )}
          >
            {labels.profiles}
          </Link>
          <Link
            href={adminPath}
            className={cn(
              "rounded-full px-4 py-2 text-sm font-medium transition",
              currentPath.startsWith(adminPath)
                ? "bg-accent text-white"
                : "text-ink hover:bg-accentSoft"
            )}
          >
            {labels.admin}
          </Link>
        </nav>

        <div className="flex items-center gap-2">
          <Link
            href={currentPath || "/"}
            locale="de"
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs font-semibold",
              locale === "de"
                ? "border-accent bg-accent text-white"
                : "border-border bg-white text-ink hover:bg-accentSoft"
            )}
          >
            {labels.switchToGerman}
          </Link>
          <Link
            href={currentPath || "/"}
            locale="en"
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs font-semibold",
              locale === "en"
                ? "border-accent bg-accent text-white"
                : "border-border bg-white text-ink hover:bg-accentSoft"
            )}
          >
            {labels.switchToEnglish}
          </Link>
        </div>
      </div>
    </header>
  );
}
