from fastapi import FastAPI

app = FastAPI(
    title="Backend API en",
    description="API MrSandwich ubicada y enrutada por API gateway"
)

@app.get("/health")
def health():
    return {
        "status": "OK",
        "service": "Backend API"
    }

@app.get("/products")
def products():
    return {
        "products": [
            {"id": 1, "name": "Churrasco Italiano", "price": 5990},
            {"id": 2, "name": "Barros Luco", "price": 5490},
            {"id": 3, "name": "Completo Italiano", "price": 3490}
        ]
    }

@app.get("/orders")
def orders():
    return {
        "orders": [
            {"id": 1001, "status": "paid"},
            {"id": 1002, "status": "pending"}
        ]
    }
