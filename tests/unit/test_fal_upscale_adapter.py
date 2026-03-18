from __future__ import annotations

from app.providers.fal_upscale_adapter import FalUpscaleService


def test_resolve_model_path_uses_identifier_path() -> None:
    service = FalUpscaleService()
    resolve_model_path = getattr(service, "_resolve_model_path")

    model_path = resolve_model_path(
        "fal-ai/topaz/upscale/image",
        "https://queue.fal.run/fal-ai/topaz/upscale/image",
    )

    assert model_path == "fal-ai/topaz/upscale/image"


def test_resolve_model_path_from_queue_submit_url() -> None:
    service = FalUpscaleService()
    resolve_model_path = getattr(service, "_resolve_model_path")

    model_path = resolve_model_path(
        None,
        "https://queue.fal.run/fal-ai/clarity-upscaler",
    )

    assert model_path == "fal-ai/clarity-upscaler"


def test_resolve_model_path_from_queue_identifier_url() -> None:
    service = FalUpscaleService()
    resolve_model_path = getattr(service, "_resolve_model_path")

    model_path = resolve_model_path(
        "https://queue.fal.run/fal-ai/custom/upscale",
        "https://queue.fal.run/fal-ai/topaz/upscale/image",
    )

    assert model_path == "fal-ai/custom/upscale"


def test_extract_queue_urls_prefers_submit_urls() -> None:
    service = FalUpscaleService()
    extract_queue_urls = getattr(service, "_extract_queue_urls")

    status_url, response_url = extract_queue_urls(
        submit_result={
            "status_url": "https://queue.fal.run/fal-ai/topaz/upscale/image/requests/abc/status",
            "response_url": "https://queue.fal.run/fal-ai/topaz/upscale/image/requests/abc/response",
        },
        request_id="abc",
        model_path="fal-ai/topaz/upscale/image",
    )

    assert status_url.endswith("/requests/abc/status")
    assert response_url.endswith("/requests/abc/response")


def test_extract_queue_urls_builds_fallback_when_missing() -> None:
    service = FalUpscaleService()
    extract_queue_urls = getattr(service, "_extract_queue_urls")

    status_url, response_url = extract_queue_urls(
        submit_result={},
        request_id="xyz",
        model_path="fal-ai/custom/upscale",
    )

    assert status_url == "https://queue.fal.run/fal-ai/custom/upscale/requests/xyz/status"
    assert response_url == "https://queue.fal.run/fal-ai/custom/upscale/requests/xyz"


def test_extract_result_images_supports_single_image_shape() -> None:
    service = FalUpscaleService()
    extract_result_images = getattr(service, "_extract_result_images")

    images = extract_result_images(
        {
            "image": {
                "url": "https://example.invalid/out.png",
                "content_type": "image/png",
            }
        }
    )

    assert len(images) == 1
    assert images[0]["url"] == "https://example.invalid/out.png"


def test_extract_result_images_supports_nested_data_shape() -> None:
    service = FalUpscaleService()
    extract_result_images = getattr(service, "_extract_result_images")

    images = extract_result_images(
        {
            "data": {
                "image": {
                    "url": "https://example.invalid/out.webp",
                    "content_type": "image/webp",
                }
            }
        }
    )

    assert len(images) == 1
    assert images[0]["url"] == "https://example.invalid/out.webp"
