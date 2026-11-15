from functools import lru_cache

from pydantic import TypeAdapter

from app.schemas.crop import Crop
from app.utils.geo import DATA_DIR


@lru_cache(maxsize=1)
def get_crops() -> list[Crop]:
    return TypeAdapter(list[Crop]).validate_json((DATA_DIR / "crops.json").read_bytes())
