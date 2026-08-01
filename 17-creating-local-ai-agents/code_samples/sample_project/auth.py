"""Authentication helpers."""

def login(user, password):
    # TODO: hash the password before comparing
    return user == 'admin' and password == 'secret'

def logout(session):
    session.clear()
