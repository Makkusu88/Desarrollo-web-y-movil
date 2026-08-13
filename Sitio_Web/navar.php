<!DOCTYPE html>
<html lang="es">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>Navbar</title>

    <!-- Bootstrap CSS -->
    <link
        href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css"
        rel="stylesheet"
    >

    <!-- Font Awesome -->
    <link
        rel="stylesheet"
        href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css"
    >
</head>

<body>

    <nav class="navbar navbar-expand-sm bg-dark navbar-dark">
        <div class="container-fluid">

            <a class="navbar-brand" href="navar.html"></a>
                <i class="fas fa-angry" style="font-size:48px; color:white;"></i>
                              <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#collapsibleNavbar">
                              <span class="navbar-toggler-icon"></span>
                              </button>
           

               <div class="collapse navbar-collapse" id="collapsibleNavbar">
                              <ul class="navbar-nav">
                                             <li class="nav-item dropdown">
                                                            <a class="nav-link dropdown-toggle" href="Empresa.php" role="button" data-bs-toggle="dropdown">Empresa</a>
                                                            <ul class="dropdown-menu">
                                                                           <li><a class="dropdown-item" href="#">quienes somos</a></li>
                                                                           <li><a class="dropdown-item" href="#">nuestro equipo</a></li>
                                                                           <li><a class="dropdown-item" href="#">Mision</a></li>
                                                            </ul>
                                             </li>
                                             <li class="nav-item">
                                                            <a class="nav-link" href="Productos.php">Productos</a>
                                             </li>
                                             <li class="nav-item">
                                                            <a class="nav-link" href="Servicios.php">servicios</a>
                                             </li>  
                                             <li class ="nav-item">
                                                            <a class ="nav-link" href="Contacto.php">contactos</a>
                                             </li>

                              </ul>
               </div>
</div>
</nav>




    <div class="container-fluid bg-primary p-3">
               <div class= "row">
                              <div class = "col-4"></div>
                              <div class=" col-4" style = "color:white"><strong>Empresanueva@andresbello</strong></div>
               </div>


    </div>

    <!-- Bootstrap JS -->
    <script
        src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js">
    </script>

</body>

</html>