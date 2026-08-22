from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.ai_advisor import generate_ai_response, get_user_financial_context

chatbot_bp = Blueprint('chatbot', __name__)

@chatbot_bp.route('/chatbot')
@login_required
def index():
    """Render the AI Financial Advisor chat page"""
    context = get_user_financial_context(current_user.id)
    return render_template('chatbot.html', financial_context=context)


@chatbot_bp.route('/api/chatbot/message', methods=['POST'])
@login_required
def send_message():
    """API endpoint to receive chat messages and return Gemini AI responses"""
    data = request.get_json() or {}
    user_message = data.get('message', '').strip()
    history = data.get('history', [])

    if not user_message:
        return jsonify({"status": "error", "reply": "Please enter a valid message."}), 400

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
