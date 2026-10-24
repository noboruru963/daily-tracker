# Daily - Habit Tracker App

A highly customizable, and highly personal habit tracker app built with Python Flask.

## Features

- **4 Visual Models**: Graph, Progression, Calendar, and Percentage tracking
- **Customizable Themes**: Choose colors and icons for your habits
- **Community Section**: Share and discover public habits
- **Simple Authentication**: Username/password registration and login
- **Responsive Design**: Works on desktop and mobile devices

## Visual Models

1. **Graph**: Track trends over time with line, bar, or area charts
2. **Progression**: Step-by-step progress tracking with locked/unlocked stages
3. **Calendar**: Time-based habit tracking with schedule management
4. **Percentage**: Progress towards a goal with min/max values

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/noboruru963/daily-tracker
   cd daily-tracker
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set environment variables:
   ```bash
   set SECRET_KEY=your-secret-key
   ```
   Use a strong, unique secret key in production. Passwords must be at least 8 characters and
   contain an uppercase letter and a symbol.

### Firebase Authentication and Python app database

Firebase Authentication handles sign-up, login, email verification, and password-reset emails. Flask/SQLAlchemy continues to store Daily Tracker user profiles, habits, and tracking data; the app does not use Firestore.

In PowerShell, copy `.env.example` to `.env` in the project folder and edit the Firebase settings. `run.py` loads this file when the app starts:

```powershell
Copy-Item .env.example .env
notepad .env
```

In the Firebase Console, enable **Authentication → Sign-in method → Email/Password** and add `localhost` to **Authentication → Settings → Authorized domains**. Get the exact `apiKey` from **Project settings → General → Your apps → SDK setup and configuration** and replace the placeholder in `.env`. A guessed or mistyped API key will be rejected by Firebase. The web API key is public client configuration; do not put private service-account credentials in the app.

Restart Flask after editing `.env`, then refresh the site with **Ctrl+F5**. The forgot-password form sends the request through Flask to Firebase Authentication's password-reset API; Firebase sends the reset email and updates the password used by Firebase login. Firebase may return a generic success response even when the email is not a Firebase account, so verify the address appears under **Authentication → Users**. A Python-only user record is not automatically a Firebase account. Existing Python user profiles and habits are linked to the verified Firebase account when the same email is used. Existing Python passwords do not transfer to Firebase.

If the address exists under **Authentication → Users** but Firebase emails still do not arrive, open **Authentication → Templates → SMTP settings** and configure an email sender you control. For Gmail, use `smtp.gmail.com`, port `587` with TLS, your Gmail address, and a Google App Password (requires 2-Step Verification). Never put that App Password in the web app or commit it to the repository. Firebase's default sender (`noreply@…firebaseapp.com`) is managed by Firebase; Flask's own SMTP settings do not control Firebase Auth emails.

5. Run the application:
   ```bash
   python run.py
   ```

6. Open your browser and go to: `http://127.0.0.1:5000`

## Project Structure

```
daily/
├── app/
│   ├── __init__.py          # Flask app initialization
│   ├── config.py            # Configuration settings
│   ├── models/              # Database models
│   │   ├── user.py
│   │   ├── habit.py
│   │   ├── record.py
│   │   ├── settings.py
│   │   └── community.py
│   ├── routes/              # URL routes
│   │   ├── auth.py
│   │   ├── habits.py
│   │   ├── tracking.py
│   │   └── community.py
│   ├── services/            # Business logic
│   │   ├── habit_service.py
│   │   ├── tracking_service.py
│   │   └── community_service.py
│   ├── templates/           # HTML templates
│   │   ├── base.html
│   │   ├── auth/
│   │   ├── habits/
│   │   ├── tracking/
│   │   └── community/
│   └── static/              # Static files
│       ├── css/
│       │   └── style.css
│       ├── js/
│       └── images/
├── tests/                   # Test files
│   ├── unit/
│   └── integration/
├── requirements.txt
└── run.py
```

## Testing

Run unit tests:
```bash
pytest tests/unit/
```

Run integration tests:
```bash
pytest tests/integration/
```

Run all tests:
```bash
pytest
```

## Development

### Team Structure
- **Frontend Developers (2)**: Focus on UI/UX, templates, and styling
- **Backend Developers (2)**: Focus on routes, models, and business logic

### Key Components

1. **Visual Models**: Each habit can choose one of 4 visual models
2. **Customization**: Users can customize colors, icons, and themes
3. **Community**: Share public habits and interact with other users
4. **Data Tracking**: Record numerical values with descriptions

### API Endpoints

- `GET /habits/dashboard` - User dashboard
- `POST /habits/create` - Create new habit
- `GET /habits/<id>` - View habit details
- `POST /tracking/<id>/add` - Add record to habit
- `GET /tracking/api/<id>/data` - Get habit data as JSON

## Technologies Used

- **Backend**: Python Flask, SQLAlchemy, Flask-Login
- **Frontend**: Bootstrap 5, Chart.js, Jinja2 templates
- **Database**: SQLite (development), PostgreSQL (production)
- **Testing**: pytest, Flask test client

## Contributing

1. Create a feature branch
2. Make your changes
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License.
