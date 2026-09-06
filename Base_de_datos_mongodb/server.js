const express = require('express')
const mongoose = require('mongoose')
const cors = require('cors')

const {ApolloServer, gql} = require('apollo-server-express')
const Usuario = require ('./models/usuario')
const Categoria = require('./models/Categoria');
const Producto = require('./models/Productos');
const Ingrediente = require('./models/ingrediente');
const Proveedor = require('./models/proveedor');


mongoose.connect('mongodb://127.0.0.1:27017/MrSandwich')
const typeDefs = gql`
    type Usuario {
        id: ID!
        nombre: String!
        pass: String!
    }
    input UsuarioInput{
    nombre: String!
    pass: String!
    }
    type Alert{
    message: String
    }
    type Query{
    getUsuarios:[Usuario]
    getUsuariosById(id: ID!): Usuario

    getCategorias: [Categoria]
    getCategoriaById(id: ID!): Categoria

    getProductos: [Producto]
    getProductoById(id: ID!): Producto
    getIngredientes: [Ingrediente]
    getIngredienteById(id: ID!): Ingrediente

    getProveedores: [Proveedor]
    getProveedorById(id: ID!): Proveedor
    
    }
    type Mutation{
    addUsuario(input: UsuarioInput): Usuario
    updUsuario(id: ID!, input: UsuarioInput): Usuario
    delUsuario(id:ID!): Alert
    
    addCategoria(input: CategoriaInput): Categoria
    updCategoria(id: ID!, input: CategoriaInput): Categoria
    delCategoria(id: ID!): Alert

    addProducto(input: ProductoInput): Producto
    updProducto(id: ID!, input: ProductoInput): Producto
    delProducto(id: ID!): Alert
    
    addIngrediente(input: IngredienteInput): Ingrediente
    updIngrediente(id: ID!, input: IngredienteInput): Ingrediente
    delIngrediente(id: ID!): Alert

    addProveedor(input: ProveedorInput): Proveedor
    updProveedor(id: ID!, input: ProveedorInput): Proveedor
    delProveedor(id: ID!): Alert
    }
    type Categoria {
    id: ID!
    nombre: String!
    descripcion: String
    activo: Boolean
}

input CategoriaInput {
    nombre: String!
    descripcion: String
    activo: Boolean
}

type Producto {
    id: ID!
    nombre: String!
    descripcion: String
    precio: Float!
    categoria: Categoria!
    disponible: Boolean
    imagen: String
}

input ProductoInput {
    nombre: String!
    descripcion: String
    precio: Float!
    categoria: ID!
    disponible: Boolean
    imagen: String
}
    type Ingrediente {
    id: ID!
    nombre: String!
    stock: Float
    unidadMedida: String
    stockMinimo: Float
}

input IngredienteInput {
    nombre: String!
    stock: Float
    unidadMedida: String
    stockMinimo: Float
}

type Proveedor {
    id: ID!
    nombre: String!
    telefono: String
    correo: String
    direccion: String
    activo: Boolean
}

input ProveedorInput {
    nombre: String!
    telefono: String
    correo: String
    direccion: String
    activo: Boolean
}
`;

