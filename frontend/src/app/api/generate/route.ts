import { NextRequest, NextResponse } from "next/server";
import { generateRequestSchema } from "@/lib/validation/generate";

function getFastApiBaseUrl() {
  return (
    process.env.FASTAPI_BASE_URL ||
    process.env.NEXT_PUBLIC_FASTAPI_BASE_URL ||
    "http://127.0.0.1:8010"
  ).replace(/\/$/, "");
}

export async function POST(request: NextRequest) {
  const payload = await request.json();
  const parsed = generateRequestSchema.safeParse(payload);

  if (!parsed.success) {
    return NextResponse.json(
      {
        ok: false,
        error: parsed.error.issues[0]?.message || "Invalid input"
      },
      { status: 400 }
    );
  }

  const body = new URLSearchParams();
  body.set("prompt_user", parsed.data.promptUser);
  body.set("profile_id", String(parsed.data.profileId));
  body.set("n_images", String(parsed.data.nImages));

  if (parsed.data.width) {
    body.set("width", String(parsed.data.width));
  }
  if (parsed.data.height) {
    body.set("height", String(parsed.data.height));
  }
  if (parsed.data.aspectRatio) {
    body.set("aspect_ratio", parsed.data.aspectRatio.trim());
  }
  if (parsed.data.seed) {
    body.set("seed", String(parsed.data.seed));
  }

  const response = await fetch(`${getFastApiBaseUrl()}/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded"
    },
    body,
    redirect: "manual"
  });

  if (response.status >= 300 && response.status < 400) {
    return NextResponse.json({
      ok: true,
      jobPath: response.headers.get("location")
    });
  }

  if (!response.ok) {
    const errorBody = await response.text();
    return NextResponse.json(
      {
        ok: false,
        error: errorBody.slice(0, 500) || "FastAPI rejected request"
      },
      { status: 400 }
    );
  }

  return NextResponse.json({ ok: true, jobPath: null });
}
