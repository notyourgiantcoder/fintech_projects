import json
from pathlib import Path

import pytest

from finbo.core import FinancialProfile

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"


@pytest.fixture
def samples_dir() -> Path:
    return SAMPLES


@pytest.fixture(params=["in", "us"])
def sample_profile(request) -> FinancialProfile:
    data = json.loads((SAMPLES / f"profile_{request.param}.json").read_text())
    return FinancialProfile.model_validate(data)
