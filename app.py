# Flask Application
from flask import Flask, render_template, request, redirect, url_for, session, flash
from db import get_db_connection
import hashlib
import secrets
import os
import bcrypt
from datetime import timedelta
import functools
import stripe
from cart import Cart

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['SESSION_COOKIE_SECURE'] = False  # Cambiar a True en producción con HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

@app.before_request
def make_session_permanent():
    session.permanent = True

def require_login(user_type=None):
    """Decorador para requerir login y opcionalmente un tipo de usuario específico"""
    def decorator(f):
        @functools.wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Por favor inicia sesión para continuar', 'warning')
                return redirect(url_for('login'))
            
            if user_type and session.get('user_type') != user_type:
                flash('No tienes permisos para acceder a esta página', 'error')
                return redirect(url_for('login'))
            
            # Verificar si la sesión ha expirado
            if 'last_activity' in session:
                from datetime import datetime, timedelta
                last_activity = datetime.fromisoformat(session['last_activity'])
                if datetime.now() - last_activity > app.config['PERMANENT_SESSION_LIFETIME']:
                    session.clear()
                    flash('Tu sesión ha expirado, por favor inicia sesión nuevamente', 'warning')
                    return redirect(url_for('login'))
            
            # Actualizar última actividad
            session['last_activity'] = datetime.now().isoformat()
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Custom filter for line breaks
@app.template_filter('nl2br')
def nl2br(text):
    return text.replace('\n', '<br>') if text else ''

@app.route('/')
def index():
    conn = get_db_connection()
    if conn:
        # Verificar tablas en la base de datos
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        cursor.close()
        conn.close()
        
        print(f"✅ Base de datos conectada - {len(tables)} tablas encontradas")
        return render_template('index.html', tables_count=len(tables))
    return "❌ Error de conexión con MySQL - revisa credenciales o que MySQL esté corriendo"

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # Verificar si el email ya existe
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return render_template('register.html', error='El email ya está registrado')
            
            # Insertar nuevo usuario
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            cursor.execute(
                "INSERT INTO users (name, email, password, user_type) VALUES (%s, %s, %s, %s)",
                (name, email, hashed_password, user_type)
            )
            conn.commit()
            cursor.close()
            conn.close()
            
            flash('Registro exitoso. Por favor inicia sesión.')
            return redirect(url_for('login'))
        
        return render_template('register.html', error='Error de conexión con la base de datos')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user_type = request.form.get('user_type', '')  # Obtener el tipo del formulario
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # Obtener usuario de la base de datos (consulta optimizada)
            if user_type:
                cursor.execute(
                    "SELECT id, name, user_type, password FROM users WHERE email = %s AND user_type = %s LIMIT 1",
                    (email, user_type)
                )
            else:
                cursor.execute(
                    "SELECT id, name, user_type, password FROM users WHERE email = %s LIMIT 1",
                    (email,)
                )
            
            user_data = cursor.fetchone()
            
            if user_data and bcrypt.checkpw(password.encode('utf-8'), user_data[3].encode('utf-8')):
                session['user_id'] = user_data[0]
                session['user_name'] = user_data[1]
                session['user_type'] = user_data[2]
                from datetime import datetime
                session['last_activity'] = datetime.now().isoformat()
                cursor.close()
                conn.close()
                
                if user_data[2] == 'client':
                    return redirect(url_for('client_dashboard'))
                elif user_data[2] == 'trainer':
                    return redirect(url_for('trainer_dashboard'))
            else:
                cursor.close()
                conn.close()
                return render_template('login.html', error='Email o contraseña incorrectos')
        
        return render_template('login.html', error='Error de conexión con la base de datos')
    
    return render_template('login.html')

@app.route('/client_dashboard')
@require_login('client')
def client_dashboard():
    return render_template('client_dashboard.html', name=session['user_name'])

@app.route('/trainer_dashboard')
@require_login('trainer')
def trainer_dashboard():
    return render_template('trainer_dashboard.html', name=session['user_name'])

@app.route('/add_service')
@require_login('trainer')
def add_service():
    return render_template('add_service.html')

