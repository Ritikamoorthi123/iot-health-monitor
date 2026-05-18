from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score
import serial
import time
import json
import os

app = Flask(_name_)
app.secret_key = "secret123"

# =========================
# Load Dataset & Train Model
# =========================

print("📊 Loading Dataset...")

df = pd.read_csv("preeclampsia.csv")

X = df.drop("RiskLevel", axis=1)
y = df["RiskLevel"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model = DecisionTreeClassifier()
model.fit(X_train, y_train)

accuracy = accuracy_score(y_test, model.predict(X_test))
print(f"✅ Model Training Completed! Accuracy: {accuracy*100:.2f}%")

# =========================
# Risk Mapping
# =========================

risk_map = {
    "low risk": 1,
    "mid risk": 2,
    "high risk": 3
}

# =========================
# Arduino Direct Connection (FORCED COM20)
# =========================

arduino = None

try:
    arduino = serial.Serial("COM20", 9600, timeout=1)
    time.sleep(2)
    print("✅ Arduino Connected Successfully on COM20")
except Exception as e:
    print("❌ Arduino Connection Failed:", e)
    print("⚠️ Running in Simulation Mode")

# =========================
# User File Setup
# =========================

users_file = "users.json"

if not os.path.exists(users_file):
    with open(users_file, "w") as f:
        json.dump({}, f)

# =========================
# Routes
# =========================

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with open(users_file, "r") as f:
            users = json.load(f)

        if username in users:
            flash("User already exists!")
            return redirect(url_for("register"))

        users[username] = password

        with open(users_file, "w") as f:
            json.dump(users, f)

        flash("Registration Successful! Please Login.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with open(users_file, "r") as f:
            users = json.load(f)

        if username in users and users[username] == password:
            session["user"] = username
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid Credentials!")

    return render_template("login.html")


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    prediction = None
    risk_color = None

    if request.method == "POST":
        try:
            age = float(request.form["age"])
            systolicBP = float(request.form["systolicBP"])
            diastolicBP = float(request.form["diastolicBP"])
            bs = float(request.form["bs"])
            bodyTemp = float(request.form["bodyTemp"])
            heartRate = float(request.form["heartRate"])

            user_data = [[age, systolicBP, diastolicBP, bs, bodyTemp, heartRate]]

            predicted_risk = model.predict(user_data)[0]
            prediction = predicted_risk

            predicted_risk_lower = predicted_risk.lower()

            # Risk color for UI
            if predicted_risk_lower == "low risk":
                risk_color = "success"
            elif predicted_risk_lower == "mid risk":
                risk_color = "warning"
            else:
                risk_color = "danger"

            # =====================
            # SEND DATA TO ARDUINO
            # =====================

            if arduino and arduino.is_open:
                risk_number = risk_map.get(predicted_risk_lower, 0)
                send_data = str(risk_number) + "\n"
                arduino.write(send_data.encode())
                arduino.flush()

                print("📡 Sent to Arduino:", send_data.strip())

            else:
                print("⚠️ Arduino Not Connected. Simulation Only.")

        except Exception as e:
            print("❌ Error:", e)
            flash("Invalid Input Values!")

    return render_template("dashboard.html",
                           prediction=prediction,
                           risk_color=risk_color)


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


# =========================
# Run App (NO DEBUG)
# =========================

if _name_ == "_main_":
    app.run(debug=False)