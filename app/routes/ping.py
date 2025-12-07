from flask import Blueprint
from app.utils.response import standard_response

ping_bp = Blueprint('ping', __name__)


@ping_bp.route('/ping', methods=['GET'])
def ping():
    return standard_response(200, "pong", {"server": "flask", "status": "running"})
