
async function iniciarCarrito() {
    const lista = document.querySelector("[data-lineas]");
    const vacio = document.querySelector("[data-vacio]");
    const form = document.querySelector("[data-checkout]");
    const totales = document.querySelector("[data-totales]");
    const error = document.querySelector("[data-error]");
    const boton = document.querySelector("[data-confirmar]");
    const bloqueDireccion = document.querySelector("[data-bloque-direccion]");
    const selectDireccion = form.querySelector('select[name="direccion_id"]');
    const sesion = await obtenerSesion();
    let cotizacion = null;
    let claveIdempotencia = crypto.randomUUID();

    function mostrarError(texto) {
        error.textContent = texto;
        error.hidden = !texto;
    }

    function tipoEntrega() {
        return form.querySelector('input[name="tipo_entrega"]:checked').value;
    }

    function pintarTotales() {
        totales.replaceChildren();
        if (!cotizacion) return;
        const envio = tipoEntrega() === "DELIVERY" ? 1990 : 0;
        totales.append(
            el("div", {}, el("span", {}, "Subtotal"), el("span", {}, formatoPrecio(cotizacion.subtotal))),
            el("div", {}, el("span", {}, "Despacho"), el("span", {}, envio ? formatoPrecio(envio) : "Sin costo")),
            el("div", { class: "total-final" }, el("span", {}, "Total"), el("span", {}, formatoPrecio(cotizacion.subtotal + envio))));
    }

    async function cotizarYPintar() {
        const carrito = leerCarrito();
        vacio.hidden = carrito.length > 0;
        form.hidden = carrito.length === 0;
        lista.replaceChildren();
        cotizacion = null;
        if (!carrito.length) return;
        try {
            cotizacion = await api("/orders/quote", { metodo: "POST", cuerpo: { items: carrito.map(aItem) } });
            mostrarError("");
        } catch (err) {
            mostrarError("No se pudo calcular el total: " + mensajeError(err) + ". Revisa tu pedido.");
        }
        carrito.forEach((linea, i) => {
            const oficial = cotizacion ? cotizacion.items[i] : null;
            const detalle = oficial ? [oficial.opcion, ...oficial.extras].filter(Boolean).join(" · ") : "";
            const menos = el("button", { type: "button", class: "btn-secundario btn-chico", "aria-label": "Quitar uno" }, "−");
            const mas = el("button", { type: "button", class: "btn-secundario btn-chico", "aria-label": "Agregar uno" }, "+");
            const quitar = el("button", { type: "button", class: "btn-peligro btn-chico" }, "Eliminar");
            menos.addEventListener("click", () => cambiarCantidad(i, -1));
            mas.addEventListener("click", () => cambiarCantidad(i, 1));
            quitar.addEventListener("click", () => cambiarCantidad(i, -linea.qty));
            lista.appendChild(el("li", { class: "linea" },
                el("img", { src: linea.imagen || "img/logo-circulo.jpg", alt: "" }),
                el("div", {},
                    el("div", { class: "linea-nombre" }, `${linea.qty} × ${linea.nombre}`),
                    el("div", { class: "linea-detalle" }, detalle),
                    el("div", { class: "botonera", style: "margin-top:6px" }, menos, mas, quitar)),
                el("div", { class: "linea-precio" }, oficial ? formatoPrecio(oficial.total_linea) : "—")));
        });
        pintarTotales();
    }

    function aItem(linea) {
        return { product_id: linea.product_id, option_id: linea.option_id, extras: linea.extras, qty: linea.qty };
    }

    function cambiarCantidad(indice, delta) {
        const carrito = leerCarrito();
        carrito[indice].qty = Math.min(10, carrito[indice].qty + delta);
        if (carrito[indice].qty <= 0) carrito.splice(indice, 1);
        guardarCarrito(carrito);
        claveIdempotencia = crypto.randomUUID();
        cotizarYPintar();
    }

    async function cargarDirecciones() {
        if (!tieneRol(sesion, "cliente")) return;
        try {
            const direcciones = await api("/clients/me/addresses");
            selectDireccion.replaceChildren(...direcciones.map((d) =>
                el("option", { value: d.id }, `${d.alias}: ${d.calle} ${d.numero}, ${d.comuna}`)));
            if (!direcciones.length) {
                selectDireccion.append(el("option", { value: "" }, "No tienes direcciones guardadas"));
            }
        } catch (err) {
            mostrarError(mensajeError(err));
        }
    }

    form.addEventListener("change", (e) => {
        if (e.target.name === "tipo_entrega") {
            bloqueDireccion.hidden = tipoEntrega() !== "DELIVERY";
            pintarTotales();
        }
    });

    if (!sesion.autenticado) {
        boton.textContent = "Inicia sesión para continuar";
    } else if (!tieneRol(sesion, "cliente")) {
        boton.disabled = true;
        mostrarError("Las cuentas del personal no pueden realizar pedidos.");
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!sesion.autenticado) {
            window.location.href = "login.html?volver=carrito.html";
            return;
        }
        const carrito = leerCarrito();
        if (!carrito.length) return;
        const tipo = tipoEntrega();
        if (tipo === "DELIVERY" && !selectDireccion.value) {
            mostrarError("Agrega una dirección de entrega en Mi cuenta.");
            return;
        }
        mostrarError("");
        boton.disabled = true;
        boton.textContent = "Creando pedido...";
        let pedido;
        try {
            pedido = await api("/orders", {
                metodo: "POST",
                cabeceras: { "Idempotency-Key": claveIdempotencia },
                cuerpo: {
                    items: carrito.map(aItem),
                    tipo_entrega: tipo,
                    direccion_id: tipo === "DELIVERY" ? selectDireccion.value : null,
                    notas: form.notas.value.trim() || null
                }
            });
        } catch (err) {
            mostrarError(mensajeError(err));
            boton.disabled = false;
            boton.textContent = "Confirmar y pagar";
            return;
        }
        guardarCarrito([]);
        try {
            boton.textContent = "Redirigiendo al pago...";
            const pago = await api("/payments", { metodo: "POST", cuerpo: { order_id: pedido.id } });
            window.location.href = pago.checkout_url;
        } catch (err) {
            window.location.href = `pedido.html?id=${encodeURIComponent(pedido.id)}`;
        }
    });

    await cargarDirecciones();
    await cotizarYPintar();
}

