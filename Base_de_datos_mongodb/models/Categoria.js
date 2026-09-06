
const mongoose = require('mongoose');

const categoriaSchema = new mongoose.Schema({
    nombre: {
        type: String,
        required: true
    },

    descripcion: {
        type: String
    },

    activo: {
        type: Boolean,
        default: true
    }
});

module.exports = mongoose.model('categoria', categoriaSchema);