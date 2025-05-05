
RAZORPAY_KEY_ID = 'rzp_test_QexwuNHqMTPr9q'
RAZORPAY_KEY_SECRET = 'vNUOKhPUjFFkShUOJnZyQQTA'
MONGO_URI = "mongodb+srv://adityaw12:IASa%401324@vjti.5qlebit.mongodb.net/"
NEWS_API_KEY = 'faa95bb57476497e8245b03dd6c97ff7'
NEWS_API_URL = 'https://newsapi.org/v2/everything'
EXCHANGE_API_URL = 'https://api.exchangerate-api.com/v4/latest/'

IMPORTANT_CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'CNY', 'INR', 'BRL']

import pymongo
mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client['wallet_db']
users_collection = db['users']
transactions_collection = db['transactions']