// --- P06 Seguimiento -> S30 GraphQL resumenPedido (orders + inventory + payments),
//     S22 reintentar pago, S19 anular -------------------------------------------

const CONSULTA_RESUMEN = `
query ResumenPedido($id: ID!) {
  resumenPedido(id: $id) {
    id estado tipoEntrega creadoEn expiraEn subtotal costoEnvio total notas requiereReembolso
    items { nombre opcion extras cantidad totalLinea producto { imagen disponible } }
    historial { estado en motivo }
    pago { estado comprobante }
    direccionEntrega { alias calle numero comuna referencia }
  }
}`;

const ESTADOS_FINALES = ["ENTREGADO", "ANULADO"];

async function iniciarPedido() {
    const sesion = await exigirSesion();
    if (!sesion) return;
    const id = new URLSearchParams(location.search).get("id") || "";
    const carga = document.querySelector("[data-estado-carga]");
    const contenedor = document.querySelector("[data-resumen]");
    const error = document.querySelector("[data-error]");
    let temporizador = null;

    async function cargar() {
        let resp;
        try {
            resp = await graphql(CONSULTA_RESUMEN, { id });
        } catch (err) {
            carga.textContent = mensajeError(err);
            carga.classList.add("error");
            return;
        }
        const pedido = resp.data && resp.data.resumenPedido;
        if (!pedido) {
            carga.textContent = "No encontramos este pedido en tu cuenta.";
            carga.classList.add("error");
            return;
        }
        carga.hidden = true;
        contenedor.hidden = false;
        pintar(pedido, resp.errors || []);
        clearTimeout(temporizador);
        if (!ESTADOS_FINALES.includes(pedido.estado)) {
            temporizador = setTimeout(cargar, 5000);
        }
    }

    function pintar(p, errores) {
        document.querySelector("[data-titulo-pedido]").textContent = `Pedido ${p.id}`;
        document.querySelector("[data-chip]").replaceChildren(chipEstado(p.estado));
        document.querySelector("[data-items]").replaceChildren(...p.items.map((i) =>
            el("li", { class: "linea" },
                el("img", { src: i.producto?.imagen || "img/logo-circulo.jpg", alt: "" }),
                el("div", {},
                    el("div", { class: "linea-nombre" }, `${i.cantidad} × ${i.nombre}`),
                    el("div", { class: "linea-detalle" }, [i.opcion, ...i.extras].filter(Boolean).join(" · "))),
                el("div", { class: "linea-precio" }, formatoPrecio(i.totalLinea)))));
        document.querySelector("[data-totales]").replaceChildren(
            el("div", {}, el("span", {}, "Subtotal"), el("span", {}, formatoPrecio(p.subtotal))),
            el("div", {}, el("span", {}, "Despacho"), el("span", {}, p.costoEnvio ? formatoPrecio(p.costoEnvio) : "Sin costo")),
            el("div", { class: "total-final" }, el("span", {}, "Total"), el("span", {}, formatoPrecio(p.total))));

        const pagoTexto = p.pago
            ? `Pago: ${p.pago.estado.toLowerCase().replace(/_/g, " ")}${p.pago.comprobante ? " · comprobante " + p.pago.comprobante : ""}`
            : (errores.some((e) => e.path?.includes("pago")) ? "Estado del pago no disponible por el momento." : "Pago: aún no iniciado");
        document.querySelector("[data-pago]").textContent = pagoTexto;
        const d = p.direccionEntrega;
        document.querySelector("[data-entrega]").textContent = p.tipoEntrega === "DELIVERY" && d
            ? `Delivery a ${d.calle} ${d.numero}, ${d.comuna}${d.referencia ? " (" + d.referencia + ")" : ""}`
            : "Retiro en el local";
        document.querySelector("[data-historial]").replaceChildren(...p.historial.map((h) =>
            el("li", {}, el("strong", {}, NOMBRES_ESTADO[h.estado] || h.estado), ` · ${formatoFecha(h.en)}`,
                h.motivo ? ` · ${h.motivo}` : "")));

        const acciones = document.querySelector("[data-acciones]");
        acciones.replaceChildren();
        if (p.estado === "PENDIENTE_PAGO" && tieneRol(sesion, "cliente")) {
            const pagar = el("button", { type: "button", class: "btn-primario" }, "Pagar ahora");
            const anular = el("button", { type: "button", class: "btn-peligro" }, "Anular pedido");
            pagar.addEventListener("click", async () => {
                pagar.disabled = true;
                try {
                    const pago = await api("/payments", { metodo: "POST", cuerpo: { order_id: p.id } });
                    window.location.href = pago.checkout_url;
                } catch (err) {
                    mostrarErrorPedido(mensajeError(err));
                    pagar.disabled = false;
                }
            });
            anular.addEventListener("click", async () => {
                if (!confirm("¿Anular este pedido? Se liberarán los productos reservados.")) return;
                anular.disabled = true;
                try {
                    await api(`/orders/${encodeURIComponent(p.id)}/cancel`, { metodo: "POST" });
                    mostrarAviso("Pedido anulado");
                    cargar();
                } catch (err) {
                    mostrarErrorPedido(mensajeError(err));
                    anular.disabled = false;
                }
            });
            acciones.append(pagar, anular);
            if (p.expiraEn) acciones.append(el("p", { class: "nota" }, `Tienes hasta las ${formatoFecha(p.expiraEn)} para pagar.`));
        }
        if (p.requiereReembolso) {
            acciones.append(el("p", { class: "mensaje" }, "Este pedido fue anulado después del pago: el local gestionará la devolución."));
        }
    }

    function mostrarErrorPedido(texto) {
        error.textContent = texto;
        error.hidden = false;
    }

    cargar();
}

document.addEventListener("DOMContentLoaded", () => {
    iniciarCabecera();
    const pagina = document.body.dataset.pagina;
    if (pagina === "carrito") iniciarCarrito();
    else if (pagina === "pedido") iniciarPedido();
});