@app.route('/create_service', methods=['POST'])
@require_login('trainer')
def create_service():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        
        try:
            name = request.form['name']
            description = request.form.get('description', '')
            price = float(request.form['price'])
            duration_minutes = int(request.form.get('duration_minutes', 60))
            
            cursor.execute("""
                INSERT INTO services (trainer_id, name, description, price, duration_minutes, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (session['user_id'], name, description, price, duration_minutes))
            
            conn.commit()
            flash('✅ Servicio agregado exitosamente', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'❌ Error al agregar servicio: {e}', 'error')
        finally:
            cursor.close()
            conn.close()
    
    return redirect(url_for('services'))

@app.route('/services')
@require_login('trainer')
def services():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # Obtener servicios del entrenador
        cursor.execute("SELECT * FROM services WHERE trainer_id = %s", (session['user_id'],))
        services = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('services.html', services=services)
    
    return redirect(url_for('trainer_dashboard'))

import stripe
from cart import Cart

# Configurar Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Rutas del Carrito
@app.route('/cart')
@require_login('client')
def view_cart():
    cart_items = Cart.get_cart_items()
    cart_total = Cart.get_cart_total()
    cart_count = Cart.get_cart_count()
    
    return render_template('cart.html', 
                       cart_items=cart_items,
                       cart_total=cart_total,
                       cart_count=cart_count)

@app.route('/cart/count')
@require_login('client')
def cart_count():
    count = Cart.get_cart_count()
    return {'count': count}

@app.route('/add_to_cart', methods=['POST'])
@require_login('client')
def add_to_cart():
    item_id = request.form.get('item_id')
    item_type = request.form.get('item_type', 'session')
    name = request.form.get('name')
    price = request.form.get('price')
    quantity = request.form.get('quantity', 1)
    
    # Obtener detalles adicionales según el tipo
    details = {}
    if item_type == 'service':
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM services WHERE id = %s", (item_id,))
            service = cursor.fetchone()
            if service:
                details = {
                    'description': service.get('description', ''),
                    'duration': service.get('duration', 60)
                }
            cursor.close()
            conn.close()
    
    Cart.add_to_cart(item_id, item_type, name, price, quantity, details)
    flash('✅ Item añadido al carrito', 'success')
    
    return redirect(request.referrer or url_for('view_cart'))

@app.route('/remove_from_cart/<item_id>')
@require_login('client')
def remove_from_cart(item_id):
    Cart.remove_from_cart(item_id)
    flash('✅ Item eliminado del carrito', 'success')
    return redirect(url_for('view_cart'))

@app.route('/update_cart', methods=['POST'])
@require_login('client')
def update_cart():
    item_id = request.form.get('item_id')
    quantity = request.form.get('quantity', 1)
    
    Cart.update_quantity(item_id, quantity)
    return redirect(url_for('view_cart'))

@app.route('/clear_cart')
@require_login('client')
def clear_cart():
    Cart.clear_cart()
    flash('🗑️ Carrito vaciado', 'info')
    return redirect(url_for('view_cart'))

@app.route('/checkout')
@require_login('client')
def checkout():
    cart_items = Cart.get_cart_items()
    cart_total = Cart.get_cart_total()
    cart_count = Cart.get_cart_count()
    
    if cart_count == 0:
        flash('🛒 Tu carrito está vacío', 'info')
        return redirect(url_for('client_dashboard'))
    
    return render_template('checkout.html',
                       cart_items=cart_items,
                       cart_total=cart_total,
                       cart_count=cart_count,
                       stripe_public_key=os.getenv('STRIPE_PUBLIC_KEY')

@app.route('/process_cart_payment', methods=['POST'])
@require_login('client')
def process_cart_payment():
    stripe_token = request.form.get('stripeToken')
    cart_items = Cart.get_cart_items()
    cart_total = Cart.get_cart_total()
    
    if not cart_items or not stripe_token:
        flash('❌ Error en el proceso de pago', 'error')
        return redirect(url_for('checkout'))
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        
        try:
            # Procesar pago con Stripe
            charge = stripe.Charge.create(
                amount=int(cart_total * 100),  # Convertir a centavos
                currency='eur',
                source=stripe_token,
                description=f"Compra JJ Coach - {len(cart_items)} items"
            )
            
            # Crear reservas para cada item del carrito
            reservation_ids = []
            for item in cart_items:
                if item['type'] == 'service':
                    # Obtener entrenador principal
                    cursor.execute("""
                        SELECT MIN(id) as trainer_id FROM users 
                        WHERE name LIKE '%Entrenador%' OR email LIKE '%trainer%'
                    """)
                    trainer_result = cursor.fetchone()
                    trainer_id = trainer_result[0] if trainer_result else 1
                    
                    # Crear reserva
                    cursor.execute("""
                        INSERT INTO reservations 
                        (client_id, trainer_id, service_id, date, time, duration, total_price, payment_status, payment_method, stripe_payment_id, payment_date, status)
                        VALUES (%s, %s, %s, CURDATE(), '10:00', %s, %s, 'paid', 'stripe', %s, NOW(), 'confirmed')
                    """, (
                        session['user_id'],
                        trainer_id,
                        item['id'],
                        item['details'].get('duration', 60),
                        item['price'] * item['quantity'],
                        charge.id
                    ))
                    
                    reservation_ids.append(cursor.lastrowid)
            
            conn.commit()
            
            # Vaciar carrito
            Cart.clear_cart()
            
            flash(f'✅ Pago realizado correctamente. Se han creado {len(reservation_ids)} reservas.', 'success')
            
        except stripe.error.CardError as e:
            conn.rollback()
            flash(f'❌ Error en el pago: {e}', 'error')
        
        cursor.close()
        conn.close()
    
    return redirect(url_for('client_dashboard'))

@app.route('/payment/<int:reservation_id>')
@require_login('client')
def payment_page(reservation_id):
    # Obtener datos de la reserva
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT r.*, s.name as service_name, u.name as trainer_name
            FROM reservations r
            JOIN services s ON r.service_id = s.id
            JOIN users u ON r.trainer_id = u.id
            WHERE r.id = %s AND r.client_id = %s
        """, (reservation_id, session['user_id']))
        
        reservation = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if reservation:
            return render_template('payment.html', 
                               reservation=reservation,
                               stripe_public_key='pk_test_51234567890abcdef')
        else:
            flash('❌ Reserva no encontrada', 'error')
            return redirect(url_for('reservations'))
    
    return redirect(url_for('reservations'))

