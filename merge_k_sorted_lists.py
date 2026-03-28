import heapq
from typing import List, Optional


class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

    def __repr__(self):
        return f"{self.val}->{self.next}"


def merge_k_lists(lists: List[Optional[ListNode]]) -> Optional[ListNode]:
    """合并 K 个有序链表，时间复杂度 O(N·logK)，空间复杂度 O(K)"""
    # 建立最小堆，每个元素是 (val, list_index, node)
    # list_index 用于在 val 相同时打破平局，避免 node 比较报错
    min_heap = []
    for i, node in enumerate(lists):
        if node:
            heapq.heappush(min_heap, (node.val, i, node))

    dummy = ListNode()
    tail = dummy

    while min_heap:
        val, idx, node = heapq.heappop(min_heap)
        tail.next = node
        tail = tail.next
        if node.next:
            heapq.heappush(min_heap, (node.next.val, idx, node.next))

    return dummy.next


# ---------- 辅助函数 ----------
def build_list(values: List[int]) -> Optional[ListNode]:
    dummy = ListNode()
    tail = dummy
    for v in values:
        tail.next = ListNode(v)
        tail = tail.next
    return dummy.next


def list_to_values(head: Optional[ListNode]) -> List[int]:
    result = []
    while head:
        result.append(head.val)
        head = head.next
    return result


# ---------- 测试 ----------
if __name__ == "__main__":
    # 测试用例 1：常规情况
    lists = [
        build_list([1, 4, 5]),
        build_list([1, 3, 4]),
        build_list([2, 6]),
    ]
    merged = merge_k_lists(lists)
    print(list_to_values(merged))  # [1, 1, 2, 3, 4, 4, 5, 6]

    # 测试用例 2：空数组
    print(list_to_values(merge_k_lists([])))  # []

    # 测试用例 3：包含空链表
    print(list_to_values(merge_k_lists([None, build_list([1])])))  # [1]
