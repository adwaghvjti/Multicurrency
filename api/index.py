from flask import Flask
from app import app as flask_app

# This exposes the Flask application for Vercel to use
app = flask_app

# Make the app available to the Vercel handler
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
