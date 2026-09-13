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

            <a class="navbar-brand" href="index.php">
                <i class="fas fa-angry" style="font-size:48px; color:white;"></i>
            </a>

               
               <div class="d-flex ms-auto order-sm-last">
                              <button type="button" class="btn btn-primary me-2" data-bs-toggle="modal" data-bs-target="#modalAcceder">
                                             Acceder
                              </button>
                              <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#collapsibleNavbar">
                                             <span class="navbar-toggler-icon"></span>
                              </button>
               </div>

           

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
                                                            <a class = "nav-link" href="Contactos.php">contactos</a>
                                             </li>

                              </ul>
               </div>
</div>
</nav>

<!-- Modal Acceder -->
<div class="modal fade" id="modalAcceder">
               <div class="modal-dialog">
                              <div class="modal-content">

                                             <div class="modal-header">
                                                            <h4 class="modal-title">Autenticación</h4>
                                                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                                             </div>

                                             <div class="modal-body">
                                                            Modal body..
                                             </div>

                                             <div class="modal-footer">
                                                            <button type="button" class="btn btn-danger" data-bs-dismiss="modal">Close</button>
                                             </div>

                              </div>
               </div>
</div>



               <div class= "container bg-warning">
                                                <!-- Carousel -->
                    <div id="demo" class="carousel slide" data-bs-ride="carousel">

                    <!-- Indicators/dots -->
                    <div class="carousel-indicators">
                        <button type="button" data-bs-target="#demo" data-bs-slide-to="0" class="active"></button>
                        <button type="button" data-bs-target="#demo" data-bs-slide-to="1"></button>
                        <button type="button" data-bs-target="#demo" data-bs-slide-to="2"></button>
                    </div>

                    <!-- The slideshow/carousel -->
                    <div class="carousel-inner">
                        <div class="carousel-item active">
                        <img src="img/la.jpg" alt="Los Angeles" class="d-block w-100">
                        </div>
                        <div class="carousel-item">
                        <img src="img/chicago.jpg" alt="Chicago" class="d-block w-100">
                        </div>
                        <div class="carousel-item">
                        <img src="img/ny.jpg" alt="New York" class="d-block w-100">
                        </div>
                    </div>

                    <!-- Left and right controls/icons -->
                    <button class="carousel-control-prev" type="button" data-bs-target="#demo" data-bs-slide="prev">
                        <span class="carousel-control-prev-icon"></span>
                    </button>
                    <button class="carousel-control-next" type="button" data-bs-target="#demo" data-bs-slide="next">
                        <span class="carousel-control-next-icon"></span>
                    </button>
                    </div>
                    <div class="container-fluid">
                        <div class="row">
                            <div class="col-12 col-sm-6 col-md-4 col-lg-3 col-xl-2 col-xxl-2">
                                <div class="card">
                                    <img class="card-img-top" src="img/img_avatar1.png" alt="Card image">
                                    <div class="card-body">
                                        <h4 class="card-title">John Doe</h4>
                                        <p class="card-text">Some example text.</p>
                                        <a href="#" class="btn btn-primary">See Profile</a>
                                    </div>
                                </div>
                            </div>

                            <div class="col-12 col-sm-6 col-md-4 col-lg-3 col-xl-2 col-xxl-2">
                                <div class="card">
                                    <img class="card-img-top" src="img/img_avatar1.png" alt="Card image">
                                    <div class="card-body">
                                        <h4 class="card-title">Jane Doe</h4>
                                        <p class="card-text">Some example text.</p>
                                        <a href="#" class="btn btn-primary">See Profile</a>
                                    </div>
                                </div>
                            </div>

                            <div class="col-12 col-sm-6 col-md-4 col-lg-3 col-xl-2 col-xxl-2">
                                <div class="card">
                                    <img class="card-img-top" src="img/img_avatar1.png" alt="Card image">
                                    <div class="card-body">
                                        <h4 class="card-title">Carlos Perez</h4>
                                        <p class="card-text">Some example text.</p>
                                        <a href="#" class="btn btn-primary">See Profile</a>
                                    </div>
                                </div>
                            </div>

                            <div class="col-12 col-sm-6 col-md-4 col-lg-3 col-xl-2 col-xxl-2">
                                <div class="card">
                                    <img class="card-img-top" src="img/img_avatar1.png" alt="Card image">
                                    <div class="card-body">
                                        <h4 class="card-title">Ana Silva</h4>
                                        <p class="card-text">Some example text.</p>
                                        <a href="#" class="btn btn-primary">See Profile</a>
                                    </div>
                                </div>
                            </div>

                            <div class="col-12 col-sm-6 col-md-4 col-lg-3 col-xl-2 col-xxl-2">
                                <div class="card">
                                    <img class="card-img-top" src="img/img_avatar1.png" alt="Card image">
                                    <div class="card-body">
                                        <h4 class="card-title">Luis Rojas</h4>
                                        <p class="card-text">Some example text.</p>
                                        <a href="#" class="btn btn-primary">See Profile</a>
                                    </div>
                                </div>
                            </div>

                            <div class="col-12 col-sm-6 col-md-4 col-lg-3 col-xl-2 col-xxl-2">
                                <div class="card">
                                    <img class="card-img-top" src="img/img_avatar1.png" alt="Card image">
                                    <div class="card-body">
                                        <h4 class="card-title">Maria Lopez</h4>
                                        <p class="card-text">Some example text.</p>
                                        <a href="#" class="btn btn-primary">See Profile</a>
                                    </div>
                                </div>
                            </div>

                        </div>
                    </div>


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