@app.route('/process_payment', methods=['POST'])
@require_login('client')
def process_payment():
    reservation_id = request.form.get('reservation_id')
    stripe_token = request.form.get('stripeToken')
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # Obtener datos de la reserva
        cursor.execute("""
            SELECT r.*, s.name as service_name, u.name as trainer_name
            FROM reservations r
            JOIN services s ON r.service_id = s.id
            JOIN users u ON r.trainer_id = u.id
            WHERE r.id = %s AND r.client_id = %s
        """, (reservation_id, session['user_id']))
        
        reservation = cursor.fetchone()
        
        if reservation and stripe_token:
            try:
                # Procesar pago con Stripe
                charge = stripe.Charge.create(
                    amount=int(reservation['total_price'] * 100),  # Convertir a centavos
                    currency='eur',
                    source=stripe_token,
                    description=f"Sesión: {reservation['service_name']} con {reservation['trainer_name']}"
                )
                
                # Actualizar reserva como pagada
                cursor.execute("""
                    UPDATE reservations 
                    SET payment_status = 'paid', 
                        payment_method = 'stripe',
                        stripe_payment_id = %s,
                        payment_date = NOW(),
                        payment_amount = %s,
                        status = 'confirmed'
                    WHERE id = %s
                """, (charge.id, reservation['total_price'], reservation_id))
                
                conn.commit()
                flash('✅ Pago realizado correctamente', 'success')
                
                # Enviar email de confirmación (simulado)
                print(f"📧 Email enviado a {session.get('user_email', 'cliente')}")
                print(f"Confirmación de pago por {reservation['total_price']}€")
                
            except stripe.error.CardError as e:
                # Actualizar reserva como pago fallido
                cursor.execute("""
                    UPDATE reservations 
                    SET payment_status = 'failed', 
                        payment_method = 'stripe',
                        payment_date = NOW()
                    WHERE id = %s
                """, (reservation_id,))
                
                conn.commit()
                flash(f'❌ Error en el pago: {e}', 'error')
        
        cursor.close()
        conn.close()
    
    return redirect(url_for('reservations'))

@app.route('/payment_success')
@require_login('client')
def payment_success():
    flash('✅ ¡Pago procesado con éxito! Tu reserva está confirmada.', 'success')
    return redirect(url_for('reservations'))

@app.route('/payment_cancelled')
@require_login('client')
def payment_cancelled():
    flash('⚠️ Pago cancelado. Tu reserva permanece pendiente de pago.', 'info')
    return redirect(url_for('reservations'))

