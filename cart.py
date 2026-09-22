# Carrito de compras - Sesión
from flask import session

class Cart:
    @staticmethod
    def get_cart():
        """Obtener el carrito de la sesión"""
        return session.get('cart', {})
    
    @staticmethod
    def add_to_cart(item_id, item_type, name, price, quantity=1, details=None):
        """Añadir item al carrito"""
        cart = Cart.get_cart()
        
        if item_id not in cart:
            cart[item_id] = {
                'id': item_id,
                'type': item_type,  # 'session' o 'service'
                'name': name,
                'price': float(price),
                'quantity': int(quantity),
                'details': details or {}
            }
        else:
            cart[item_id]['quantity'] += int(quantity)
        
        session['cart'] = cart
        return True
    
    @staticmethod
    def remove_from_cart(item_id):
        """Eliminar item del carrito"""
        cart = Cart.get_cart()
        
        if item_id in cart:
            del cart[item_id]
            session['cart'] = cart
            return True
        return False
    
    @staticmethod
    def update_quantity(item_id, quantity):
        """Actualizar cantidad de un item"""
        cart = Cart.get_cart()
        
        if item_id in cart and int(quantity) > 0:
            cart[item_id]['quantity'] = int(quantity)
            session['cart'] = cart
            return True
        return False
    
    @staticmethod
    def clear_cart():
        """Vaciar el carrito"""
        session['cart'] = {}
        return True
    
    @staticmethod
    def get_cart_total():
        """Calcular total del carrito"""
        cart = Cart.get_cart()
        total = 0
        
        for item in cart.values():
            total += item['price'] * item['quantity']
        
        return total
    
    @staticmethod
    def get_cart_count():
        """Obtener número de items en el carrito"""
        cart = Cart.get_cart()
        return sum(item['quantity'] for item in cart.values())
    
    @staticmethod
    def get_cart_items():
        """Obtener lista de items del carrito"""
        return list(Cart.get_cart().values())
