from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class OrderEvent:
    order_id: str
    version: int
    status: str


@dataclass
class OrderState:
    status: Optional[str] = None
    next_version: int = 1
    pending: Dict[int, OrderEvent] = field(default_factory=dict)


class EventProcessor:
    def __init__(self) -> None:
        self.orders: Dict[str, OrderState] = {}

    def receive(self, event: OrderEvent) -> List[str]:
        state = self.orders.setdefault(event.order_id, OrderState())

        if event.version < state.next_version:
            return [
                f"{event.order_id}: ignored duplicate version {event.version}"
            ]

        if event.version > state.next_version:
            if event.version in state.pending:
                return [
                    f"{event.order_id}: ignored duplicate version {event.version}"
                ]
            state.pending[event.version] = event
            return [
                f"{event.order_id}: pending version {event.version}; "
                f"waiting for version {state.next_version}"
            ]

        messages = [self._apply(state, event)]
        while state.next_version in state.pending:
            pending_event = state.pending.pop(state.next_version)
            messages.append(self._apply(state, pending_event))
        return messages

    def snapshot(self, order_id: str) -> Tuple[Optional[str], int, List[int]]:
        state = self.orders[order_id]
        return state.status, state.next_version, sorted(state.pending)

    @staticmethod
    def _apply(state: OrderState, event: OrderEvent) -> str:
        state.status = event.status
        state.next_version += 1
        return f"{event.order_id}: applied version {event.version} ({event.status})"


class FencedOrderStore:
    def __init__(self) -> None:
        self._next_token = 1
        self._latest_token: Dict[str, int] = {}
        self._status: Dict[str, str] = {}

    def acquire(self, order_id: str) -> int:
        token = self._next_token
        self._next_token += 1
        self._latest_token[order_id] = token
        return token

    def update(self, order_id: str, token: int, status: str) -> str:
        latest_token = self._latest_token.get(order_id)
        if latest_token is None:
            return f"{order_id}: rejected token {token}; no lease exists"
        if token < latest_token:
            return (
                f"{order_id}: rejected stale token {token}; "
                f"newest token is {latest_token}"
            )
        if token > latest_token:
            return (
                f"{order_id}: rejected token {token}; "
                f"newest token is {latest_token}"
            )
        self._status[order_id] = status
        return f"{order_id}: accepted token {token} ({status})"

    def status(self, order_id: str) -> Optional[str]:
        return self._status.get(order_id)


def run_demo() -> None:
    processor = EventProcessor()
    print("Versioned event ordering")
    for event in (
        OrderEvent("order-100", 2, "PAID"),
        OrderEvent("order-100", 1, "CREATED"),
        OrderEvent("order-100", 2, "PAID"),
    ):
        for message in processor.receive(event):
            print(message)
    print(f"final state: {processor.snapshot('order-100')}")

    print("\nMissing event")
    for message in processor.receive(OrderEvent("order-200", 3, "SHIPPED")):
        print(message)
    print(f"pending state: {processor.snapshot('order-200')}")

    print("\nStale worker fencing")
    store = FencedOrderStore()
    worker_one = store.acquire("order-300")
    worker_two = store.acquire("order-300")
    print(f"worker-1 token: {worker_one}")
    print(f"worker-2 token: {worker_two}")
    print(store.update("order-300", worker_two, "PAID"))
    print(store.update("order-300", worker_one, "SHIPPED"))
    print(f"final state: {store.status('order-300')}")


if __name__ == "__main__":
    run_demo()
