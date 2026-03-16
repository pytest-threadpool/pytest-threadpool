from queue import LifoQueue
from typing import ClassVar


class UserPoolMeta(type):
    """Initializes the user pool on class creation.

    Uses LifoQueue so the most recently returned user is reused first,
    demonstrating resource recycling in parallel tests.
    """

    _user_pool: ClassVar = LifoQueue(4)

    def __new__(cls, *args, **kwargs):
        for i in ["John", "Peter", "Jane", "Maxwell"]:
            cls._user_pool.put(i)
        return super().__new__(cls, *args, **kwargs)

    def get_user(cls):
        return cls._user_pool.get()

    def release_user(cls, user):
        cls._user_pool.put(user)


class UserPool(metaclass=UserPoolMeta): ...
