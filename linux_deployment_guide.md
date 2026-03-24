# Linux Deployment Guide (Without Docker)

This guide provides step-by-step instructions to deploy the Content Validator backend on a Linux-based server (such as Ubuntu/Debian) without using Docker.

## 1. System Requirements

The backend requires several system-level libraries for image processing, video frame extraction, and OCR.

Update your package list and install the required dependencies:
```bash
sudo apt-get update
sudo apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    tesseract-ocr \
    ffmpeg \
    libgomp1 \
    mysql-server
```
*(Adjust the python version based on your local default, but Python 3.11+ is recommended based on the Dockerfile)*

## 2. Database Setup

The `init.sql` file contains the complete schema needed for the application.

1. Secure your MySQL installation:
   ```bash
   sudo mysql_secure_installation
   ```
2. Log into MySQL and create the database or simply import the `init.sql`:
   ```bash
   # Log into MySQL root
   sudo mysql -u root -p
   
   # You may want to create a dedicated user for the app here
   # CREATE USER 'cv_user'@'localhost' IDENTIFIED BY 'your_password';
   # GRANT ALL PRIVILEGES ON content_validator.* TO 'cv_user'@'localhost';
   # FLUSH PRIVILEGES;
   # exit;
   ```
3. Import the schema script (it will automatically create the `content_validator` database and its tables):
   ```bash
   mysql -u root -p < database/init.sql
   ```
   *Note: The `init.sql` is fully up-to-date with your current SQLAlchemy `models.py` structure, so no further schema patching is required upon first launch.*

## 3. Backend Setup

1. Navigate to the backend directory of the extracted codebase.
2. Create and activate a Python virtual environment:
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   ```
3. Install the required Python packages:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. Setup necessary application directories (if they don't exist):
   ```bash
   mkdir -p uploads/templates uploads/validations
   ```

## 4. Environment Configuration

Create a `.env` file in the `backend` directory with your database connection details and API keys. Use the same variables defined in your Docker setup:

```env
# Database configuration
DATABASE_URL=mysql+pymysql://<user>:<password>@localhost:3306/content_validator

# Replace with your API keys based on the app's needs
# ANTHROPIC_API_KEY=...
# OPENAI_API_KEY=...
```

## 5. Running the Application

To run the application for testing/development:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Production Recommendation
For a production deployment, it's highly recommended to run the app using `gunicorn` with `uvicorn` workers, and manage the process using `systemd`.

**Example Gunicorn Command:**
```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 120
```
