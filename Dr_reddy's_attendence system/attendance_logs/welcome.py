from flask import Flask
import pymysql

app = Flask(__name__)

def connect_db():
    return pymysql.connect(host='database-3.cyf46wciucqs.us-east-1.rds.amazonaws.com',
                           user='admin',
                           password='balaji1234',
                           database='testdb')

@app.route('/')
def users():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    result = cursor.fetchall()
    conn.close()
    return str(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
