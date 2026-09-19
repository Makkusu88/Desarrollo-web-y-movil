const CLAVE_SESION = "mrsandwich_sesion";
const CLAVE_PEDIDO = "mrsandwich_pedido";

function formatoPrecio(valor) {
    return "$" + valor;
}

function leerStorage(clave, porDefecto) {
    try {
        const valor = localStorage.getItem(clave);
        return valor ? JSON.parse(valor) : porDefecto;
    } catch (err) {
        return porDefecto;
    }
}

function guardarStorage(clave, valor) {
    try {
        localStorage.setItem(clave, JSON.stringify(valor));
    } catch (err) {
        console.log(`No se pudo guardar ${clave}: ${err}`);
    }
}

function mostrarAviso(texto) {
    const aviso = document.querySelector(".aviso");
    if (!aviso) return;
    aviso.textContent = texto;
    aviso.hidden = false;
    clearTimeout(mostrarAviso.timer);
    mostrarAviso.timer = setTimeout(() => { aviso.hidden = true; }, 3000);
}

function iniciarSesionCabecera() {
    const boton = document.querySelector("[data-sesion]");
    if (!boton) return;

    const sesion = leerStorage(CLAVE_SESION, null);
    if (!sesion) return;

    boton.querySelector("span").textContent = `Hola, ${sesion.nombre} · Salir`;
    boton.setAttribute("href", "#");
    boton.addEventListener("click", (e) => {
        e.preventDefault();
        localStorage.removeItem(CLAVE_SESION);
        mostrarAviso("Sesión cerrada");
        boton.querySelector("span").textContent = "Inicio de sesión";
        boton.setAttribute("href", "login.html");
    }, { once: true });
}

function iniciarBusqueda(alBuscar) {
    const botonBuscar = document.querySelector('[data-accion="buscar"]');
    const barra = document.querySelector(".barra-busqueda");
    if (!botonBuscar || !barra) return;

    const input = barra.querySelector("input");

    botonBuscar.addEventListener("click", () => {
        barra.hidden = !barra.hidden;
        if (!barra.hidden) input.focus();
    });

    barra.querySelector(".barra-cerrar").addEventListener("click", () => {
        barra.hidden = true;
        input.value = "";
        if (alBuscar) alBuscar("");
    });

    if (alBuscar) {
        barra.addEventListener("submit", (e) => e.preventDefault());
        input.addEventListener("input", () => alBuscar(input.value));
    }
}

function crearTarjeta(producto) {
    const tarjeta = document.createElement("a");
    tarjeta.className = "tarjeta";
    tarjeta.href = `producto.html?id=${producto.id}`;

    const texto = document.createElement("div");
    texto.className = "tarjeta-texto";

    const nombre = document.createElement("h2");
    nombre.className = "tarjeta-nombre";
    nombre.innerText = producto.nombre;

    const descripcion = document.createElement("p");
    descripcion.className = "tarjeta-descripcion";
    descripcion.innerText = producto.descripcion;

    const precio = document.createElement("span");
    precio.className = "tarjeta-precio";
    precio.innerText = formatoPrecio(producto.precio);

    texto.append(nombre, descripcion, precio);

    const imagen = document.createElement("img");
    imagen.className = "tarjeta-imagen";
    imagen.src = producto.imagen;
    imagen.alt = producto.nombre;
    imagen.loading = "lazy";

    tarjeta.append(texto, imagen);
    return tarjeta;
}

