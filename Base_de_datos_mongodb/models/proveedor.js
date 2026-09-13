const mongoose = require('mongoose');

const proveedorSchema = new mongoose.Schema({
    nombre: {
        type: String,
        required: true
    },

    telefono: {
        type: String
    },

    correo: {
        type: String
    },

    direccion: {
        type: String
    },

    activo: {
        type: Boolean,
        default: true
    }
});

module.exports = mongoose.model('proveedor', proveedorSchema);