# 🛍️ PowerPay Marketplace Platform

A full-stack Django-powered multi-vendor e-commerce platform that allows users to browse and purchase products, while vendors can manage their own stores. The system includes secure authentication, support ticketing with live chat, vendor management tools, and a global notification system.

---

## 🚀 Features

### 🔐 Authentication & Accounts
Handled by the `accounts` app:
- Custom `User` and `Vendor` models
- Login, signup, logout flows
- Password reset functionality
- Two-Factor Authentication (2FA) via Email OTP
- Secure account management for both vendors and customers

---

### 🏪 Shop / Marketplace System
Managed by the `shop` app:
- Product management (add, edit, delete)
- Product listings and dynamic display for users
- Shopping flow support (orders, sales tracking)
- Vendor dashboard for inventory management
- Admin dashboard to:
  - Approve vendors
  - Suspend vendors
  - View vendor status and store data

---

### 🔔 Notification System
Provided by the `notifications` app:
- Global notification support across the entire project
- Supports multiple notification types (info, warning, success, error)
- Integrated into user dashboards and vendor/admin interfaces

---

### 🎧 Support System
Powered by the `support` app:
- Ticket system where users/vendors can submit support requests
- Admins can reply to tickets
- Real-time chat feature per ticket for direct communication

---

### 🎨 UI Styling & Frontend Tools
This project integrates:
- **Tailwind CSS**
- **DaisyUI**
- **HTMX** for interactive partial updates without full-page reloads

---

## 📁 Project Structure

project_root/
│
├── accounts/
│ ├── models.py
│ ├── views.py
│ ├── forms.py
│ ├── urls.py
│ └── templates/accounts/
│
├── shop/
│ ├── models.py
│ ├── views.py
│ ├── urls.py
│ ├── templates/shop/
│ └── vendor_dashboard/
│
├── notifications/
│ ├── models.py
│ ├── views.py
│ ├── urls.py
│ └── templates/notifications/
│
├── support/
│ ├── models.py
│ ├── views.py
│ ├── urls.py
│ └── templates/support/
│
├── static/
│ ├── css/
│ ├── js/
│ └── images/
│
├── templates/
│ ├── base.html
│ ├── footer.html
│
├── manage.py


---

## 🛠️ Installation and Setup

### Prerequisites

*   Python 3.x
*   Git

### Steps

1.  **Clone the Repository:**

    ```bash
    git clone [Your Repository URL]
    cd POWERPAYSHOP
    ```

2.  **Create and Activate Virtual Environment:**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use: .\venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    (Ensure you have a `requirements.txt` file.)

    ```bash
    pip install -r requirements.txt
    ```

4.  **Database Migration:**

    ```bash
    python manage.py makemigrations
    python manage.py migrate
    ```

5.  **Create Superuser (Admin):**

    ```bash
    python manage.py createsuperuser
    ```

6.  **Run Tailwind Watch (if applicable):**
    If your setup uses a process to compile assets:

    ```bash
    # Example for a typical setup
    python manage.py tailwind start
    ```

7.  **Run the Development Server:**

    ```bash
    python manage.py runserver
    ```

    The site will be accessible at `http://127.0.0.1:8000/`.

---

