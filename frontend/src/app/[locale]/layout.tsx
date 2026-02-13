import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { ReactNode } from "react";
import { MainNav } from "@/components/layout/main-nav";
import { AppLocale, routing } from "@/i18n/routing";
import "../globals.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Lumigen React Migration",
  description: "React/Next.js migration frontend for Lumigen"
};

type LocaleLayoutProps = {
  children: ReactNode;
  params: {
    locale: string;
  };
};

export default async function LocaleLayout({
  children,
  params: { locale }
}: LocaleLayoutProps) {
  if (!routing.locales.includes(locale as AppLocale)) {
    notFound();
  }

  const messages = await getMessages();
  const t = await getTranslations("Nav");

  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <MainNav
            locale={locale as AppLocale}
            labels={{
              title: t("title"),
              generate: t("generate"),
              gallery: t("gallery"),
              profiles: t("profiles"),
              admin: t("admin"),
              switchToGerman: t("switchToGerman"),
              switchToEnglish: t("switchToEnglish")
            }}
          />
          <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
