"""Reusable code templates for test cases.

These generate source strings used by ftdir.makepyfile() or
joinpath().write_text(). Not executed directly.
"""


def sequential_order_class(class_name="TestSeq", decorator=""):
    """Class that verifies sequential execution via sleep + order list.

    Used by package override tests, sequential tests, and anywhere
    we need to prove tests did NOT run in parallel.

    Args:
        class_name: Name for the generated class.
        decorator: Optional decorator line(s) to place before the class.
    """
    prefix = f"{decorator}\n" if decorator else ""
    return (
        "import time\n"
        "\n"
        f"{prefix}"
        f"class {class_name}:\n"
        "    order = []\n"
        "\n"
        "    def test_a(self):\n"
        "        time.sleep(0.05)\n"
        "        self.order.append('a')\n"
        "\n"
        "    def test_b(self):\n"
        "        self.order.append('b')\n"
        "\n"
        "    def test_verify(self):\n"
        "        assert self.order == ['a', 'b']\n"
    )
