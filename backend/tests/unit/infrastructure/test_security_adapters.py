from tests.security import fast_hasher


class TestArgon2:
    def test_hashes_are_salted_and_verifiable(self) -> None:
        hasher = fast_hasher()

        first, second = hasher.hash("senha-forte"), hasher.hash("senha-forte")

        assert first != second  # sal aleatório: mesma senha, hashes diferentes
        assert first.startswith("$argon2id$")
        assert hasher.verify("senha-forte", first)
        assert not hasher.verify("senha-errada", first)

    def test_garbage_hashes_never_verify(self) -> None:
        assert not fast_hasher().verify("qualquer", "isso-nao-e-um-hash")
