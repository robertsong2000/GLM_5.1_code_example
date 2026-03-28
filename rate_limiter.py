"""
简易限流器：支持滑动窗口和令牌桶两种算法。

特性：
- 多用户隔离（不同用户独立计数）
- 线程安全
- 内存过期自动清理
"""

import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Dict


# ---------- 算法策略（策略模式） ----------

class _Algorithm(ABC):
    """限流算法的抽象基类"""

    @abstractmethod
    def allow(self) -> bool:
        ...

    @abstractmethod
    def is_expired(self) -> bool:
        ...


class _SlidingWindow(_Algorithm):
    """
    滑动窗口算法

    在任意 window_seconds 长度的窗口内，请求数不超过 max_requests。
    用时间戳列表记录每个请求的时刻，窗口外的记录按需淘汰。
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self._max = max_requests
        self._window = window_seconds
        self._timestamps: list[float] = []

    def allow(self) -> bool:
        now = time.monotonic()
        cutoff = now - self._window
        # 淘汰窗口外的旧记录
        self._timestamps = [t for t in self._timestamps if t > cutoff]
        if len(self._timestamps) >= self._max:
            return False
        self._timestamps.append(now)
        return True

    def is_expired(self) -> bool:
        # 超过一个窗口周期没有任何请求则视为过期
        return (
            not self._timestamps
            or time.monotonic() - self._timestamps[-1] > self._window
        )


class _TokenBucket(_Algorithm):
    """
    令牌桶算法

    以固定速率向桶中放入令牌，桶满则丢弃。
    每次请求消耗一枚令牌，桶空则拒绝。
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self._capacity = max_requests
        # 令牌放入速率 = max_requests / window_seconds（个/秒）
        self._rate = max_requests / window_seconds
        self._tokens: float = max_requests  # 初始满桶
        self._last_refill: float = time.monotonic()

    def allow(self) -> bool:
        self._refill()
        if self._tokens < 1.0:
            return False
        self._tokens -= 1.0
        return True

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last_refill = now

    def is_expired(self) -> bool:
        # 已经超过 window_seconds 没有请求，且令牌已恢复满
        return (
            time.monotonic() - self._last_refill > self._window_equivalent()
            and self._tokens >= self._capacity
        )

    def _window_equivalent(self) -> float:
        return self._capacity / self._rate  # == window_seconds


# ---------- 限流器主体 ----------

_ALGORITHM_MAP = {
    "sliding_window": _SlidingWindow,
    "token_bucket": _TokenBucket,
}

_CLEANUP_INTERVAL = 60  # 每 60 秒执行一次过期清理


class RateLimiter:
    """
    限流器

    用法::

        rl = RateLimiter(algorithm="sliding_window", max_requests=100, window_seconds=60)
        rl.allow_request("user_123")  # True / False

    支持的 algorithm 值: "sliding_window", "token_bucket"
    """

    def __init__(
        self,
        algorithm: str = "sliding_window",
        max_requests: int = 100,
        window_seconds: int = 60,
    ):
        if algorithm not in _ALGORITHM_MAP:
            raise ValueError(
                f"未知算法 '{algorithm}'，可选: {list(_ALGORITHM_MAP.keys())}"
            )

        self._algo_cls = _ALGORITHM_MAP[algorithm]
        self._max_requests = max_requests
        self._window_seconds = window_seconds

        # 每个用户一个独立的算法实例
        self._buckets: Dict[str, _Algorithm] = {}
        self._lock = threading.Lock()

        # 后台清理线程（守护线程，主进程退出时自动结束）
        self._stop_event = threading.Event()
        self._cleaner = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleaner.start()

    def allow_request(self, user_id: str) -> bool:
        """判断指定用户的请求是否放行。线程安全。"""
        with self._lock:
            bucket = self._buckets.get(user_id)
            if bucket is None:
                bucket = self._algo_cls(self._max_requests, self._window_seconds)
                self._buckets[user_id] = bucket
            return bucket.allow()

    # ---------- 内部方法 ----------

    def _cleanup_loop(self) -> None:
        """定期清理过期用户数据，释放内存"""
        while not self._stop_event.wait(_CLEANUP_INTERVAL):
            with self._lock:
                expired = [
                    uid
                    for uid, bucket in self._buckets.items()
                    if bucket.is_expired()
                ]
                for uid in expired:
                    del self._buckets[uid]

    def shutdown(self) -> None:
        """停止后台清理线程（可选调用，不调用也安全）"""
        self._stop_event.set()
        self._cleaner.join(timeout=5)

    # 便于测试/调试
    @property
    def active_users(self) -> int:
        with self._lock:
            return len(self._buckets)


# ---------- 简单演示 ----------

if __name__ == "__main__":
    # 演示滑动窗口
    print("=== 滑动窗口 ===")
    rl = RateLimiter(algorithm="sliding_window", max_requests=5, window_seconds=2)
    for i in range(7):
        result = rl.allow_request("alice")
        print(f"  请求 {i + 1}: {'放行' if result else '拒绝'}")
    print(f"  活跃用户数: {rl.active_users}")

    # 演示令牌桶
    print("\n=== 令牌桶 ===")
    rl2 = RateLimiter(algorithm="token_bucket", max_requests=3, window_seconds=1)
    for i in range(5):
        result = rl2.allow_request("bob")
        print(f"  请求 {i + 1}: {'放行' if result else '拒绝'}")
    rl2.shutdown()