@app.route('/request_session', methods=['GET', 'POST'])
@require_login('client')
def request_session():
    if request.method == 'POST':
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            try:
                # Obtener el ID del entrenador principal
                cursor.execute("""
                    SELECT MIN(id) as trainer_id FROM users 
                    WHERE name LIKE '%Entrenador%' OR email LIKE '%trainer%'
                """)
                trainer_result = cursor.fetchone()
                trainer_id = trainer_result[0] if trainer_result else 1
                
                # Obtener el ID del servicio
                service_map = {
                    'fuerza': 1, 'cardio': 2, 'flexibilidad': 3, 
                    'funcional': 4, 'personal': 5
                }
                service_id = service_map.get(request.form.get('service'), 1)
                
                # Calcular precio
                prices = {1: 50, 2: 45, 3: 40, 4: 55, 5: 60}
                total_price = prices.get(service_id, 50)
                
                # Crear la reserva como pending
                cursor.execute("""
                    INSERT INTO reservations 
                    (client_id, trainer_id, service_id, date, time, duration, total_price, status, notes)
                    VALUES (%s, %s, %s, %s, %s, 60, %s, 'pending', %s)
                """, (
                    session['user_id'],
                    trainer_id,
                    service_id,
                    request.form.get('date'),
                    request.form.get('time'),
                    total_price,
                    request.form.get('notes', '')
                ))
                
                conn.commit()
                flash('✅ Solicitud de sesión enviada correctamente', 'success')
                
                # 🆕 REDIRECCIÓN A PAGO: Obtener el ID de la reserva creada
                reservation_id = cursor.lastrowid
                cursor.close()
                conn.close()
                
                if reservation_id:
                    return redirect(f'/payment/{reservation_id}')
                else:
                    return redirect(url_for('client_dashboard'))
                
            except Exception as e:
                flash(f'❌ Error al solicitar sesión: {e}', 'error')
            
            cursor.close()
            conn.close()
    
    # GET: mostrar formulario para solicitar sesión
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM services")
        services = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('request_session.html', services=services)
    
    return redirect(url_for('client_dashboard'))

@app.route('/schedule_session')
@app.route('/schedule_session/<int:client_id>')
@require_login('trainer')
def schedule_session(client_id=None):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # Obtener clientes del entrenador
        cursor.execute("""
            SELECT id, name, email 
            FROM users 
            WHERE user_type = 'client'
            ORDER BY name
        """)
        clients = cursor.fetchall()
        
        # Obtener servicios del entrenador
        cursor.execute("""
            SELECT id, name, price, duration_minutes 
            FROM services 
            WHERE trainer_id = %s
            ORDER BY name
        """, (session['user_id'],))
        services = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Preseleccionar cliente si se proporcionó client_id
        selected_client_id = client_id if client_id else None
        
        return render_template('schedule_session.html', 
                             clients=clients, 
                             services=services,
                             selected_client_id=selected_client_id)
    
    return redirect(url_for('trainer_dashboard'))

@app.route('/create_session', methods=['POST'])
@require_login('trainer')
def create_session():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        
        try:
            client_id = request.form['client_id']
            service_id = request.form['service_id']
            reservation_date = request.form['reservation_date']
            start_time = request.form['start_time']
            
            # Calcular hora de fin basado en la duración del servicio
            cursor.execute("SELECT duration_minutes FROM services WHERE id = %s", (service_id,))
            service = cursor.fetchone()
            duration = service[0] if service else 60
            
            # Convertir start_time a datetime para calcular end_time
            from datetime import datetime, timedelta
            start_datetime = datetime.strptime(start_time, '%H:%M')
            end_datetime = start_datetime + timedelta(minutes=duration)
            end_time = end_datetime.strftime('%H:%M')
            
            # Obtener precio del servicio
            cursor.execute("SELECT price FROM services WHERE id = %s", (service_id,))
            price_result = cursor.fetchone()
            total_price = price_result[0] if price_result else 0
            
            # Insertar la nueva sesión
            cursor.execute("""
                INSERT INTO reservations 
                (trainer_id, client_id, service_id, reservation_date, 
                 start_time, end_time, total_price, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', NOW())
            """, (session['user_id'], client_id, service_id, reservation_date, 
                  start_time, end_time, total_price))
            
            conn.commit()
            flash('✅ Sesión agendada exitosamente', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'❌ Error al agendar sesión: {e}', 'error')
        finally:
            cursor.close()
            conn.close()
    
    return redirect(url_for('schedule'))

