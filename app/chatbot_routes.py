from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.ai_advisor import generate_ai_response, get_user_financial_context
from app.api_guard import rate_limited, sanitize_error_message, log_api_event
from config import Config
import logging

logger = logging.getLogger(__name__)

chatbot_bp = Blueprint('chatbot', __name__)

@chatbot_bp.route('/chatbot')
@login_required
def index():
    """Render the AI Financial Advisor chat page"""
    context = get_user_financial_context(current_user.id)
    return render_template('chatbot.html', financial_context=context)


@chatbot_bp.route('/api/chatbot/message', methods=['POST'])
@login_required
@rate_limited(limit=Config.RATE_LIMIT_CHATBOT, window=60, action='chatbot_message', is_json=True)
def send_message():
    """API endpoint to receive chat messages and return Gemini AI responses"""
    data = request.get_json() or {}
    user_message = data.get('message', '').strip()
    history = data.get('history', [])

    if not user_message:
        return jsonify({"status": "error", "reply": "Please enter a valid message."}), 400

    try:
        reply = generate_ai_response(
            user_id=current_user.id,
            username=current_user.username,
            user_message=user_message,
            chat_history=history
        )

        return jsonify({
            "status": "success",
            "reply": reply
        })
    except Exception as e:
        safe_err = sanitize_error_message(e)
        logger.error(f"Chatbot route unexpected error: {safe_err}", exc_info=True)
        return jsonify({
            "status": "error",
            "reply": "AI service is temporarily unavailable. Please try again shortly."
        }), 500

