import razorpay
import logging
from config import RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

def create_razorpay_order(amount):
    try:
        order_data = {
            "amount": int(amount * 100),
            "currency": "INR",
            "payment_capture": 1
        }
        return razorpay_client.order.create(data=order_data)
    except razorpay.errors.ServerError as e:
        logging.error(f"Razorpay server error: {e}")
        raise Exception("Payment gateway is currently unavailable. Please try again later.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise Exception("An unexpected error occurred. Please try again later.")
