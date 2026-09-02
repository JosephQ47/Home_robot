import unittest

from app import ApiError, MockTaskAdapter, RobotState


class RobotStateTest(unittest.TestCase):
    def setUp(self):
        self.state = RobotState(MockTaskAdapter())
        for task in self.state.bootstrap()["tasks"]:
            self.state.cancel_task(task["task_id"], "test cleanup")

    def test_create_task_validates_trackable_follow_target(self):
        with self.assertRaises(ApiError) as ctx:
            self.state.create_task(
                {
                    "name": "杯子跟随",
                    "map_id": "home1",
                    "area_id": "study",
                    "target_class": "杯子",
                    "mode": "follow",
                    "request_id": "req-1",
                }
            )
        self.assertEqual(ctx.exception.code, "TARGET_NOT_TRACKABLE")

    def test_create_task_is_idempotent_by_request_id(self):
        payload = {
            "name": "客厅搜索",
            "map_id": "home1",
            "area_id": "living",
            "target_class": "人员",
            "mode": "search",
            "request_id": "same-request",
        }
        first = self.state.create_task(payload)
        second = self.state.create_task(payload)
        self.assertEqual(first["task_id"], second["task_id"])

    def test_rejects_new_task_while_active_task_running(self):
        self.state.create_task(
            {
                "name": "客厅搜索",
                "map_id": "home1",
                "area_id": "living",
                "target_class": "人员",
                "mode": "search",
                "request_id": "req-active",
            }
        )
        with self.assertRaises(ApiError) as ctx:
            self.state.create_task(
                {
                    "name": "厨房搜索",
                    "map_id": "home1",
                    "area_id": "kitchen",
                    "target_class": "垃圾桶",
                    "mode": "search",
                    "request_id": "req-busy",
                }
            )
        self.assertEqual(ctx.exception.code, "TASK_BUSY")


if __name__ == "__main__":
    unittest.main()