const resolvers ={
               Query: {
                              async getUsuarios(obj){
                                             const usuarios =await Usuario.find();
                                             return usuarios;
                              },
                              async getUsuariosById(obj,{id}){
                                             const usuariobus = await Usuario.findById(id);
                                             if(usuariobus == null){
                                                            return null;
                                             } else {
                                                            return usuariobus
                                             }
                              },
                              async getCategorias() {
                                             const categorias = await Categoria.find();
                                             return categorias;
                              },

                              async getCategoriaById(obj, { id }) {
                                             const categoriaBuscada = await Categoria.findById(id);
                                             return categoriaBuscada;
                              },
                              async getProductos() {
                                             const productos = await Producto.find().populate('categoria');
                                             return productos;
                              },

                              async getProductoById(obj, { id }) {
                                             const productoBuscado = await Producto
                                             .findById(id)
                                             .populate('categoria');

                              return productoBuscado;
                              },
                              async getIngredientes() {
                                             const ingredientes = await Ingrediente.find();
                                             return ingredientes;
                              },

                              async getIngredienteById(obj, { id }) {
                                             const ingredienteBuscado = await Ingrediente.findById(id);
                                             return ingredienteBuscado;
                              },

                              async getProveedores() {
                                             const proveedores = await Proveedor.find();
                                             return proveedores;
                              },

                              async getProveedorById(obj, { id }) {
                                             const proveedorBuscado = await Proveedor.findById(id);
                                             return proveedorBuscado;
                              }

               },
               Mutation: {
                              async addUsuario(obj, { input }) {
                              const nuevoUsuario = new Usuario(input);
                              await nuevoUsuario.save();
                              return nuevoUsuario;
                              },
                              async updUsuario(obj, {id, input}){
                                             const usuarioActualizado = await Usuario.findByIdAndUpdate(id, input, {new: true});
                                             return usuarioActualizado;
                              },
                              async delUsuario(obj,{id}){
                                             await Usuario.deleteOne({_id: id})
                                             return{
                                                            message: "Usuario Eliminado"
                                             };

                              },
                              async addCategoria(obj, { input }) {
                                             const nuevaCategoria = new Categoria(input);
                                             await nuevaCategoria.save();
                                             return nuevaCategoria;
                                             },

                              async updCategoria(obj, { id, input }) {
                                             const categoriaActualizada = await Categoria.findByIdAndUpdate(
                                             id,
                                             input,
                                             { new: true }
                              );

                              return categoriaActualizada;
                              },

                              async delCategoria(obj, { id }) {
                                             await Categoria.deleteOne({ _id: id });

                                             return {
                                             message: "Categoría eliminada"
                                             };
                              },
                              async addProducto(obj, { input }) {
                                             const nuevoProducto = new Producto(input);
                                             await nuevoProducto.save();

                                             return await Producto
                                             .findById(nuevoProducto._id)
                                             .populate('categoria');
                              },

                              async updProducto(obj, { id, input }) {
                                             const productoActualizado = await Producto
                                             .findByIdAndUpdate(
                                             id,
                                             input,
                                             { new: true }
                                             )
                                             .populate('categoria');

                              return productoActualizado;
                              },

                              async delProducto(obj, { id }) {
                                             await Producto.deleteOne({ _id: id });

                                             return {
                                             message: "Producto eliminado"
                                             };
                              },
                              async addIngrediente(obj, { input }) {
                                             const nuevoIngrediente = new Ingrediente(input);
                                             await nuevoIngrediente.save();
                              return nuevoIngrediente;
                              },

                              async updIngrediente(obj, { id, input }) {
                                             const ingredienteActualizado = await Ingrediente.findByIdAndUpdate(
                                             id,
                                             input,
                              { new: true }
                              );

                              return ingredienteActualizado;
                              },

                              async delIngrediente(obj, { id }) {
                                             await Ingrediente.deleteOne({ _id: id });

                                             return {
                                             message: "Ingrediente eliminado"
                              };
                              },
                              async addProveedor(obj, { input }) {
                                             const nuevoProveedor = new Proveedor(input);
                                             await nuevoProveedor.save();
                                             return nuevoProveedor;
                              },

                              async updProveedor(obj, { id, input }) {
                              const proveedorActualizado = await Proveedor.findByIdAndUpdate(
                              id,
                              input,
                              { new: true }
                              );

                              return proveedorActualizado;
                              },

                              async delProveedor(obj, { id }) {
                                             await Proveedor.deleteOne({ _id: id });

                                             return {
                                             message: "Proveedor eliminado"
                              };
                              }
               }
};
let apolloServe = null;
const corsOption ={
               origin: "http://localhost:8090",
               Credential: false
};
async function startServer(){
               apolloServe =new ApolloServer({typeDefs, resolvers, corsOption});
               await apolloServe.start();
               apolloServe.applyMiddleware({app, cors:false});

}

startServer();

const app =express();
app.use(cors());
app.listen(8090,function(){
               console.log("servidor iniciado");

})