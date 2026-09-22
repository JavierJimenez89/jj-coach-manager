# JJ Coach Manager

Aplicación web full-stack para la gestión de entrenadores personales y sus clientes, desarrollada con **Python, Flask y MySQL**.

El sistema permite gestionar clientes, servicios, sesiones, reservas y pagos desde una interfaz diferenciada para entrenadores y clientes.

Proyecto desarrollado como Trabajo Fin de Grado Superior de Desarrollo de Aplicaciones Web (DAW).

## Tecnologías utilizadas

- Python
- Flask
- MySQL
- HTML5
- CSS3
- Stripe
- bcrypt
- python-dotenv

## Funcionalidades

### Entrenadores
- Panel de control personalizado
- Gestión de clientes
- Creación y gestión de servicios
- Calendario de sesiones
- Gestión de reservas
- Control de disponibilidad
- Seguimiento del progreso de clientes
- Consulta de estadísticas e ingresos

### Clientes
- Registro e inicio de sesión
- Gestión del perfil
- Consulta de servicios
- Solicitud y gestión de sesiones
- Carrito de compra
- Pago mediante Stripe
- Consulta de reservas
- Seguimiento del progreso

## Seguridad

- Contraseñas protegidas mediante bcrypt
- Variables sensibles gestionadas mediante variables de entorno
- Separación de permisos entre clientes y entrenadores
- Protección de rutas mediante autenticación
- Configuración de cookies de sesión

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/JavierJimenez89/jj-coach-manager.git
cd jj-coach-manager
```

### 2. Crear un entorno virtual

```bash
python -m venv venv
```

En Windows:

```bash
venv\Scripts\activate
```

En Linux/macOS:

```bash
source venv/bin/activate
```

### 3. Instalar las dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar las variables de entorno

Copia `.env.example` y crea un archivo `.env` con tu configuración local.

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your-password
DB_NAME=jj_coach_manager

STRIPE_PUBLIC_KEY=your-stripe-public-key
STRIPE_SECRET_KEY=your-stripe-secret-key
```

El archivo `.env` no debe incluirse en el repositorio.

### 5. Crear la base de datos

Importa el archivo:

```text
database.sql
```

en MySQL.

También puede importarse mediante MySQL Workbench o phpMyAdmin.

### 6. Ejecutar la aplicación

```bash
python app.py
```

Después abre en el navegador:

```text
http://127.0.0.1:5000
```

## Usuarios de demostración

El archivo `database.sql` incluye usuarios ficticios para probar la aplicación.

**Cliente**

```text
Email: cliente@jjcoach.com
Contraseña: 123456
```

**Entrenador**

```text
Email: trainer@jjcoach.com
Contraseña: 123456
```

Estas credenciales son exclusivamente para demostración y desarrollo.

## Estructura del proyecto

```text
JJ-Coach-Manager/
│
├── app.py
├── db.py
├── cart.py
├── database.sql
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── templates/
│
└── static/
```

## Pagos

La aplicación incorpora integración con **Stripe** para gestionar pagos.

Las claves de Stripe se configuran mediante variables de entorno y no se almacenan directamente en el código fuente.

## Estado del proyecto

Proyecto académico funcional desarrollado como Trabajo Fin de Grado Superior de Desarrollo de Aplicaciones Web.

El proyecto tiene finalidad demostrativa y de portfolio.

## Autor

**Francisco Javier Jiménez Redondo**

Desarrollador Full-Stack

Python · Flask · MySQL · WordPress · WooCommerce