import re
import sys
from pathlib import Path

from grpc_tools import protoc

BACKEND = Path(__file__).resolve().parent.parent / "backend"
SALIDA = BACKEND / "grpc_gen"


def main():
    SALIDA.mkdir(exist_ok=True)
    (SALIDA / "__init__.py").touch()
    for proto in (BACKEND / "proto").glob("*.proto"):
        codigo = protoc.main(["protoc", f"-I{BACKEND / 'proto'}", f"--python_out={SALIDA}",
                              f"--grpc_python_out={SALIDA}", f"--pyi_out={SALIDA}", str(proto)])
        if codigo != 0:
            sys.exit(codigo)
    # protoc genera "import x_pb2"; se cambia a import relativo al paquete.
    for archivo in SALIDA.glob("*_pb2_grpc.py"):
        texto = archivo.read_text(encoding="utf-8")
        texto = re.sub(r"^import (\w+_pb2) as", r"from grpc_gen import \1 as", texto, flags=re.M)
        archivo.write_text(texto, encoding="utf-8")
    print("Código gRPC generado en", SALIDA)


if __name__ == "__main__":
    main()
