"use client";

import { Eye, Pencil, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

type ProfileActionsProps = {
  profileId: number;
  locale: string;
};

type DeleteResponse = {
  ok: boolean;
  error?: string;
};

export function ProfileActions({
  profileId,
  locale
}: ProfileActionsProps) {
  const t = useTranslations("Profiles");
  const router = useRouter();
  const [isDeleting, setIsDeleting] = useState(false);

  async function deleteProfile() {
    if (!window.confirm(t("deleteConfirm"))) {
      return;
    }

    setIsDeleting(true);
    try {
      const response = await fetch(`/api/profiles/${profileId}`, {
        method: "DELETE"
      });
      const payload = (await response.json()) as DeleteResponse;
      if (!response.ok || !payload.ok) {
        window.alert(payload.error || t("deleteError"));
        return;
      }
      router.refresh();
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <a
        href={`/${locale}/profiles/${profileId}`}
        className="inline-flex items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
      >
        <Eye className="h-3.5 w-3.5" />
        {t("open")}
      </a>
      <a
        href={`/${locale}/profiles/${profileId}/edit`}
        className="inline-flex items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
      >
        <Pencil className="h-3.5 w-3.5" />
        {t("edit")}
      </a>
      <button
        type="button"
        disabled={isDeleting}
        onClick={deleteProfile}
        className="inline-flex items-center gap-1 rounded-lg border border-rose-200 px-2.5 py-1.5 text-xs font-medium text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
      >
        <Trash2 className="h-3.5 w-3.5" />
        {isDeleting ? t("deleting") : t("delete")}
      </button>
    </div>
  );
}
