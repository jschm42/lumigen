import { Prisma } from "@prisma/client";
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { parseModelConfigFormData } from "@/lib/validation/model-config";

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

export async function POST(request: Request) {
  const formData = await request.formData();
  const returnTo = safeReturnTo(formData.get("returnTo"));

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
    await prisma.modelConfig.create({
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
    return redirectWithMessage(
      request,
      returnTo,
      "error",
      "Could not create model config"
    );
  }

  return redirectWithMessage(
    request,
    returnTo,
    "message",
    "Model config created"
  );
}
