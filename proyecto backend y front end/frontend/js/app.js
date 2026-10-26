
function crearTarjeta(producto) {
    const tarjeta = el("a", { class: "tarjeta" + (producto.disponible ? "" : " agotado"), href: `producto.html?id=${producto.id}` },
        el("div", { class: "tarjeta-texto" },
            el("h2", { class: "tarjeta-nombre" }, producto.nombre),
            el("p", { class: "tarjeta-descripcion" }, producto.descripcion),
            el("span", { class: "tarjeta-precio" }, producto.disponible ? formatoPrecio(producto.precio) : "Agotado")),
        el("img", { class: "tarjeta-imagen", src: producto.imagen, alt: producto.nombre, loading: "lazy" }));
    return tarjeta;
}

async function iniciarInicio() {
    const grilla = document.querySelector(".grilla-productos");
    const estado = document.querySelector(".catalogo-estado");
    const nav = document.querySelector(".categorias");
    const inputBusqueda = document.querySelector(".barra-busqueda input");

    const filtro = { categoria: null, texto: "" };
    const params = new URLSearchParams(window.location.search);
    if (params.get("q")) {
        filtro.texto = params.get("q");
        inputBusqueda.value = filtro.texto;
        document.querySelector(".barra-busqueda").hidden = false;
    }
    filtro.categoria = params.get("categoria");

    let productos = [];
    try {
        const [categorias, lista] = await Promise.all([api("/categories"), api("/products")]);
        productos = lista;
        categorias.forEach((cat) => {
            const boton = el("button", { type: "button", class: "categoria", "data-categoria": cat.id,
                "aria-pressed": String(filtro.categoria === cat.id) }, cat.nombre);
            boton.addEventListener("click", () => {
                filtro.categoria = filtro.categoria === cat.id ? null : cat.id;
                nav.querySelectorAll(".categoria").forEach((b) => {
                    b.setAttribute("aria-pressed", String(b.dataset.categoria === filtro.categoria));
                });
                pintar();
            });
            nav.appendChild(boton);
        });
    } catch (err) {
        estado.hidden = false;
        estado.textContent = "No pudimos cargar el menú. " + mensajeError(err);
        return;
    }

    function pintar() {
        const texto = filtro.texto.trim().toLowerCase();
        const lista = productos.filter((p) => {
            const coincideCategoria = !filtro.categoria || p.categoria === filtro.categoria;
            const coincideTexto = !texto || p.nombre.toLowerCase().includes(texto) || p.descripcion.toLowerCase().includes(texto);
            return coincideCategoria && coincideTexto;
        });

        grilla.replaceChildren(...lista.map(crearTarjeta));

        if (lista.length === 0) {
            estado.hidden = false;
            estado.textContent = "No encontramos productos con esa búsqueda.";
        } else if (filtro.categoria || texto) {
            estado.hidden = false;
            estado.textContent = `${lista.length} producto(s) encontrado(s).`;
        } else {
            estado.hidden = true;
        }
    }

    iniciarBusqueda((valor) => {
        filtro.texto = valor;
        pintar();
    });
    pintar();
}

const TEXTOS_LOGIN = {
    es: {
        subtitulo: "Inicie sesión para acceder a sus <strong>Beneficios reales</strong>",
        usuario: "Email*",
        clave: "Contraseña*",
        olvido: "He olvidado mi contraseña",
        boton: "Iniciar sesión",
        registro: "¿No tienes cuenta? Regístrate",
        errUsuario: "Ingresa tu email.",
        errEmail: "El email no es válido.",
        errClave: "Ingresa tu contraseña.",
        bienvenida: "¡Bienvenido! Redirigiendo..."
    },
    en: {
        subtitulo: "Sign in to access your <strong>Royal benefits</strong>",
        usuario: "Email*",
        clave: "Password*",
        olvido: "I forgot my password",
        boton: "Sign in",
        registro: "No account? Sign up",
        errUsuario: "Enter your email.",
        errEmail: "The email is not valid.",
        errClave: "Enter your password.",
        bienvenida: "Welcome! Redirecting..."
    }
};


function iniciarLogin() {
    const form = document.querySelector(".login-form");
    const usuario = form.querySelector("#usuario");
    const clave = form.querySelector("#clave");
    const mensaje = form.querySelector(".login-mensaje");
    const selectIdioma = document.querySelector('select[name="idioma"]');
    const botonEnviar = form.querySelector(".login-boton");
    let idioma = "es";

    function t(c) {
        return TEXTOS_LOGIN[idioma][c];
    }

    function aplicarIdioma() {
        document.documentElement.lang = idioma;
        document.querySelector('[data-texto="subtitulo"]').innerHTML = t("subtitulo"); 
        document.querySelector('[data-texto="olvido"]').innerText = t("olvido");
        document.querySelector('[data-texto="boton"]').innerText = t("boton");
        document.querySelector('[data-texto="registro"]').innerText = t("registro");
        usuario.placeholder = t("usuario");
        clave.placeholder = t("clave");
    }

    function marcarError(input, texto) {
        form.querySelector(`[data-error="${input.name}"]`).innerText = texto;
        input.setAttribute("aria-invalid", texto ? "true" : "false");
    }

    function validar() {
        let valido = true;
        const valorUsuario = usuario.value.trim();
        if (!valorUsuario) {
            marcarError(usuario, t("errUsuario"));
            valido = false;
        } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(valorUsuario)) {
            marcarError(usuario, t("errEmail"));
            valido = false;
        } else {
            marcarError(usuario, "");
        }
        if (!clave.value) {
            marcarError(clave, t("errClave"));
            valido = false;
        } else {
            marcarError(clave, "");
        }
        return valido;
    }

    selectIdioma.addEventListener("change", () => {
        idioma = selectIdioma.value;
        aplicarIdioma();
    });

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        mensaje.hidden = true;
        if (!validar()) return;
        botonEnviar.disabled = true;
        try {
            const resp = await api("/auth/login", { metodo: "POST", cuerpo: { email: usuario.value.trim(), password: clave.value } });
            clave.value = "";
            mensaje.innerText = t("bienvenida");
            mensaje.hidden = false;
            const volver = new URLSearchParams(location.search).get("volver");
            const esPersonal = resp.roles.includes("staff") || resp.roles.includes("admin");
            const destino = volver && /^[a-z\-]+\.html(\?[\w=\-&%]*)?$/.test(volver) ? volver : (esPersonal ? "admin.html" : "index.html");
            setTimeout(() => { window.location.href = destino; }, 600);
        } catch (err) {
            mensaje.innerText = err.status === 401 ? "Email o contraseña incorrectos." : mensajeError(err);
            mensaje.hidden = false;
        } finally {
            botonEnviar.disabled = false;
        }
    });
}


