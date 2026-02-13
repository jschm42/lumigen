import { Prisma } from "@prisma/client";
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { profilePayloadSchema } from "@/lib/validation/profile";

export async function POST(request: NextRequest) {
  const payload = await request.json();
  const parsed = profilePayloadSchema.safeParse(payload);

  if (!parsed.success) {
    return NextResponse.json(
      {
        ok: false,
        error: parsed.error.issues[0]?.message || "Invalid input"
      },
      { status: 400 }
    );
  }

  const [modelConfig, storageTemplate] = await Promise.all([
    prisma.modelConfig.findUnique({
      where: { id: parsed.data.modelConfigId },
      select: { id: true, provider: true, model: true }
    }),
    prisma.storageTemplate.findUnique({
      where: { id: parsed.data.storageTemplateId },
      select: { id: true }
    })
  ]);

  if (!modelConfig) {
    return NextResponse.json(
      { ok: false, error: "Selected model does not exist" },
      { status: 400 }
    );
  }
  if (!storageTemplate) {
    return NextResponse.json(
      { ok: false, error: "Selected storage template does not exist" },
      { status: 400 }
    );
  }

  try {
    const profile = await prisma.profile.create({
      data: {
        name: parsed.data.name.trim(),
        provider: modelConfig.provider,
        model: modelConfig.model,
        modelConfigId: modelConfig.id,
        basePrompt: parsed.data.basePrompt.trim() || null,
        negativePrompt: parsed.data.negativePrompt.trim() || null,
        width: parsed.data.width ?? null,
        height: parsed.data.height ?? null,
        aspectRatio: parsed.data.aspectRatio?.trim() || null,
        nImages: parsed.data.nImages,
        seed: parsed.data.seed ?? null,
        outputFormat: parsed.data.outputFormat,
        paramsJson: parsed.data.paramsJson,
        storageTemplateId: storageTemplate.id
      },
      select: {
        id: true
      }
    });

    return NextResponse.json({ ok: true, id: profile.id });
  } catch (error) {
    if (
      error instanceof Prisma.PrismaClientKnownRequestError &&
      error.code === "P2002"
    ) {
      return NextResponse.json(
        { ok: false, error: "Profile name already exists" },
        { status: 400 }
      );
    }
    return NextResponse.json(
      { ok: false, error: "Could not create profile" },
      { status: 500 }
    );
  }
}
