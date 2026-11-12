from calc.core import add, divide, Calculator


def test_add():
    assert add(2, 3) == 5


def test_divide():
    assert divide(10, 2) == 5


def test_calculator_run():
    c = Calculator()
    assert c.run(4, 2) == 3
