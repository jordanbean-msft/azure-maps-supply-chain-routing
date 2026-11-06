import hashlib


def route_id(supplier_id: str, factory_id: str, index: int) -> str:
    lane = hashlib.sha256(f"{supplier_id}:{factory_id}".encode()).hexdigest()[:20]
    return f"lane-{lane}-{index}"
