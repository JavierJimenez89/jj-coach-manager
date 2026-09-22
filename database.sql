-- Base de datos JJ Coach Manager
-- Script para crear la estructura completa de la base de datos

-- Crear base de datos si no existe
CREATE DATABASE IF NOT EXISTS jj_coach_manager;
USE jj_coach_manager;

-- Tabla de usuarios
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    user_type ENUM('client', 'trainer') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_user_type (user_type)
);

-- Tabla de servicios
CREATE TABLE IF NOT EXISTS services (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trainer_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    duration INT DEFAULT 60 COMMENT 'Duración en minutos',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trainer_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_trainer (trainer_id),
    INDEX idx_active (is_active)
);

-- Tabla de reservas/sesiones
CREATE TABLE IF NOT EXISTS reservations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    client_id INT NOT NULL,
    trainer_id INT NOT NULL,
    service_id INT NOT NULL,
    reservation_date DATETIME NOT NULL,
    status ENUM('pending', 'confirmed', 'cancelled') DEFAULT 'pending',
    payment_status ENUM('pending', 'paid', 'failed', 'refunded') DEFAULT 'pending',
    payment_method VARCHAR(50),
    payment_amount DECIMAL(10,2),
    payment_date DATETIME,
    stripe_payment_id VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (trainer_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE,
    INDEX idx_client (client_id),
    INDEX idx_trainer (trainer_id),
    INDEX idx_date (reservation_date),
    INDEX idx_status (status),
    INDEX idx_payment (payment_status)
);

-- Tabla de disponibilidad de entrenadores
CREATE TABLE IF NOT EXISTS trainer_availability (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trainer_id INT NOT NULL,
    day_of_week ENUM('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday') NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    is_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trainer_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY unique_availability (trainer_id, day_of_week, start_time),
    INDEX idx_trainer_day (trainer_id, day_of_week)
);

-- Tabla de progreso de clientes
CREATE TABLE IF NOT EXISTS client_progress (
    id INT AUTO_INCREMENT PRIMARY KEY,
    client_id INT NOT NULL,
    trainer_id INT NOT NULL,
    progress_date DATE NOT NULL,
    weight DECIMAL(5,2),
    height DECIMAL(5,2),
    body_fat DECIMAL(5,2),
    muscle_mass DECIMAL(5,2),
    measurements JSON COMMENT 'Mediciones corporales en formato JSON',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (trainer_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_client_progress (client_id, progress_date),
    INDEX idx_trainer_clients (trainer_id)
);

-- Tabla de mensajes internos
CREATE TABLE IF NOT EXISTS messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT NOT NULL,
    receiver_id INT NOT NULL,
    subject VARCHAR(200),
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    is_deleted_by_sender BOOLEAN DEFAULT FALSE,
    is_deleted_by_receiver BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_receiver_unread (receiver_id, is_read),
    INDEX idx_sender_deleted (sender_id, is_deleted_by_sender),
    INDEX idx_receiver_deleted (receiver_id, is_deleted_by_receiver)
);

-- Insertar usuarios de prueba (contraseña: 123456)
-- Hash de '123456' con bcrypt: $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx.LrUpm
INSERT IGNORE INTO users (name, email, password, user_type) VALUES
('Cliente Prueba', 'cliente@jjcoach.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx.LrUpm', 'client'),
('Entrenador Prueba', 'trainer@jjcoach.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx.LrUpm', 'trainer');

-- Insertar servicios de ejemplo
INSERT IGNORE INTO services (trainer_id, name, description, price, duration) VALUES
(2, 'Sesión Personal Training', 'Sesión individual de entrenamiento personalizado', 50.00, 60),
(2, 'Plan Nutricional', 'Consulta y plan de nutrición personalizado', 40.00, 45),
(2, 'Sesión Grupal', 'Entrenamiento en grupos pequeños (2-4 personas)', 25.00, 60);

-- Insertar disponibilidad de ejemplo para el entrenador
INSERT IGNORE INTO trainer_availability (trainer_id, day_of_week, start_time, end_time) VALUES
(2, 'monday', '08:00:00', '20:00:00'),
(2, 'tuesday', '08:00:00', '20:00:00'),
(2, 'wednesday', '08:00:00', '20:00:00'),
(2, 'thursday', '08:00:00', '20:00:00'),
(2, 'friday', '08:00:00', '20:00:00'),
(2, 'saturday', '10:00:00', '14:00:00');

-- Mostrar resumen
SELECT 'Base de datos creada exitosamente' as mensaje;
SELECT COUNT(*) as total_usuarios FROM users;
SELECT COUNT(*) as total_servicios FROM services;
SELECT COUNT(*) as total_disponibilidad FROM trainer_availability;
