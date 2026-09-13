const mongoose = require('mongoose');

const productoSchema = new mongoose.Schema({
    nombre: {
        type: String,
        required: true
    },

    descripcion: {
        type: String
    },

    precio: {
        type: Number,
        required: true
    },

    categoria: {
        type: mongoose.Schema.Types.ObjectId,
        ref: 'categoria',
        required: true
    },

    disponible: {
        type: Boolean,
        default: true
    },

    imagen: {
        type: String
    }
});

module.exports = mongoose.model('producto', productoSchema);