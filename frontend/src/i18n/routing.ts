import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["de", "en"],
  defaultLocale: "de"
});

export type AppLocale = (typeof routing.locales)[number];
