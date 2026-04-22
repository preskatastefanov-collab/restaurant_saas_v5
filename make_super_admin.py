from database import init_db, get_db

# първо се уверяваме, че таблиците съществуват
init_db()

conn = get_db()
cursor = conn.cursor()

# смяна на ролята
cursor.execute(
    "UPDATE users SET role = ? WHERE username = ?",
    ("super_admin", "admin")
)

conn.commit()

# проверка
row = cursor.execute(
    "SELECT username, role FROM users WHERE username = ?",
    ("admin",)
).fetchone()

conn.close()

if row:
    print(f"Готово: {row['username']} вече е с роля {row['role']}")
else:
    print("Няма намерен потребител admin")