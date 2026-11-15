import unittest

from order_simulation import EventProcessor, FencedOrderStore, OrderEvent


class EventProcessorTests(unittest.TestCase):
    def test_out_of_order_events_are_applied_once_in_version_order(self):
        processor = EventProcessor()

        first = processor.receive(OrderEvent("order-1", 2, "PAID"))
        second = processor.receive(OrderEvent("order-1", 1, "CREATED"))
        duplicate = processor.receive(OrderEvent("order-1", 2, "PAID"))

        self.assertEqual(first, [
            "order-1: pending version 2; waiting for version 1"
        ])
        self.assertEqual(second, [
            "order-1: applied version 1 (CREATED)",
            "order-1: applied version 2 (PAID)",
        ])
        self.assertEqual(duplicate, [
            "order-1: ignored duplicate version 2"
        ])
        self.assertEqual(processor.snapshot("order-1"), ("PAID", 3, []))

    def test_later_event_stays_pending_when_version_is_missing(self):
        processor = EventProcessor()

        result = processor.receive(OrderEvent("order-2", 3, "SHIPPED"))
        duplicate = processor.receive(OrderEvent("order-2", 3, "SHIPPED"))

        self.assertEqual(result, [
            "order-2: pending version 3; waiting for version 1"
        ])
        self.assertEqual(duplicate, [
            "order-2: ignored duplicate version 3"
        ])
        self.assertEqual(processor.snapshot("order-2"), (None, 1, [3]))


class FencedOrderStoreTests(unittest.TestCase):
    def test_stale_worker_is_rejected(self):
        store = FencedOrderStore()
        old_token = store.acquire("order-3")
        new_token = store.acquire("order-3")

        self.assertEqual(store.update("order-3", new_token, "PAID"),
                         "order-3: accepted token 2 (PAID)")
        self.assertEqual(store.update("order-3", old_token, "SHIPPED"),
                         "order-3: rejected stale token 1; newest token is 2")
        self.assertEqual(store.status("order-3"), "PAID")

    def test_token_issued_for_another_order_is_rejected(self):
        store = FencedOrderStore()
        token_a = store.acquire("order-a")
        store.acquire("order-b")

        self.assertEqual(store.update("order-a", 2, "PAID"),
                         "order-a: rejected token 2; newest token is 1")
        self.assertIsNone(store.status("order-a"))
        self.assertEqual(token_a, 1)


if __name__ == "__main__":
    unittest.main()
