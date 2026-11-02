from dataclasses import dataclass

import httpx

VALET_URL = "https://www.bankofcanada.ca/valet/observations/group/FX_RATES_DAILY/json"
BASE_CURRENCY = "CAD"


@dataclass(frozen=True, slots=True)
class Rates:
    """Exchange rates published by the Bank of Canada on one day.

    Attributes:
        date: Publication date, formatted YYYY-MM-DD
        cad_per_unit: Canadian dollars per unit of each currency, keyed by ISO 4217 code
    """

    date: str
    cad_per_unit: dict[str, float]


def parse_rates(payload: dict) -> Rates:
    """Extract the latest rates from a Valet FX_RATES_DAILY response.

    Discontinued series still report their last observation, so only series published on the
    most recent date are kept.

    Args:
        payload: Decoded Valet response for `?recent=1`

    Returns:
        The latest rates, including CAD itself

    Raises:
        ValueError: If the response has no observations
    """
    observations = payload["observations"]
    if not observations:
        raise ValueError("Bank of Canada returned no exchange rate observations")
    latest = max(observations, key=lambda observation: observation["d"])
    # Series keys look like "FXUSDCAD": the quoted currency sits between "FX" and "CAD".
    rates = {key[2:5]: float(value["v"]) for key, value in latest.items() if key != "d"}
    return Rates(latest["d"], {**rates, BASE_CURRENCY: 1.0})


async def fetch_rates() -> Rates:
    """Fetch the latest daily exchange rates from the Bank of Canada Valet API.

    Returns:
        The latest rates

    Raises:
        httpx.HTTPStatusError: If the API returns an error
        ValueError: If the response has no observations
    """
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(VALET_URL, params={"recent": 1})
    response.raise_for_status()
    return parse_rates(response.json())
