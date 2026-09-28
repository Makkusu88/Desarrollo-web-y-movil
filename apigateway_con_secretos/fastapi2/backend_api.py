from fastapi import FastAPI

app = FastAPI(
    title="Backend API es",
    description="API MrSandwich ubicada y enrutada por API gateway"
)

@app.get("/health")
def health():
    return {
        "status": "OK",
        "service": "Backend API"
    }

@app.get("/productos")
def productos():
    return {
        "productos": [
            {"id": 1, "nombre": "Churrasco Italiano", "precio": 5990},
            {"id": 2, "nombre": "Barros Luco", "precio": 5490},
            {"id": 3, "nombre": "Completo Italiano", "precio": 3490}
        ]
    }

@app.get("/ordenes")
def ordenes():
    return {
        "ordenes": [
            {"id": 1001, "estado": "pagada"},
            {"id": 1002, "estado": "pendiente"}
        ]
    }
