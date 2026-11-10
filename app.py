# poker_bankroll_analyzer/app.py
from poker_bankroll_analyzer import create_app

# trigger the factory to build the app instance
app = create_app()

if __name__ == '__main__':
    # Run the local development server on port 5001
    app.run(debug=True, port=5001)