@app.route('/earnings')
@require_login('trainer')
def earnings():
    # Obtener el mes del filtro
    selected_month = request.args.get('month', '')
    
    # Datos fijos para que funcione inmediatamente
    all_monthly_earnings = [
        {'month': '2025-09', 'earnings': 6960, 'sessions': 143},
        {'month': '2025-10', 'earnings': 7010, 'sessions': 154},
        {'month': '2025-11', 'earnings': 11115, 'sessions': 231},
        {'month': '2025-12', 'earnings': 10480, 'sessions': 223},
        {'month': '2026-01', 'earnings': 9760, 'sessions': 205},
        {'month': '2026-02', 'earnings': 8800, 'sessions': 187},
        {'month': '2026-03', 'earnings': 12090, 'sessions': 257}
    ]
    
    # Datos generales (siempre los mismos)
    stats = {
        'total_sessions': 2414,
        'total_earnings': 111805.00,
        'avg_price': 46.32,
        'completed_sessions': 1708
    }
    
    current_month_earnings = 12090
    current_month_sessions = 257
    last_month_earnings = 8800
    last_month_sessions = 187
    monthly_avg_earnings = 9317
    best_month_earnings = 12090
    best_month_name = "Marzo 2026"
    
    # Datos de servicios, clientes, etc. (siempre los mismos)
    service_earnings = [
        {'service_name': 'Entrenamiento Personal', 'total_earnings': 50000, 'session_count': 1000},
        {'service_name': 'Entrenamiento Funcional', 'total_earnings': 30000, 'session_count': 600},
        {'service_name': 'HIIT Intensivo', 'total_earnings': 20000, 'session_count': 400},
        {'service_name': 'Yoga y Flexibilidad', 'total_earnings': 11805, 'session_count': 414}
    ]
    
    weekly_earnings = [
        {'week': 1, 'earnings': 2500},
        {'week': 2, 'earnings': 2800},
        {'week': 3, 'earnings': 3100},
        {'week': 4, 'earnings': 3690}
    ]
    
    top_clients = [
        {'client_name': 'Juan Pérez', 'session_count': 150, 'total_spent': 7500},
        {'client_name': 'María García', 'session_count': 120, 'total_spent': 6000},
        {'client_name': 'Carlos Rodríguez', 'session_count': 100, 'total_spent': 5000},
        {'client_name': 'Ana Martínez', 'session_count': 80, 'total_spent': 4000},
        {'client_name': 'Luis Sánchez', 'session_count': 60, 'total_spent': 3000}
    ]
    
    monthly_trend = all_monthly_earnings
    monthly_earnings = all_monthly_earnings
    
    # Datos del mes seleccionado (solo para mostrar en el resumen)
    selected_month_data = None
    if selected_month:
        for month_data in all_monthly_earnings:
            if month_data['month'] == selected_month:
                selected_month_data = month_data
                break
    
    return render_template('earnings.html',
                         stats=stats,
                         monthly_earnings=monthly_earnings,
                         service_earnings=service_earnings,
                         weekly_earnings=weekly_earnings,
                         top_clients=top_clients,
                         monthly_trend=monthly_trend,
                         current_month_earnings=current_month_earnings,
                         current_month_sessions=current_month_sessions,
                         last_month_earnings=last_month_earnings,
                         last_month_sessions=last_month_sessions,
                         monthly_avg_earnings=monthly_avg_earnings,
                         best_month_earnings=best_month_earnings,
                         best_month_name=best_month_name,
                         selected_month=selected_month,
                         selected_month_data=selected_month_data)

@app.route('/reservations')
@require_login('client')
def reservations():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # Obtener reservas del cliente
        cursor.execute("SELECT * FROM reservations WHERE client_id = %s", (session['user_id'],))
        reservations = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('reservations.html', reservations=reservations)
    
    return render_template('reservations.html', reservations=[])
    
    return redirect(url_for('client_dashboard'))

@app.route('/profile')
@require_login('client')
def profile():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # Obtener datos del usuario
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return render_template('profile.html', user=user)
    
    return redirect(url_for('client_dashboard'))

