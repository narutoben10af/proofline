import asyncio

import pytest

from proofline.providers import GemmaProvider, ProviderUnavailable


def test_gemma_provider_requires_no_live_key_for_tests() -> None:
    provider = GemmaProvider(None, "gemma-4-26b-a4b-it", 30, 1)

    with pytest.raises(ProviderUnavailable, match="not configured"):
        asyncio.run(provider.extract_claims(["public fixture text"]))
