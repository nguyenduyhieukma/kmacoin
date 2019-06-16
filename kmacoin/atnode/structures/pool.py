from threading import Lock
from typing import Any


class ObjectNotFound(Exception):
    """Raised when an object is not found in a pool."""
    pass


class Pool(object):
    """
    A thread-safe pool, used to cache recently received objects.

    Attributes:
        obj_dict: objects stored as a dict to speed up searching, removing and
            to allow them to be associated with values.
        obj_list: to keep track of the oldest object.
        index: index of the oldest object.
        lock: to synchronize concurrent accesses to the pool.

    """
    def __init__(self, size: int):
        self.obj_dict = {}
        self.obj_list = [None] * size
        self.index = 0
        self.lock = Lock()

    def add(self, obj: Any, val: Any = None) -> bool:
        """
        Try to add an object.

        Args:
            obj: the object to be added.
            val: the value to be associated with the object.

        Returns:
            True if the object is actually added, otherwise False.

        """
        with self.lock:
            if obj in self.obj_dict:  # the object is already added.
                return False

            else:
                # remove the oldest object
                oldest_obj = self.obj_list[self.index]
                if oldest_obj in self.obj_dict:
                    del self.obj_dict[oldest_obj]

                # add the object to `obj_dict` and `obj_list`
                self.obj_dict[obj] = val
                self.obj_list[self.index] = obj

                # update the oldest object
                self.index = (self.index + 1) % len(self.obj_list)

                return True

    def pop(self, obj: object) -> Any:
        """
        Try to get a value associated with an object in this pool. The object
        is also removed.

        Args:
            obj: the object to be removed.

        Raises:
            ObjectNotFound: when the object is not found in this pool.

        Returns:
            The value associated with the object.

        """
        with self.lock:
            if obj in self.obj_dict:
                result = self.obj_dict[obj]
                del self.obj_dict[obj]
                return result
            else:
                raise ObjectNotFound()
