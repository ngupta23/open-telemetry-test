import pytest

from python_uv_template.hello import main


def test_hello():
    assert main() == "Hello, world!"


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (1, 1, 2),
        (2, 3, 5),
        (10, 5, 15),
        (0, 0, 0),
        (-1, -1, -2),
        (100, 200, 300),
        (-5, 5, 0),
        (3, 7, 10),
        (8, 12, 20),
        (50, 25, 75),
    ],
)
def test_addition(a, b, expected):
    assert a + b == expected
