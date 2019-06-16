from kmacoin.objects.xstate import ExtendedState

from typing import Dict, Optional, Any


class Item(object):
    """This class represents an item in a double-linked list."""
    prev_item: Optional['Item']
    next_item: Optional['Item']

    def __init__(self, obj: object):
        self.prev_item = None
        self.next_item = None
        self.obj = obj


class DoubleLinkedList(object):
    """This class represents a double-linked list."""
    def __init__(self):
        self.size = 0
        self.head = Item(None)
        self.tail = Item(None)
        self.head.next_item = self.tail
        self.tail.prev_item = self.head

    def add_to_head(self, item: Item):
        """Add an item to the head of this list."""
        first = self.head.next_item
        self.head.next_item = item
        item.next_item = first
        first.prev_item = item
        item.prev_item = self.head
        self.size += 1

    def remove_from_tail(self):
        """Remove and return the last item of this list."""
        assert self.size > 0
        last = self.tail.prev_item
        self.tail.prev_item = last.prev_item
        last.prev_item.next_item = self.tail
        self.size -= 1
        return last

    def remove(self, item: Item):
        """Remove an item from this list."""
        prev = item.prev_item
        next_ = item.next_item
        prev.next_item = next_
        next_.prev_item = prev
        self.size -= 1


class StateCache(object):
    """An LRU-cache for recent states."""
    items_dict: Dict[Any, Item]

    def __init__(self, max_size: int):
        self.max_size = max_size
        self.items_dll = DoubleLinkedList()
        self.items_dict = {}

    def add(self, key: bytes, value: ExtendedState):
        """Add a key, value pair to this cache."""
        item = Item((key, value))
        self.items_dict[key] = item
        self.items_dll.add_to_head(item)
        if self.items_dll.size > self.max_size:
            removed_item = self.items_dll.remove_from_tail()
            key, value = removed_item.obj
            del self.items_dict[key]

    def get(self, key: bytes) -> ExtendedState:
        """Get a value associated with a key added to this cache before."""
        item = self.items_dict[key]
        self.items_dll.remove(item)
        self.items_dll.add_to_head(item)
        _, value = item.obj
        return value

    def haskey(self, key: bytes) -> bool:
        """Test cache hit/miss."""
        return key in self.items_dict
