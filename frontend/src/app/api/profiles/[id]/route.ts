import { Prisma } from "@prisma/client";
import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { profilePayloadSchema } from "@/lib/validation/profile";

type RouteContext = { params: { id: string } };

function parseId(raw: string): number | null {
  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

export async function PATCH(request: NextRequest, { params }: RouteContext) {
  const profileId = parseId(params.id);
  if (!profileId) {
    return NextResponse.json(
      { ok: false, error: "Invalid profile id" },
      { status: 400 }
    );
  }

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

  const [profile, modelConfig, storageTemplate] = await Promise.all([
    prisma.profile.findUnique({
      where: { id: profileId },
      select: { id: true }
    }),
    prisma.modelConfig.findUnique({
      where: { id: parsed.data.modelConfigId },
      select: { id: true, provider: true, model: true }
    }),
    prisma.storageTemplate.findUnique({
      where: { id: parsed.data.storageTemplateId },
      select: { id: true }
    })
  ]);

  if (!profile) {
    return NextResponse.json(
      { ok: false, error: "Profile not found" },
      { status: 404 }
    );
  }
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
    await prisma.profile.update({
      where: { id: profile.id },
      select: { id: true },
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
      }
    });

    return NextResponse.json({ ok: true });
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
      { ok: false, error: "Could not update profile" },
      { status: 500 }
    );
  }
}

export async function DELETE(_request: Request, { params }: RouteContext) {
  const profileId = parseId(params.id);
  if (!profileId) {
    return NextResponse.json(
      { ok: false, error: "Invalid profile id" },
      { status: 400 }
    );
  }

  const profile = await prisma.profile.findUnique({
    where: { id: profileId },
    select: { id: true }
  });
  if (!profile) {
    return NextResponse.json(
      { ok: false, error: "Profile not found" },
      { status: 404 }
    );
  }

  try {
    await prisma.profile.delete({
      where: { id: profile.id },
      select: { id: true }
    });
    return NextResponse.json({ ok: true });
  } catch (error) {
    if (
      error instanceof Prisma.PrismaClientKnownRequestError &&
      error.code === "P2003"
    ) {
      return NextResponse.json(
        {
          ok: false,
          error: "Profile cannot be deleted while generations still reference it"
        },
        { status: 400 }
      );
    }
    return NextResponse.json(
      { ok: false, error: "Could not delete profile" },
      { status: 500 }
    );
  }
}
