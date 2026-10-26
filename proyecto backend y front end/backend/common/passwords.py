import base64
import hashlib
import secrets

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1


def hash_clave(clave: str) -> str:
    sal = secrets.token_bytes(16)
    derivada = hashlib.scrypt(clave.encode(), salt=sal, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return "scrypt${}${}${}${}${}".format(SCRYPT_N, SCRYPT_R, SCRYPT_P,
                                          base64.b64encode(sal).decode(), base64.b64encode(derivada).decode())


def verificar_clave(clave: str, almacenado: str) -> bool:
    _, n, r, p, sal, derivada = almacenado.split("$")
    calculada = hashlib.scrypt(clave.encode(), salt=base64.b64decode(sal), n=int(n), r=int(r), p=int(p), dklen=32)
    return secrets.compare_digest(calculada, base64.b64decode(derivada))
