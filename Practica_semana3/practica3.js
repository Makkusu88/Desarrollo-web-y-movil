const respuestaAPI = {
    "status": 200,
    "message" : "Productos obtenidos correctamente",
    "data": [
        {
            "id": 1,
            "nombre": "Teclado",
            "precio": 4590
        },
        {
            "id": 2,
            "nombre": "Mouse",
            "precio": 6000
        }
    ]
};

function agregarProducto(){
    let cmb = document.getElementById("cmbProducto");
    let id = document.getElementById("txtId").value;
    let nombre = document.getElementById("txtNombre").value;
    let opt = document.createElement("option");
    opt.setAttribute("value", id);
    opt.innerText = nombre;
    cmb.appendChild(opt);
}

function cargarProductos(){
    let cmb = document.getElementById("cmbApi");
    respuestaAPI.data.forEach((producto) => {
        let opt = document.createElement("option");
        opt.setAttribute("value", producto.id);
        opt.innerText = producto.nombre;
        cmb.appendChild(opt);
    });
}

respuestaAPI.data.forEach((producto) => {
    console.log(`${producto.nombre} - $${producto.precio}`);
})

let texto = document.createElement("input");
texto.setAttribute("type","text");
texto.setAttribute("value", "hola");
document.body.appendChild(texto);

let cmbComuna = document.createElement("select");
cmbComuna.setAttribute("name","cmbComuna");
respuestaAPI.data.forEach((com) => {
  let optionAux = document.createElement("option");
  optionAux.setAttribute("value", com.id);
  optionAux.innerText = com.nombre;
  cmbComuna.appendChild(optionAux);
});
document.body.appendChild(cmbComuna);

let variable1 = null;
console.log(typeof(variable1));
variable1 = { "rut": "1-9"};
console.log(typeof(variable1.rut));
let variable2 = NaN;
console.log(typeof(variable2));
variable2 = 1/0;
console.log(typeof(variable2)); console.log(variable2);
variable2 = 1/variable1;
console.log(typeof(variable2)); console.log(variable2);
let variable3;
console.log(typeof(variable3));
console.log(variable3 instanceof Object)
console.log(null instanceof Object);
try {
    variable2 = variable2 + y;
} catch (err) {
    console.log(`Error ${err}`);
}

const objeto = { propiedad1 : 1, propiedad2 : 2};
delete objeto.propiedad1;
console.log(objeto);
const ordenado = { propiedad1: 3, ...objeto};
console.log(ordenado);
const objeto2 = { "tipo":"IOT"};
const composicion = Object.assign({}, ordenado, objeto2);
console.log(composicion);
const composicion2 = {ordenado, objeto2};
console.log(composicion2);
console.log(composicion2.objeto2);
for(let prop in composicion2){
    console.log(prop);
}
Object.entries(composicion2).forEach(([key, value]) => {
    console.log(`key: ${key}, value: ${value.propiedad1}`);
});
Object.values(composicion2).forEach(value => {
    console.log(`value: ${value}`);
});
Object.entries(composicion2).forEach(([key, value]) => {
    Object.entries(value).forEach(([key, value]) => {
        console.log(`key: ${key}, value: ${value}`);
    });
});
