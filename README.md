# 🍅 AI-Driven Tomato Leaf Disease Detection System

An intelligent web-based application that detects tomato leaf diseases using Artificial Intelligence and Deep Learning.  
The system allows users to upload tomato leaf images and receive disease predictions along with care tips and management recommendations.

---

# 📌 Project Overview

This Final Year Project (FYP) combines:

- Artificial Intelligence
- Deep Learning
- Computer Vision
- Flask Web Development
- PostgreSQL Database
- Image Processing

The application is designed to help farmers, students, and agricultural researchers identify tomato plant diseases quickly and accurately.

---

# 🚀 Features

## 🌿 Disease Detection
- Upload tomato leaf images
- AI model predicts disease category
- Fast and accurate classification

## 🧠 Deep Learning Model
- TensorFlow-based trained model
- CNN (Convolutional Neural Network)
- Image preprocessing pipeline

## 👤 User Authentication
- User registration and login
- Password management
- Account dashboard

## 📊 Dashboard
- User profile management
- Prediction history
- Feedback handling

## 💡 Care Tips
- Disease treatment suggestions
- Prevention recommendations
- Tomato plant care guidance

## 📧 Email Services
- Forgot password support
- Email verification/recovery features

## 🔒 Security Features
- Rate limiting
- Secure password handling
- Input validation

---

# 🏗️ Project Structure

```bash
AI-Driven Tomato Leaf Disease Detection System/
│
├── app.py
├── config.py
├── requirements.txt
│
├── backend/
│   ├── email_service.py
│   ├── models.py
│   ├── model_handler.py
│   ├── preprocessor.py
│   ├── rate_limiter.py
│   └── routes.py
│
├── models/
│   ├── class_names.json
│   └── trained model code.ipynb
│
├── static/
│   ├── css/
│   ├── js/
│   ├── img/
│   └── vendor/
│
├── templates/
│   ├── about.html
│   ├── dashboard.html
│   ├── account.html
│   ├── contact.html
│   ├── feedback.html
│   └── partials/
│
└── __pycache__/
```

---

# 📖 Structure Explanation

## 1️⃣ app.py
Main entry point of the application.

Responsibilities:
- Starts Flask server
- Initializes application
- Connects routes and backend logic

---

## 2️⃣ config.py
Contains project configuration settings.

Examples:
- Database settings
- Secret keys
- Upload folder paths
- Flask configurations

---

# 📂 backend Folder

This folder contains the core backend logic of the system.

## email_service.py
Handles:
- Password reset emails
- User notifications
- Email communication system

---

## models.py
Contains database models.

Examples:
- User table
- Feedback table
- Prediction records

Uses:
- Flask-SQLAlchemy ORM

---

## model_handler.py
Responsible for:
- Loading trained AI model
- Running predictions
- Returning disease results

This is the main AI prediction engine.

---

## preprocessor.py
Handles image preprocessing before prediction.

Functions may include:
- Image resizing
- Normalization
- Noise reduction
- Tensor formatting

This improves model accuracy.

---

## rate_limiter.py
Provides security against:
- Spam requests
- Too many API hits
- Abuse attacks

Improves system stability and security.

---

## routes.py
Contains all Flask routes.

Examples:
- Login routes
- Upload routes
- Dashboard routes
- Prediction routes

Acts as the controller of the web application.

---

# 📂 models Folder

## class_names.json
Stores disease labels/classes.

Example:
```json
{
  "0": "Tomato Early Blight",
  "1": "Tomato Late Blight"
}
```

---

## trained model code.ipynb
Jupyter notebook used for:
- Model training
- Dataset preprocessing
- Accuracy evaluation
- Experimentation

This is where the AI model was developed.
You can download the trained model using the given link
https://drive.google.com/file/d/17FxEYTrjDGG7SNRktU6e63pJEpjlDDuc/view?usp=drive_link

---

# 📂 static Folder

Contains frontend static files.

## css/
Application styling files.

## js/
JavaScript functionality.

## img/
Images, logos, backgrounds.

## vendor/
Third-party frontend libraries:
- Bootstrap
- Bootstrap Icons

---

# 📂 templates Folder

Contains HTML templates using Flask/Jinja.

Examples:
- Login pages
- Dashboard pages
- About page
- FAQ page
- Feedback page

---

# 🔧 Technologies Used

## Backend
- Python
- Flask
- Flask-SQLAlchemy

## AI & ML
- TensorFlow
- CNN
- OpenCV
- NumPy

## Frontend
- HTML
- CSS
- JavaScript
- Bootstrap

## Database
- PostgreSQL

---

# ⚙️ Installation Guide

## 1️⃣ Clone Repository

```bash
git clone https://github.com/your-username/AI-Driven-Tomato-Leaf-Disease-Detection-System.git
```

---

## 2️⃣ Navigate to Project

```bash
cd AI-Driven-Tomato-Leaf-Disease-Detection-System
```

---

## 3️⃣ Create Virtual Environment

```bash
python -m venv venv
```

Activate environment:

### Windows
```bash
venv\Scripts\activate
```

### Linux/Mac
```bash
source venv/bin/activate
```

---

## 4️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 5️⃣ Configure Database

Setup PostgreSQL database and update configuration inside:

```bash
config.py
```

---

## 6️⃣ Run Application

```bash
python app.py
```

---

# 🧪 Future Improvements

- Mobile application integration
- Real-time camera detection
- Multi-crop disease detection
- Cloud deployment
- AI chatbot for farmers
- Multilingual support

---

# 📈 Project Strengths

✅ Clean folder organization  
✅ Modular backend architecture  
✅ AI + Web integration  
✅ Secure authentication system  
✅ Good separation of frontend and backend  
✅ Scalable project structure  

---





# 📚 Learning Outcomes

This project demonstrates practical knowledge of:
- Deep Learning
- Image Classification
- Computer Vision
- Flask Development
- Database Integration
- Full Stack Development
- AI Deployment

---

# 👨‍💻 Author

Final Year Project by:
**[Fakhar Zaman]**

Department of Computer Science

---

# 📄 License

This project is developed for educational and research purposes.
