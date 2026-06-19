"""
Módulo de hashing de contraseñas.

Implementa el esquema de seguridad solicitado:

        Contraseña + Pepper + Salt  ->  bcrypt

- Pepper: cadena secreta global almacenada en la variable de entorno PEPPER.
          Se concatena a la contraseña antes del hashing. A diferencia del
          salt, el pepper NO se guarda en la base de datos; vive únicamente
          en el entorno del servidor.
- Salt:   valor aleatorio único por contraseña. bcrypt lo genera
          automáticamente con gensalt() y lo incrusta dentro del hash final.
- bcrypt: función de derivación de clave lenta y adaptativa.

Para evitar el límite de 72 bytes que tiene bcrypt sobre su entrada (y la
truncación silenciosa que provoca), primero combinamos contraseña + pepper y
aplicamos SHA-256. El digest hexadecimal resultante (64 caracteres) se entrega
a bcrypt, que añade el salt y produce el hash definitivo.

En la base de datos se almacena ÚNICAMENTE el campo password_hash. La
contraseña en texto plano nunca se persiste.
"""

import hashlib
import os

import bcrypt

# Número de rondas de bcrypt (coste de trabajo). 12 es un valor recomendado
# que equilibra seguridad y tiempo de respuesta para un proyecto académico.
BCRYPT_ROUNDS = 12


def _get_pepper() -> str:
    """Obtiene el pepper desde el entorno."""
    return os.getenv("PEPPER", "")


def _prepare(password: str) -> bytes:
    """
    Combina la contraseña con el pepper y la normaliza a un digest SHA-256
    para mantenerla por debajo del límite de 72 bytes de bcrypt.
    """
    combinada = (password + _get_pepper()).encode("utf-8")
    digest = hashlib.sha256(combinada).hexdigest()
    return digest.encode("utf-8")


def hash_password(password: str) -> str:
    """
    Genera el hash bcrypt de una contraseña.

    Devuelve una cadena lista para guardar en la columna password_hash.
    """
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(_prepare(password), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verifica una contraseña en texto plano contra el hash almacenado.

    Devuelve True si coinciden, False en caso contrario.
    """
    try:
        return bcrypt.checkpw(_prepare(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Hash con formato inválido o nulo.
        return False
