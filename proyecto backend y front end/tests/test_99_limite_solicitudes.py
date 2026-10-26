import httpx

from conftest import API


def test_rate_limit_login():
    codigos = []
    with httpx.Client(timeout=10) as c:
        for _ in range(40):
            r = c.post(f"{API}/auth/login", json={"email": "nadie@cliente.test", "password": "ClaveErronea1"})
            codigos.append(r.status_code)
            if r.status_code == 429:
                assert r.headers["Retry-After"] == "60"
                break
    assert 429 in codigos
    assert set(codigos[:-1]) <= {401}
