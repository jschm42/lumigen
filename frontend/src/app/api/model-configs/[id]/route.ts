import { Prisma } from "@prisma/client";
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { parseModelConfigFormData } from "@/lib/validation/model-config";

function parseId(raw: string): number | null {
  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

function safeReturnTo(value: FormDataEntryValue | null): string {
  if (typeof value !== "string") {
    return "/de/admin";
  }
  const candidate = value.trim();
  if (!candidate.startsWith("/") || candidate.startsWith("//")) {
    return "/de/admin";
  }
  return candidate;
}

function redirectWithMessage(
  request: Request,
  returnTo: string,
  key: "message" | "error",
  value: string
) {
  const target = new URL(returnTo, request.url);
  target.searchParams.set(key, value);
  return NextResponse.redirect(target, 303);
}

type RouteContext = {
  params: {
    id: string;
  };
};

export async function POST(request: Request, { params }: RouteContext) {
  const modelConfigId = parseId(params.id);
  if (!modelConfigId) {
    const target = new URL("/de/admin", request.url);
    target.searchParams.set("error", "Invalid model config id");
    return NextResponse.redirect(target, 303);
  }

  const formData = await request.formData();
  const returnTo = safeReturnTo(formData.get("returnTo"));
  const actionRaw = formData.get("_action");
  const action =
    typeof actionRaw === "string" ? actionRaw.trim().toLowerCase() : "";

  if (action === "delete") {
    try {
      await prisma.modelConfig.delete({
        where: { id: modelConfigId }
      });
    } catch (error) {
      if (
        error instanceof Prisma.PrismaClientKnownRequestError &&
        error.code === "P2025"
      ) {
        return redirectWithMessage(
          request,
          returnTo,
          "error",
          "Model config not found"
        );
      }
      return redirectWithMessage(
        request,
        returnTo,
        "error",
        "Could not delete model config"
      );
    }

    return redirectWithMessage(
      request,
      returnTo,
      "message",
      "Model config deleted"
    );
  }

  if (action !== "update") {
    return redirectWithMessage(request, returnTo, "error", "Unknown action");
  }

  const parsed = parseModelConfigFormData(formData);
  if (!parsed.success) {
    return redirectWithMessage(
      request,
      returnTo,
      "error",
      parsed.error.issues[0]?.message || "Invalid input"
    );
  }

  try {
    await prisma.modelConfig.update({
      where: { id: modelConfigId },
      data: {
        name: parsed.data.name,
        provider: parsed.data.provider,
        model: parsed.data.model,
        enhancementPrompt: parsed.data.enhancementPrompt
      }
    });
  } catch (error) {
    if (
      error instanceof Prisma.PrismaClientKnownRequestError &&
      error.code === "P2002"
    ) {
      return redirectWithMessage(
        request,
        returnTo,
        "error",
        "Model config name already exists"
      );
    }
    if (
      error instanceof Prisma.PrismaClientKnownRequestError &&
      error.code === "P2025"
    ) {
      return redirectWithMessage(
        request,
        returnTo,
        "error",
        "Model config not found"
      );
    }
    return redirectWithMessage(
      request,
      returnTo,
      "error",
      "Could not update model config"
    );
  }

  return redirectWithMessage(
    request,
    returnTo,
    "message",
    "Model config updated"
  );
}
