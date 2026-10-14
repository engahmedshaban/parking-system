import hashlib
pwd = "P@ssw0rd_@dmin201092"
print(hashlib.sha256(pwd.encode()).hexdigest())