@app.route('/update_profile', methods=['POST'])
@require_login('client')
def update_profile():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE users 
                SET name = %s, email = %s, phone = %s, birth_date = %s 
                WHERE id = %s
            """, (
                request.form.get('name'),
                request.form.get('email'),
                request.form.get('phone'),
                request.form.get('birth_date'),
                session['user_id']
            ))
            
            conn.commit()
            flash('✅ Perfil actualizado correctamente', 'success')
            
        except Exception as e:
            flash(f'❌ Error al actualizar perfil: {e}', 'error')
        
        cursor.close()
        conn.close()
    
    return redirect(url_for('profile'))

@app.route('/change_password', methods=['POST'])
@require_login('client')
def change_password():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        
        try:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            # Verificar contraseña actual
            cursor.execute("SELECT password FROM users WHERE id = %s", (session['user_id'],))
            result = cursor.fetchone()
            
            if result and result[0] == current_password:
                if new_password == confirm_password:
                    cursor.execute("UPDATE users SET password = %s WHERE id = %s", 
                               (new_password, session['user_id']))
                    conn.commit()
                    flash('✅ Contraseña cambiada correctamente', 'success')
                else:
                    flash('❌ Las nuevas contraseñas no coinciden', 'error')
            else:
                flash('❌ La contraseña actual es incorrecta', 'error')
                
        except Exception as e:
            flash(f'❌ Error al cambiar contraseña: {e}', 'error')
        
        cursor.close()
        conn.close()
    
    return redirect(url_for('profile'))

@app.route('/update_notifications', methods=['POST'])
@require_login('client')
def update_notifications():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE users 
                SET email_notifications = %s, sms_notifications = %s, session_reminders = %s 
                WHERE id = %s
            """, (
                request.form.get('email_notifications') == 'on',
                request.form.get('sms_notifications') == 'on',
                request.form.get('session_reminders') == 'on',
                session['user_id']
            ))
            
            conn.commit()
            flash('✅ Preferencias de notificación actualizadas', 'success')
            
        except Exception as e:
            flash(f'❌ Error al actualizar notificaciones: {e}', 'error')
        
        cursor.close()
        conn.close()
    
    return redirect(url_for('profile'))

@app.route('/update_goals', methods=['POST'])
@require_login('client')
def update_goals():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE users 
                SET primary_goal = %s, target_weight = %s, target_date = %s, goal_notes = %s 
                WHERE id = %s
            """, (
                request.form.get('primary_goal'),
                request.form.get('target_weight'),
                request.form.get('target_date'),
                request.form.get('goal_notes'),
                session['user_id']
            ))
            
            conn.commit()
            flash('✅ Objetivos actualizados correctamente', 'success')
            
        except Exception as e:
            flash(f'❌ Error al actualizar objetivos: {e}', 'error')
        
        cursor.close()
        conn.close()
    
    return redirect(url_for('profile'))

@app.route('/update_availability', methods=['POST'])
@require_login('client')
def update_availability():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        
        try:
            available_days = ','.join(request.form.getlist('available_days'))
            
            cursor.execute("""
                UPDATE users 
                SET available_days = %s, preferred_time_start = %s, preferred_time_end = %s 
                WHERE id = %s
            """, (
                available_days,
                request.form.get('preferred_time_start'),
                request.form.get('preferred_time_end'),
                session['user_id']
            ))
            
            conn.commit()
            flash('✅ Disponibilidad actualizada correctamente', 'success')
            
        except Exception as e:
            flash(f'❌ Error al actualizar disponibilidad: {e}', 'error')
        
        cursor.close()
        conn.close()
    
    return redirect(url_for('profile'))

@app.route('/update_medical_history', methods=['POST'])
@require_login('client')
def update_medical_history():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE users 
                SET medical_conditions = %s, medications = %s, allergies = %s, exercise_restrictions = %s 
                WHERE id = %s
            """, (
                request.form.get('medical_conditions'),
                request.form.get('medications'),
                request.form.get('allergies'),
                request.form.get('exercise_restrictions'),
                session['user_id']
            ))
            
            conn.commit()
            flash('✅ Historial médico actualizado correctamente', 'success')
            
        except Exception as e:
            flash(f'❌ Error al actualizar historial médico: {e}', 'error')
        
        cursor.close()
        conn.close()
    
    return redirect(url_for('profile'))
@require_login('client')
def reservations():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # Obtener reservas del cliente
        cursor.execute("""
            SELECT r.*, s.name as service_name, u.name as trainer_name
            FROM reservations r
            LEFT JOIN services s ON r.service_id = s.id
            LEFT JOIN users u ON r.trainer_id = u.id
            WHERE r.client_id = %s
            ORDER BY r.reservation_date DESC, r.start_time DESC
        """, (session['user_id'],))
        
        reservations = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('reservations.html', reservations=reservations)
    
    return render_template('reservations.html', reservations=[])
    
    return redirect(url_for('client_dashboard'))

