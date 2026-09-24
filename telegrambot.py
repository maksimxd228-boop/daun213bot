import tkinter as tk
import time

clicks = 0
times = []

def click():
    global clicks
    clicks += 1
    times.append(time.time())
    label.config(text=f"Кликов: {clicks}")

def update_cps():
    recent = [t for t in times if time.time() - t < 1]
    cps_label.config(text=f"В секунду: {len(recent)}")
    times[:] = recent
    root.after(100, update_cps)

root = tk.Tk()
root.title("Кликер")
root.geometry("300x260")
root.configure(bg="#1e1e2f")

label = tk.Label(root, text="Кликов: 0", font=("Arial", 26, "bold"), bg="#1e1e2f", fg="white")
label.pack(pady=15)

cps_label = tk.Label(root, text="В секунду: 0", font=("Arial", 16), bg="#1e1e2f", fg="#00ff88")
cps_label.pack()

btn = tk.Button(root, text="ЖМИ!", font=("Arial", 22, "bold"), bg="#ff0055", fg="white", bd=0, width=12, height=2, command=click)
btn.pack(pady=20)

update_cps()
root.mainloop()
