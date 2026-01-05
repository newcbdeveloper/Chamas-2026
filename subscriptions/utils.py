from datetime import datetime, timedelta
from django.utils import timezone
import json
import jwt
import logging


logger = logging.getLogger(__name__)

def get_chama_id(request):
    path_parts = request.path.split('/')
    logger.debug("Path parts: %s", path_parts)
    try:
        chama_id_index = path_parts.index('chamas-bookeeping') + 2
        logger.debug("Chama ID index: %s", chama_id_index)
        chama_id = int(path_parts[chama_id_index])
        logger.debug("Chama ID from path: %s", chama_id)
        return chama_id
    except (ValueError, IndexError) as e:
        logger.debug("Error extracting Chama ID from path: %s", e)
        pass  

    try:
        chama_id = int(request.data.get('chama_id')) 
        return chama_id
    except (ValueError) as e:
        pass  

    try:
        chama_id = int(request.session.get('chama_id')) 
        return chama_id
    except (ValueError) as e:
        pass  

    return None


def generate_jwt(payload, secret):
    payload['exp'] = (timezone.now() + timedelta(hours=1)).timestamp()
    encoded_jwt = jwt.encode(payload, secret, algorithm='HS256')
    return encoded_jwt

def decode_jwt(jwt_token, secret):
    decoded_payload = jwt.decode(jwt_token, secret, algorithms=['HS256'])
    return decoded_payload