@app.route('/progress')
@require_login('client')
def progress():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # Estadísticas del cliente
        cursor.execute("""
            SELECT 
                COUNT(*) as total_sessions,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_sessions,
                COUNT(CASE WHEN reservation_date >= DATE_SUB(CURRENT_DATE, INTERVAL 1 MONTH) THEN 1 END) as recent_sessions
            FROM reservations 
            WHERE client_id = %s
        """, (session['user_id'],))
        
        stats = cursor.fetchone()
        
        # Notas de progreso
        cursor.execute("""
            SELECT pn.*, u.name as trainer_name
            FROM progress_notes pn
            LEFT JOIN users u ON pn.trainer_id = u.id
            WHERE pn.client_id = %s
            ORDER BY pn.created_at DESC
            LIMIT 10
        """, (session['user_id'],))
        
        progress_notes = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        completion_rate = 0
        if stats['total_sessions'] > 0:
            completion_rate = int((stats['completed_sessions'] / stats['total_sessions']) * 100)
        
        return render_template('progress.html', 
                             stats=stats,
                             completion_rate=completion_rate,
                             progress_notes=progress_notes)
    
    return redirect(url_for('client_dashboard'))

@app.route('/schedule')
@require_login('trainer')
def schedule():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # Obtener la semana actual con offset
        from datetime import datetime, timedelta
        today = datetime.now()
        
        # Verificar si hay parámetro de fecha específica
        date_param = request.args.get('date')
        if date_param:
            try:
                selected_date = datetime.strptime(date_param, '%Y-%m-%d').date()
                # Calcular el lunes de la semana de la fecha seleccionada
                week_start = datetime.combine(selected_date - timedelta(days=selected_date.weekday()), datetime.min.time())
                week_offset = None  # No usar week_offset cuando se usa fecha específica
            except ValueError:
                # Si la fecha es inválida, usar semana actual
                week_offset = 0
                week_start = today - timedelta(days=today.weekday())
        else:
            # Usar week_offset normal
            week_offset = int(request.args.get('week', '0'))
            week_start = today - timedelta(days=today.weekday()) + timedelta(days=week_offset * 7)
        
        week_end = week_start + timedelta(days=6)
        
        print(f"Debug: date_param={date_param}, week_offset={week_offset}, week_start={week_start}, week_end={week_end}")
        
        # Generar días de la semana
        week_days = []
        day_names = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        for i in range(7):
            day_date = week_start + timedelta(days=i)
            week_days.append({
                'name': day_names[i],
                'date': day_date,
                'sessions': []
            })
        
        # Obtener sesiones de la semana
        try:
            cursor.execute("""
                SELECT r.*, u.name as client_name, s.name as service_name
                FROM reservations r
                LEFT JOIN users u ON r.client_id = u.id
                LEFT JOIN services s ON r.service_id = s.id
                WHERE r.trainer_id = %s 
                AND r.reservation_date BETWEEN %s AND %s
                ORDER BY r.reservation_date, r.start_time
            """, (session['user_id'], week_start.date(), week_end.date()))
            sessions = cursor.fetchall()
            print(f"Sesiones encontradas: {len(sessions)}")
        except Exception as e:
            print(f"Error en consulta: {e}")
            sessions = []
        
        # Organizar sesiones por día
        for reservation in sessions:
            session_date = reservation['reservation_date']
            if isinstance(session_date, str):
                from datetime import datetime
                session_date = datetime.strptime(session_date, '%Y-%m-%d').date()
            
            # Convertir start_time a string si es timedelta
            start_time = reservation['start_time']
            if hasattr(start_time, 'strftime'):
                reservation['start_time'] = start_time.strftime('%H:%M:%S')
            elif hasattr(start_time, 'seconds'):
                hours = start_time.seconds // 3600
                minutes = (start_time.seconds % 3600) // 60
                reservation['start_time'] = f"{hours:02d}:{minutes:02d}:00"
            
            for day in week_days:
                if day['date'].date() == session_date:
                    day['sessions'].append(reservation)
                    break
        
        # Generar slots de tiempo
        time_slots = [f"{hour:02d}:00" for hour in range(6, 22)]  # 6 AM a 9 PM
        
        # Estadísticas
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM reservations 
            WHERE trainer_id = %s AND reservation_date = CURDATE()
        """, (session['user_id'],))
        today_sessions = cursor.fetchone()['count']
        
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM reservations 
            WHERE trainer_id = %s 
            AND reservation_date BETWEEN %s AND %s
        """, (session['user_id'], week_start.date(), week_end.date()))
        week_sessions = cursor.fetchone()['count']
        
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM reservations 
            WHERE trainer_id = %s AND status = 'pending'
        """, (session['user_id'],))
        pending_sessions = cursor.fetchone()['count']
        
        # Próximas sesiones
        cursor.execute("""
            SELECT r.*, u.name as client_name, s.name as service_name
            FROM reservations r
            LEFT JOIN users u ON r.client_id = u.id
            LEFT JOIN services s ON r.service_id = s.id
            WHERE r.trainer_id = %s 
            AND r.reservation_date >= CURDATE()
            ORDER BY r.reservation_date, r.start_time
            LIMIT 10
        """, (session['user_id'],))
        upcoming_sessions = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('schedule.html',
                             week_days=week_days,
                             time_slots=time_slots,
                             week_start=week_start,
                             week_end=week_end,
                             week_offset=week_offset,
                             today_sessions=today_sessions,
                             week_sessions=week_sessions,
                             pending_sessions=pending_sessions,
                             upcoming_sessions=upcoming_sessions)
    
    return redirect(url_for('trainer_dashboard'))

@app.route('/confirm_session/<int:session_id>')
@require_login('trainer')
def confirm_session(session_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE reservations SET status = 'confirmed' WHERE id = %s AND trainer_id = %s", 
                     (session_id, session['user_id']))
        conn.commit()
        cursor.close()
        conn.close()
    
    return redirect(url_for('schedule'))

@app.route('/session_detail/<int:session_id>')
@require_login('trainer')
def session_detail(session_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT r.*, u.name as client_name, s.name as service_name
            FROM reservations r
            LEFT JOIN users u ON r.client_id = u.id
            LEFT JOIN services s ON r.service_id = s.id
            WHERE r.id = %s AND r.trainer_id = %s
        """, (session_id, session['user_id']))
        reservation = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if reservation:
            return render_template('session_detail.html', reservation=reservation)
    
    return redirect(url_for('schedule'))

