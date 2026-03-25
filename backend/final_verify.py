import bcrypt

stored_hash = "$2b$12$5lATrza3CdaCCLhqJKP9/ekLNmDE5SYmbNye6WZImVd7qlGhB8JOq"
password_to_test = "Armando2026!"

is_match = bcrypt.checkpw(password_to_test.encode('utf-8'), stored_hash.encode('utf-8'))
print(f"Password: {password_to_test}")
print(f"Match: {is_match}")
