import asyncio
import os

from app.services.toolkit import PrecisoToolkit


async def main() -> None:
    os.environ.setdefault("DISTILL_OFFLINE", "1")

    toolkit = PrecisoToolkit()

    sample_text = (
        "Q4 revenue grew 12% year-over-year with gross margin expansion driven by AI demand."
    )
    distill_result = await toolkit.distill_document(
        sample_text.encode("utf-8"),
        filename="sample.txt",
        mime_type="text/plain",
    )
    print("Distillation result:")
    print(distill_result)

    causal_graph = [
        {
            "head_node": "oil_price",
            "tail_node": "transport_cost",
            "strength": 0.7,
            "relation": "drives",
            "time_granularity": "monthly",
        },
        {
            "head_node": "transport_cost",
            "tail_node": "cpi",
            "strength": 0.5,
            "relation": "feeds",
            "time_granularity": "monthly",
        },
    ]

    simulation = toolkit.predict_impact("oil_price", 0.12, causal_graph)
    print("Causal simulation:")
    print(simulation)


if __name__ == "__main__":
    asyncio.run(main())
