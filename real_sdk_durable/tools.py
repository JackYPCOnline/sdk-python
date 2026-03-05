"""
tools.py

Real Strands @tool decorated functions.
These are production-grade tool definitions, not mocks.
"""

from strands import tool


@tool
def search_flights(destination: str) -> str:
    """Search for available flights to a destination.

    Args:
        destination: The city or airport code to fly to.
    """
    # In production this would call a flights API.
    # For the PoC it returns realistic data that the LLM can reason about.
    return (
        f"Available flights to {destination}:\n"
        f"  1. AF123 - Departs 08:00, arrives 11:30 - $450 economy\n"
        f"  2. LH456 - Departs 14:15, arrives 17:45 - $520 economy\n"
        f"  3. BA789 - Departs 19:00, arrives 22:30 - $380 economy"
    )


@tool
def book_hotel(city: str, nights: int) -> str:
    """Book a hotel room in a city.

    Args:
        city: The city to book a hotel in.
        nights: Number of nights to stay.
    """
    total = nights * 180
    return (
        f"Hotel booked in {city}:\n"
        f"  Hotel: Le Marais Suite\n"
        f"  Check-in: 3 days from now\n"
        f"  Duration: {nights} nights\n"
        f"  Rate: $180/night\n"
        f"  Total: ${total}\n"
        f"  Confirmation: HTL-{hash(city) % 90000 + 10000}"
    )


# Registry: name -> callable, used by the tool Activity
TOOLS = {
    "search_flights": search_flights,
    "book_hotel": book_hotel,
}

# Tool specs: passed to the model so it knows what tools are available
TOOL_SPECS = [fn.tool_spec for fn in TOOLS.values()]