function iniciarInicio() {
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
    if (params.get("categoria")) {
        filtro.categoria = params.get("categoria");
    }

    CATEGORIAS.forEach((cat) => {
        const boton = document.createElement("button");
        boton.type = "button";
        boton.className = "categoria";
        boton.innerText = cat.nombre;
        boton.dataset.categoria = cat.id;
        boton.setAttribute("aria-pressed", String(filtro.categoria === cat.id));
        boton.addEventListener("click", () => {
            filtro.categoria = filtro.categoria === cat.id ? null : cat.id;
            nav.querySelectorAll(".categoria").forEach((b) => {
                b.setAttribute("aria-pressed", String(b.dataset.categoria === filtro.categoria));
            });
            pintar();
        });
        nav.appendChild(boton);
    });

    function pintar() {
        const texto = filtro.texto.trim().toLowerCase();
        const lista = PRODUCTOS.filter((p) => {
            const coincideCategoria = !filtro.categoria || p.categoria === filtro.categoria;
            const coincideTexto = !texto || p.nombre.toLowerCase().includes(texto) || p.descripcion.toLowerCase().includes(texto);
            return coincideCategoria && coincideTexto;
        });

        grilla.innerHTML = "";
        lista.forEach((p) => grilla.appendChild(crearTarjeta(p)));

        if (lista.length === 0) {
            estado.hidden = false;
            estado.innerText = "No encontramos productos con esa búsqueda.";
        } else if (filtro.categoria || texto) {
            estado.hidden = false;
            estado.innerText = `${lista.length} producto(s) encontrado(s).`;
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
        usuario: "Nombre de pila o Email*",
        clave: "Contraseña*",
        olvido: "He olvidado mi contraseña",
        boton: "Iniciar sesión",
        errUsuario: "Ingresa tu nombre o email.",
        errEmail: "El email no es válido.",
        errClave: "La contraseña debe tener al menos 4 caracteres.",
        olvidoMensaje: "Te enviaremos un enlace para recuperar tu contraseña al email registrado.",
        bienvenida: (nombre) => `¡Bienvenido, ${nombre}! Redirigiendo...`
    },
    en: {
        subtitulo: "Sign in to access your <strong>Royal benefits</strong>",
        usuario: "First name or Email*",
        clave: "Password*",
        olvido: "I forgot my password",
        boton: "Sign in",
        errUsuario: "Enter your name or email.",
        errEmail: "The email is not valid.",
        errClave: "The password must have at least 4 characters.",
        olvidoMensaje: "We will send a recovery link to your registered email.",
        bienvenida: (nombre) => `Welcome, ${nombre}! Redirecting...`
    }
};

function iniciarLogin() {
    const form = document.querySelector(".login-form");
    const usuario = form.querySelector("#usuario");
    const clave = form.querySelector("#clave");
    const mensaje = form.querySelector(".login-mensaje");
    const selectIdioma = document.querySelector('select[name="idioma"]');
    let idioma = "es";

    function t(clave) {
        return TEXTOS_LOGIN[idioma][clave];
    }

    function aplicarIdioma() {
        document.documentElement.lang = idioma;
        document.querySelector('[data-texto="subtitulo"]').innerHTML = t("subtitulo");
        document.querySelector('[data-texto="olvido"]').innerText = t("olvido");
        document.querySelector('[data-texto="boton"]').innerText = t("boton");
        usuario.placeholder = t("usuario");
        clave.placeholder = t("clave");
    }

    function marcarError(input, texto) {
        const error = form.querySelector(`[data-error="${input.name}"]`);
        error.innerText = texto;
        input.setAttribute("aria-invalid", texto ? "true" : "false");
    }

    function validar() {
        let valido = true;
        const valorUsuario = usuario.value.trim();

        if (!valorUsuario) {
            marcarError(usuario, t("errUsuario"));
            valido = false;
        } else if (valorUsuario.includes("@") && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(valorUsuario)) {
            marcarError(usuario, t("errEmail"));
            valido = false;
        } else {
            marcarError(usuario, "");
        }

        if (clave.value.length < 4) {
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
        if (usuario.getAttribute("aria-invalid") === "true" || clave.getAttribute("aria-invalid") === "true") {
            validar();
        }
    });

    form.querySelector(".login-olvido").addEventListener("click", () => {
        mensaje.innerText = t("olvidoMensaje");
        mensaje.hidden = false;
    });

    form.addEventListener("submit", (e) => {
        e.preventDefault();
        mensaje.hidden = true;
        if (!validar()) return;

        const nombre = usuario.value.trim().split("@")[0];
        guardarStorage(CLAVE_SESION, { nombre });
        mensaje.innerText = t("bienvenida")(nombre);
        mensaje.hidden = false;
        setTimeout(() => { window.location.href = "index.html"; }, 1200);
    });
}

function iniciarDetalle() {
    const params = new URLSearchParams(window.location.search);
    const id = Number(params.get("id")) || PRODUCTOS[0].id;
    const producto = PRODUCTOS.find((p) => p.id === id);

    if (!producto) {
        document.querySelector(".detalle").innerHTML =
            '<p>Producto no encontrado. <a href="index.html">Volver al menú</a></p>';
        return;
    }

    const config = PERSONALIZACION[producto.categoria];
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
        const div = document.createElement("div");
        div.className = "opcion";
        div.innerHTML = `
            <input type="radio" name="opcion" id="opcion-${i}" value="${i}" ${i === 0 ? "checked" : ""}>
            <label for="opcion-${i}">
                <span>${opcion.nombre}</span>
                <small>${opcion.precio ? "+" + formatoPrecio(opcion.precio) : "Incluido"}</small>
            </label>`;
        div.querySelector("input").addEventListener("change", () => {
            opcionElegida = i;
            actualizarTotal();
        });
        opciones.appendChild(div);
    });

    const listaExtras = document.querySelector(".pedido-extras");
    config.extras.forEach((extra, i) => {
        const li = document.createElement("li");
        li.className = "extra";
        li.innerHTML = `
            <span class="extra-icono" aria-hidden="true">${extra.nombre.charAt(0)}</span>
            <span class="extra-nombre">${extra.nombre}
                <small>${extra.precio ? "+" + formatoPrecio(extra.precio) : "Sin costo"}</small>
            </span>
            <span class="contador">
                <button type="button" data-cambio="-1" aria-label="Quitar ${extra.nombre}" disabled>&minus;</button>
                <output aria-live="polite">0</output>
                <button type="button" data-cambio="1" aria-label="Agregar ${extra.nombre}">+</button>
            </span>`;

        const output = li.querySelector("output");
        const menos = li.querySelector('[data-cambio="-1"]');
        const mas = li.querySelector('[data-cambio="1"]');

        li.querySelectorAll("[data-cambio]").forEach((boton) => {
            boton.addEventListener("click", () => {
                cantidades[i] = Math.min(5, Math.max(0, cantidades[i] + Number(boton.dataset.cambio)));
                output.value = cantidades[i];
                menos.disabled = cantidades[i] === 0;
                mas.disabled = cantidades[i] === 5;
                actualizarTotal();
            });
        });
        listaExtras.appendChild(li);
    });

    function calcularTotal() {
        const extras = config.extras.reduce((suma, extra, i) => suma + extra.precio * cantidades[i], 0);
        return producto.precio + config.opciones[opcionElegida].precio + extras;
    }

    function actualizarTotal() {
        document.querySelector("[data-total]").innerText = formatoPrecio(calcularTotal());
    }

    document.querySelector(".pedido").addEventListener("submit", (e) => {
        e.preventDefault();
        const pedido = leerStorage(CLAVE_PEDIDO, []);
        pedido.push({
            id: producto.id,
            nombre: producto.nombre,
            opcion: config.opciones[opcionElegida].nombre,
            extras: config.extras
                .map((extra, i) => ({ nombre: extra.nombre, cantidad: cantidades[i] }))
                .filter((extra) => extra.cantidad > 0),
            total: calcularTotal()
        });
        guardarStorage(CLAVE_PEDIDO, pedido);
        mostrarAviso(`${producto.nombre} agregado a tu pedido (${pedido.length} en total)`);
    });

    iniciarBusqueda(null);
    actualizarTotal();
}

document.addEventListener("DOMContentLoaded", () => {
    const pagina = document.body.dataset.pagina;

    if (pagina === "inicio") {
        iniciarSesionCabecera();
        iniciarInicio();
    } else if (pagina === "producto") {
        iniciarSesionCabecera();
        iniciarDetalle();
    } else if (pagina === "login") {
        iniciarLogin();
    }
});
