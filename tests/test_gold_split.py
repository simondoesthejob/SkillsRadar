from skillsradar.gold.split import split_of


def test_split_is_stable_and_roughly_half():
    ids = [f"reed:{i}" for i in range(2000)]
    halves = [split_of(i) for i in ids]
    assert halves == [split_of(i) for i in ids]
    assert 0.45 < halves.count("test") / len(ids) < 0.55


def test_seed_changes_the_split():
    ids = [f"x:{i}" for i in range(200)]
    assert [split_of(i, 1) for i in ids] != [split_of(i, 2) for i in ids]
