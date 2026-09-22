# Database Configuration
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME', 'jj_coach_manager'),
            autocommit=False,
            pool_size=5,
            pool_reset_session=True
        )
        
        if connection.is_connected():
            print("✅ Conexión exitosa a MySQL")
            return connection
        else:
            print("❌ No se pudo establecer la conexión")
            return None
            
    except Error as e:
        print(f"❌ Error de conexión a MySQL: {e}")
        print(f"   Código de error: {e.errno}")
        print(f"   SQL State: {e.sqlstate}")
        return None
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return None

def close_db_connection(connection, cursor=None):
    """Cierra cursor y conexión de forma segura"""
    try:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            print("✅ Conexión cerrada correctamente")
    except Error as e:
        print(f"❌ Error cerrando conexión: {e}")