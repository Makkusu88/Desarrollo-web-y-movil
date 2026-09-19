const CATEGORIAS = [
    { id: "promociones", nombre: "Promociones" },
    { id: "sandwich", nombre: "Sandwich" },
    { id: "hamburguesas", nombre: "Hamburguesas" },
    { id: "bebidas", nombre: "Bebidas" }
];

const PRODUCTOS = [
    {
        id: 1,
        nombre: "Churrasco italiano",
        categoria: "sandwich",
        precio: 6990,
        descripcion: "Churrasco de vacuno en pan frica con tomate, palta y mayonesa casera.",
        imagen: "img/sandwich.jpg"
    },
    {
        id: 2,
        nombre: "Barros Luco",
        categoria: "sandwich",
        precio: 5490,
        descripcion: "Churrasco de vacuno con queso fundido en pan frica recién horneado.",
        imagen: "img/sandwich.jpg"
    },
    {
        id: 3,
        nombre: "Chacarero",
        categoria: "sandwich",
        precio: 6490,
        descripcion: "Churrasco de vacuno con porotos verdes, tomate y ají verde.",
        imagen: "img/sandwich.jpg"
    },
    {
        id: 4,
        nombre: "Completo italiano",
        categoria: "sandwich",
        precio: 3490,
        descripcion: "Vienesa, tomate, palta y mayonesa en pan de completo.",
        imagen: "img/sandwich.jpg"
    },
    {
        id: 5,
        nombre: "Sliders de lechón",
        categoria: "hamburguesas",
        precio: 5990,
        descripcion: "Tres mini hamburguesas de lechón crujiente, mostaza antigua y pepinillos.",
        imagen: "img/sliders.webp"
    },
    {
        id: 6,
        nombre: "Hamburguesa clásica",
        categoria: "hamburguesas",
        precio: 5490,
        descripcion: "Hamburguesa de vacuno, queso cheddar, lechuga, tomate y salsa de la casa.",
        imagen: "img/sliders.webp"
    },
    {
        id: 7,
        nombre: "Combo italiano",
        categoria: "promociones",
        precio: 8990,
        descripcion: "Churrasco italiano, papas fritas medianas y bebida a elección.",
        imagen: "img/hamburguesa-papas.webp"
    },
    {
        id: 8,
        nombre: "Promo dúo Barros Luco",
        categoria: "promociones",
        precio: 9990,
        descripcion: "Dos Barros Luco y una porción de papas fritas para compartir.",
        imagen: "img/hamburguesa-papas.webp"
    },
    {
        id: 9,
        nombre: "Coca-Cola 350 ml",
        categoria: "bebidas",
        precio: 1990,
        descripcion: "Bebida Coca-Cola en lata, bien helada.",
        imagen: "img/bebida.svg"
    },
    {
        id: 10,
        nombre: "Sprite 350 ml",
        categoria: "bebidas",
        precio: 1990,
        descripcion: "Bebida Sprite en lata, bien helada.",
        imagen: "img/bebida.svg"
    },
    {
        id: 11,
        nombre: "Jugo natural",
        categoria: "bebidas",
        precio: 2490,
        descripcion: "Jugo de fruta natural de la temporada.",
        imagen: "img/bebida.svg"
    }
];

const PERSONALIZACION = {
    sandwich: {
        opciones: [
            { nombre: "Tamaño normal", precio: 0 },
            { nombre: "Tamaño grande", precio: 1500 },
            { nombre: "En combo con papas y bebida", precio: 2990 }
        ],
        extras: [
            { nombre: "Palta extra", precio: 800 },
            { nombre: "Queso extra", precio: 700 }
        ]
    },
    hamburguesas: {
        opciones: [
            { nombre: "Tamaño normal", precio: 0 },
            { nombre: "Carne doble", precio: 1990 },
            { nombre: "En combo con papas y bebida", precio: 2990 }
        ],
        extras: [
            { nombre: "Tocino extra", precio: 900 },
            { nombre: "Queso extra", precio: 700 }
        ]
    },
    promociones: {
        opciones: [
            { nombre: "Con Coca-Cola", precio: 0 },
            { nombre: "Con Sprite", precio: 0 },
            { nombre: "Con jugo natural", precio: 500 }
        ],
        extras: [
            { nombre: "Papas extra", precio: 1500 },
            { nombre: "Salsa extra", precio: 400 }
        ]
    },
    bebidas: {
        opciones: [
            { nombre: "350 ml", precio: 0 },
            { nombre: "500 ml", precio: 500 },
            { nombre: "1,5 litros", precio: 1500 }
        ],
        extras: [
            { nombre: "Hielo", precio: 0 },
            { nombre: "Rodaja de limón", precio: 200 }
        ]
    }
};