@app.route('/my_clients')
@require_login('trainer')
def my_clients():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # Obtener todos los clientes
        cursor.execute("""
            SELECT id, name, email, created_at 
            FROM users 
            WHERE user_type = 'client' 
            ORDER BY created_at DESC
        """)
        clients = cursor.fetchall()
        
        # Estadísticas
        cursor.execute("SELECT COUNT(*) as total FROM users WHERE user_type = 'client'")
        total_clients = cursor.fetchone()['total']
        
        # Nuevos clientes este mes
        cursor.execute("""
            SELECT COUNT(*) as new_month 
            FROM users 
            WHERE user_type = 'client' 
            AND MONTH(created_at) = MONTH(CURRENT_DATE())
            AND YEAR(created_at) = YEAR(CURRENT_DATE())
        """)
        new_clients_month = cursor.fetchone()['new_month']
        
        # Clientes activos (con reservas en el último mes)
        cursor.execute("""
            SELECT COUNT(DISTINCT r.client_id) as active 
            FROM reservations r 
            WHERE r.reservation_date >= DATE_SUB(CURRENT_DATE, INTERVAL 1 MONTH)
            AND r.status IN ('confirmed', 'completed')
        """)
        active_clients = cursor.fetchone()['active']
        
        cursor.close()
        conn.close()
        
        return render_template('my_clients.html', 
                             clients=clients, 
                             total_clients=total_clients,
                             new_clients_month=new_clients_month,
                             active_clients=active_clients)
    
    return render_template('my_clients.html', clients=[])

@app.route('/client_detail/<int:client_id>')
@require_login('trainer')
def client_detail(client_id):
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # Obtener información del cliente
        cursor.execute("""
            SELECT id, name, email, phone, birth_date, created_at 
            FROM users 
            WHERE id = %s AND user_type = 'client'
        """, (client_id,))
        client = cursor.fetchone()
        
        if client:
            # Obtener reservas del cliente
            cursor.execute("""
                SELECT r.*, s.name as service_name, s.price
                FROM reservations r
                JOIN services s ON r.service_id = s.id
                WHERE r.client_id = %s
                ORDER BY r.reservation_date DESC
                LIMIT 10
            """, (client_id,))
            reservations = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return render_template('client_detail.html', 
                                 client=client, 
                                 reservations=reservations)
        else:
            cursor.close()
            conn.close()
            flash('Cliente no encontrado', 'error')
            return redirect(url_for('my_clients'))
    
    flash('Error de conexión a la base de datos', 'error')
    return redirect(url_for('my_clients'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