async function iniciarDetalle() {
    const params = new URLSearchParams(window.location.search);
    const id = Number(params.get("id")) || 1;
    let producto;
    try {
        producto = await api(`/products/${id}`);
    } catch (err) {
        document.querySelector(".detalle").replaceChildren(
            el("p", {}, err.status === 404 ? "Producto no encontrado. " : mensajeError(err) + " ",
                el("a", { href: "index.html" }, "Volver al menú")));
        return;
    }

    const config = producto.personalizacion;
    const cantidades = config.extras.map(() => 0);
    let opcionElegida = 0;

    document.title = `${producto.nombre} | Mr. Sandwich`;
    const imagen = document.querySelector(".detalle-imagen");
    imagen.src = producto.imagen;
    imagen.alt = producto.nombre;
    if (producto.categoria !== "sandwich") imagen.classList.add("contain");
    document.querySelector(".detalle-nombre").innerText = producto.nombre;
    document.querySelector(".detalle-precio").innerText = formatoPrecio(producto.precio);
    document.querySelector(".detalle-descripcion").innerText = producto.descripcion;

    const opciones = document.querySelector(".pedido-opciones");
    config.opciones.forEach((opcion, i) => {
        const input = el("input", { type: "radio", name: "opcion", id: `opcion-${i}`, value: opcion.id, checked: i === 0 });
        input.addEventListener("change", () => {
            opcionElegida = i;
            actualizarTotal();
        });
        opciones.appendChild(el("div", { class: "opcion" }, input,
            el("label", { for: `opcion-${i}` }, el("span", {}, opcion.nombre),
                el("small", {}, opcion.precio ? "+" + formatoPrecio(opcion.precio) : "Incluido"))));
    });

    const listaExtras = document.querySelector(".pedido-extras");
    config.extras.forEach((extra, i) => {
        const output = el("output", { "aria-live": "polite" }, "0");
        const menos = el("button", { type: "button", "aria-label": `Quitar ${extra.nombre}`, disabled: true }, "−");
        const mas = el("button", { type: "button", "aria-label": `Agregar ${extra.nombre}` }, "+");
        const maximo = extra.max || 5;
        [[menos, -1], [mas, 1]].forEach(([boton, cambio]) => {
            boton.addEventListener("click", () => {
                cantidades[i] = Math.min(maximo, Math.max(0, cantidades[i] + cambio));
                output.value = cantidades[i];
                menos.disabled = cantidades[i] === 0;
                mas.disabled = cantidades[i] === maximo;
                actualizarTotal();
            });
        });
        listaExtras.appendChild(el("li", { class: "extra" },
            el("span", { class: "extra-icono", "aria-hidden": "true" }, extra.nombre.charAt(0)),
            el("span", { class: "extra-nombre" }, extra.nombre, " ",
                el("small", {}, extra.precio ? "+" + formatoPrecio(extra.precio) : "Sin costo")),
            el("span", { class: "contador" }, menos, output, mas)));
    });

    function calcularTotal() {
        const extras = config.extras.reduce((suma, extra, i) => suma + extra.precio * cantidades[i], 0);
        return producto.precio + (config.opciones[opcionElegida]?.precio || 0) + extras;
    }

    function actualizarTotal() {
        document.querySelector("[data-total]").innerText = formatoPrecio(calcularTotal());
    }

    const boton = document.querySelector(".pedido-boton");
    if (!producto.disponible) {
        boton.disabled = true;
        boton.textContent = "Producto agotado";
    }

    document.querySelector(".pedido").addEventListener("submit", (e) => {
        e.preventDefault();
        if (!producto.disponible) return;
        const carrito = leerCarrito();
        carrito.push({
            product_id: producto.id,
            option_id: config.opciones[opcionElegida]?.id || null,
            extras: config.extras.map((extra, i) => ({ extra_id: extra.id, qty: cantidades[i] })).filter((x) => x.qty > 0),
            qty: 1,
            nombre: producto.nombre,
            imagen: producto.imagen
        });
        guardarCarrito(carrito);
        mostrarAviso(`${producto.nombre} agregado a tu pedido`);
    });

    iniciarBusqueda(null);
    actualizarTotal();
}

document.addEventListener("DOMContentLoaded", () => {
    const pagina = document.body.dataset.pagina;
    if (pagina === "inicio") {
        iniciarCabecera();
        iniciarInicio();
    } else if (pagina === "producto") {
        iniciarCabecera();
        iniciarDetalle();
    } else if (pagina === "login") {
        iniciarLogin();
    }
});
