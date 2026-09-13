const mongoose = require('mongoose');

const ingredienteSchema = new mongoose.Schema({
    nombre: {
        type: String,
        required: true
    },

    stock: {
        type: Number,
        default: 0
    },

    unidadMedida: {
        type: String,
        enum: [
            'UNIDAD',
            'GRAMO',
            'KILOGRAMO',
            'MILILITRO',
            'LITRO'
        ]
    },

    stockMinimo: {
        type: Number,
        default: 0
    }
});

module.exports = mongoose.model('ingrediente', ingredienteSchema);