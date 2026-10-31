from discount import discounted_price


def test_normal_discount():
    assert discounted_price(100, 20) == 80


def test_zero_discount():
    assert discounted_price(100, 0) == 100


def test_full_discount():
    assert discounted_price(100, 100) == 0
